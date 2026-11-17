"""Hotel channel authorization: durable status, encrypted credentials, public views."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.adapters.ota.official_http import (
    PLATFORMS,
    contract_is_configured,
    env_credentials,
    load_official_contract,
    platform_write_enabled,
    public_contract_status,
)
from app.config import get_settings
from app.models import ChannelConnection

PLATFORM_LABELS = {
    "ctrip": "携程",
    "meituan": "美团",
    "fliggy": "飞猪",
}

STATUS_DISCONNECTED = "disconnected"
STATUS_CREDENTIALS_MISSING = "credentials_missing"
STATUS_AUTHORIZED = "authorized"
STATUS_ERROR = "error"


def _now() -> datetime:
    return datetime.utcnow()


def _fernet() -> Fernet:
    settings = get_settings()
    secret = (settings.oiro_credentials_key or settings.jwt_secret or "oiro-demo-secret-change-me").strip()
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_credentials(payload: dict[str, str]) -> str:
    cleaned = {k: v for k, v in payload.items() if v}
    if not cleaned:
        return ""
    token = _fernet().encrypt(json.dumps(cleaned, ensure_ascii=False).encode("utf-8"))
    return token.decode("ascii")


def decrypt_credentials(token: str | None) -> dict[str, str]:
    if not token:
        return {}
    try:
        raw = _fernet().decrypt(token.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except (InvalidToken, ValueError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in data.items() if v is not None and str(v)}


def _get_or_create(db: Session, hotel_id: int, platform: str) -> ChannelConnection:
    platform = platform.lower()
    row = (
        db.query(ChannelConnection)
        .filter(ChannelConnection.hotel_id == hotel_id, ChannelConnection.platform == platform)
        .one_or_none()
    )
    if row is None:
        row = ChannelConnection(
            hotel_id=hotel_id,
            platform=platform,
            status=STATUS_DISCONNECTED,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def merged_credentials(row: ChannelConnection | None, platform: str) -> dict[str, str]:
    stored = decrypt_credentials(row.credentials_encrypted if row else "")
    env = env_credentials(platform)
    merged = dict(env)
    merged.update({k: v for k, v in stored.items() if v})
    if row:
        if row.platform_hotel_id and not merged.get("platform_hotel_id"):
            merged["platform_hotel_id"] = row.platform_hotel_id
        if row.platform_account_id and not merged.get("platform_account_id"):
            merged["platform_account_id"] = row.platform_account_id
    return merged


def has_usable_credentials(creds: dict[str, str]) -> bool:
    return bool((creds.get("key") or creds.get("token") or "").strip())


@dataclass
class LiveWriteContext:
    platform: str
    hotel_id: int | None
    status: str
    authorized: bool
    has_credentials: bool
    write_enabled: bool
    contract: dict | None
    credentials: dict[str, str]
    refuse_reason: str | None = None
    refuse_message: str | None = None

    def can_send(self, action: str) -> bool:
        return (
            not self.refuse_reason
            and self.authorized
            and self.has_credentials
            and self.write_enabled
            and contract_is_configured(self.contract, action)
        )


def resolve_live_write_context(db: Session | None, hotel_id: int | None, platform: str) -> LiveWriteContext:
    platform = (platform or "ctrip").lower()
    row = None
    if db is not None and hotel_id is not None:
        row = (
            db.query(ChannelConnection)
            .filter(ChannelConnection.hotel_id == hotel_id, ChannelConnection.platform == platform)
            .one_or_none()
        )
    creds = merged_credentials(row, platform)
    contract = load_official_contract(platform, db, hotel_id=hotel_id)
    write_enabled = platform_write_enabled(platform)
    has_creds = has_usable_credentials(creds)
    authorized = bool(row and row.status == STATUS_AUTHORIZED and has_creds)
    if not authorized and has_creds and row is None:
        # Env-only credentials (ops-provided) can authorize a live write without a UI connection,
        # but still require contract + write flag. Hotel UI connections remain the normal path.
        authorized = True
        status = STATUS_AUTHORIZED
    else:
        status = row.status if row else (STATUS_AUTHORIZED if authorized else STATUS_DISCONNECTED)

    refuse_reason = None
    refuse_message = None
    if not has_creds:
        refuse_reason = "missing_credentials"
        refuse_message = "缺少有效写入凭证，已拒绝真实写入，未发起外部请求。"
    elif not authorized:
        refuse_reason = "channel_unauthorized"
        refuse_message = "该渠道尚未授权，已拒绝真实写入，未发起外部请求。"
    elif not write_enabled:
        refuse_reason = "write_disabled"
        refuse_message = "服务器未开启该渠道写入开关，已拒绝真实写入，未发起外部请求。"
    elif not contract_is_configured(contract):
        refuse_reason = "missing_contract"
        refuse_message = "未配置官方写入契约（base URL / 路径 / 映射），已拒绝真实写入，未发起外部请求。本仓库默认不内置携程/美团/飞猪生产环境 URL。"

    return LiveWriteContext(
        platform=platform,
        hotel_id=hotel_id,
        status=status,
        authorized=authorized,
        has_credentials=has_creds,
        write_enabled=write_enabled,
        contract=contract,
        credentials=creds,
        refuse_reason=refuse_reason,
        refuse_message=refuse_message,
    )


def public_channel(db: Session, hotel_id: int, platform: str) -> dict[str, Any]:
    platform = platform.lower()
    row = (
        db.query(ChannelConnection)
        .filter(ChannelConnection.hotel_id == hotel_id, ChannelConnection.platform == platform)
        .one_or_none()
    )
    contract = load_official_contract(platform, db, hotel_id=hotel_id)
    env = env_credentials(platform)
    stored = decrypt_credentials(row.credentials_encrypted if row else "")
    creds = merged_credentials(row, platform)
    has_stored = has_usable_credentials(stored)
    has_env = has_usable_credentials(env)
    write_flag = platform_write_enabled(platform)
    configured = contract_is_configured(contract)
    contract_meta = public_contract_status(platform, db, hotel_id=hotel_id)
    actions = contract_meta.get("supported_actions") or []
    status = row.status if row else STATUS_DISCONNECTED
    live_ready = (
        status == STATUS_AUTHORIZED
        and has_usable_credentials(creds)
        and write_flag
        and configured
    )
    return {
        "platform": platform,
        "label": PLATFORM_LABELS.get(platform, platform),
        "status": status,
        "authorized_at": row.authorized_at.isoformat() if row and row.authorized_at else None,
        "last_verified": row.last_verified.isoformat() if row and row.last_verified else None,
        "platform_hotel_id": (row.platform_hotel_id if row else "") or env.get("platform_hotel_id") or "",
        "platform_account_id": (row.platform_account_id if row else "") or "",
        "has_credentials": has_stored or has_env,
        "has_server_credentials": has_env,
        "contract_configured": contract_meta["contract_configured"],
        "contract_source": contract_meta["contract_source"],
        "contract_removable": contract_meta["contract_removable"],
        "contract_host": contract_meta["contract_host"],
        "contract_hosts": contract_meta["contract_hosts"],
        "write_flag_enabled": write_flag,
        "live_ready": live_ready,
        "last_error": (row.last_error if row else "") or "",
        "supported_actions": actions,
        "connect_hint": "密钥仅保存在服务器，保存后不再回显。没有官方契约或写入开关时，live 模式会拒绝写入且不会出站。仓库内示例契约不会自动加载，生产 URL 必须来自合作方。",
    }


def list_public_channels(db: Session, hotel_id: int) -> list[dict[str, Any]]:
    return [public_channel(db, hotel_id, platform) for platform in PLATFORMS]


def _secret_fields(payload: dict) -> dict[str, str]:
    mapping = {
        "key": payload.get("key") or payload.get("api_key") or payload.get("write_key"),
        "secret": payload.get("secret") or payload.get("api_secret") or payload.get("write_secret"),
        "session": payload.get("session"),
        "token": payload.get("token"),
    }
    return {k: str(v).strip() for k, v in mapping.items() if v is not None and str(v).strip()}


def save_channel_connection(db: Session, hotel_id: int, platform: str, payload: dict) -> ChannelConnection:
    platform = platform.lower()
    if platform not in PLATFORMS:
        raise ValueError("仅支持携程、美团、飞猪渠道授权")
    row = _get_or_create(db, hotel_id, platform)
    if "platform_hotel_id" in payload and payload["platform_hotel_id"] is not None:
        row.platform_hotel_id = str(payload["platform_hotel_id"]).strip()
    if "platform_account_id" in payload and payload["platform_account_id"] is not None:
        row.platform_account_id = str(payload["platform_account_id"]).strip()

    stored = decrypt_credentials(row.credentials_encrypted)
    provided = _secret_fields(payload)
    # Empty string on a secret field means "clear this field". Omitted means keep.
    for field in ("key", "secret", "session", "token"):
        if field in payload and payload[field] is not None and str(payload[field]) == "":
            stored.pop(field, None)
        elif field in provided:
            stored[field] = provided[field]
    if row.platform_hotel_id:
        stored["platform_hotel_id"] = row.platform_hotel_id
    if row.platform_account_id:
        stored["platform_account_id"] = row.platform_account_id

    row.credentials_encrypted = encrypt_credentials(stored)
    if has_usable_credentials(stored) or has_usable_credentials(merged_credentials(row, platform)):
        row.status = STATUS_AUTHORIZED
        if row.authorized_at is None:
            row.authorized_at = _now()
        row.last_error = ""
    else:
        row.status = STATUS_CREDENTIALS_MISSING
        row.authorized_at = None
        row.last_error = "已保存连接，但还没有可用的密钥。"
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def disconnect_channel(db: Session, hotel_id: int, platform: str) -> ChannelConnection:
    row = _get_or_create(db, hotel_id, platform)
    row.credentials_encrypted = ""
    row.status = STATUS_DISCONNECTED
    row.authorized_at = None
    row.last_verified = None
    row.last_error = ""
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def mark_channel_verified(db: Session, hotel_id: int, platform: str, *, error: str | None = None) -> None:
    row = (
        db.query(ChannelConnection)
        .filter(ChannelConnection.hotel_id == hotel_id, ChannelConnection.platform == platform)
        .one_or_none()
    )
    if row is None:
        return
    if error:
        row.status = STATUS_ERROR
        row.last_error = error
    else:
        if has_usable_credentials(decrypt_credentials(row.credentials_encrypted)) or has_usable_credentials(merged_credentials(row, platform)):
            row.status = STATUS_AUTHORIZED
            if row.authorized_at is None:
                row.authorized_at = _now()
        row.last_verified = _now()
        row.last_error = ""
    row.updated_at = _now()
    db.commit()


def verify_channel(db: Session, hotel_id: int, platform: str) -> dict[str, Any]:
    """Check authorization. Opens a socket only when a contract verify/write path is configured."""
    platform = platform.lower()
    row = _get_or_create(db, hotel_id, platform)
    ctx = resolve_live_write_context(db, hotel_id, platform)
    if not ctx.has_credentials:
        row.status = STATUS_CREDENTIALS_MISSING
        row.last_error = "还没有可用的密钥，无法校验。"
        row.updated_at = _now()
        db.commit()
        return public_channel(db, hotel_id, platform)

    contract = ctx.contract
    verify_action = None
    if contract_is_configured(contract):
        actions = contract.get("actions") or {}
        if "verify" in actions:
            verify_action = "verify"
    if not contract_is_configured(contract) or not verify_action:
        # Credentials are saved, but there is no official verify endpoint to call.
        if ctx.has_credentials:
            row.status = STATUS_AUTHORIZED
            if row.authorized_at is None:
                row.authorized_at = _now()
            row.last_error = (
                ""
                if contract_is_configured(contract)
                else "凭证已保存，但未配置官方契约，无法向官方接口做连通性校验。live 写入会被拒绝，本次未发起外部请求。"
            )
        row.updated_at = _now()
        db.commit()
        return public_channel(db, hotel_id, platform)

    from app.adapters.ota.official_http import OfficialHttpClient, OfficialHttpError

    client = OfficialHttpClient(platform, contract, ctx.credentials)
    try:
        client.send_write(verify_action, {"checkpoint_id": "channel-verify"}, [], request_id="verify")
        mark_channel_verified(db, hotel_id, platform)
    except OfficialHttpError as exc:
        mark_channel_verified(db, hotel_id, platform, error=exc.message)
    return public_channel(db, hotel_id, platform)
