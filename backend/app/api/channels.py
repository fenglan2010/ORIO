from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_hotel
from app.auth import get_current_user
from app.database import get_db
from app.models import Hotel, User
from app.services.permissions import require
from app.services.channels import (
    PLATFORMS,
    disconnect_channel,
    list_public_channels,
    public_channel,
    save_channel_connection,
    verify_channel,
)
from app.adapters.ota.official_http import ContractValidationError
from app.services.official_contracts import (
    install_official_contract,
    uninstall_official_contract,
    validation_report,
)
from app.services.workflow import write_audit

router = APIRouter(prefix="/api/channels", tags=["channels"], dependencies=[Depends(get_current_user)])


class ChannelConnectBody(BaseModel):
    platform_hotel_id: str | None = None
    platform_account_id: str | None = None
    key: str | None = Field(default=None, description="Write key; omitted keeps the stored value, empty clears it.")
    secret: str | None = None
    session: str | None = None


def _platform(platform: str) -> str:
    value = (platform or "").strip().lower()
    if value not in PLATFORMS:
        raise HTTPException(status_code=404, detail="仅支持携程、美团、飞猪渠道")
    return value


def _public(db: Session, hotel: Hotel, platform: str) -> dict:
    body = public_channel(db, hotel.id, platform)
    for forbidden in (
        "key", "secret", "token", "session", "credentials_encrypted",
        "write_key", "write_secret", "api_key", "api_secret",
        "contract", "headers", "auth_header", "key_header", "request_template",
    ):
        body.pop(forbidden, None)
    return body


@router.get("")
def list_channels(db: Session = Depends(get_db), hotel: Hotel = Depends(current_hotel), user: User = Depends(require("view_channels"))):
    return {"channels": list_public_channels(db, hotel.id)}


@router.get("/{platform}")
def get_channel(platform: str, db: Session = Depends(get_db), hotel: Hotel = Depends(current_hotel), user: User = Depends(require("view_channels"))):
    return _public(db, hotel, _platform(platform))


@router.put("/{platform}")
def connect_channel(
    platform: str,
    body: ChannelConnectBody,
    db: Session = Depends(get_db),
    hotel: Hotel = Depends(current_hotel),
    user: User = Depends(require("manage_channels")),
):
    platform = _platform(platform)
    payload = body.model_dump(exclude_unset=True)
    try:
        row = save_channel_connection(db, hotel.id, platform, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit(
        db,
        actor=user.username,
        action="channel_connect",
        entity_type="channel_connection",
        entity_id=f"{hotel.id}:{platform}",
        after={
            "platform": platform,
            "status": row.status,
            "has_credentials": bool(row.credentials_encrypted),
            "platform_hotel_id": row.platform_hotel_id,
            "platform_account_id": row.platform_account_id,
        },
        reason="保存渠道连接（密钥不写入审计）",
    )
    return _public(db, hotel, platform)


@router.post("/{platform}/verify")
def verify(
    platform: str,
    db: Session = Depends(get_db),
    hotel: Hotel = Depends(current_hotel),
    user: User = Depends(require("manage_channels")),
):
    platform = _platform(platform)
    result = verify_channel(db, hotel.id, platform)
    write_audit(
        db,
        actor=user.username,
        action="channel_verify",
        entity_type="channel_connection",
        entity_id=f"{hotel.id}:{platform}",
        after={"platform": platform, "status": result.get("status"), "last_error": result.get("last_error")},
        reason="校验渠道连接（未回显密钥）",
    )
    return result


@router.post("/{platform}/disconnect")
def disconnect(
    platform: str,
    db: Session = Depends(get_db),
    hotel: Hotel = Depends(current_hotel),
    user: User = Depends(require("manage_channels")),
):
    platform = _platform(platform)
    row = disconnect_channel(db, hotel.id, platform)
    write_audit(
        db,
        actor=user.username,
        action="channel_disconnect",
        entity_type="channel_connection",
        entity_id=f"{hotel.id}:{platform}",
        after={"platform": platform, "status": row.status},
        reason="断开渠道并清除已保存的密钥",
    )
    return _public(db, hotel, platform)


@router.post("/{platform}/contract/validate")
def validate_contract(
    platform: str,
    body: dict,
    user: User = Depends(require("manage_channels")),
):
    """Schema-check a contract JSON. Does not persist and does not open a socket."""
    report = validation_report(body, _platform(platform))
    if not report["valid"]:
        raise HTTPException(status_code=400, detail="；".join(report["errors"] or [report["message"]]))
    return report


@router.put("/{platform}/contract")
def put_contract(
    platform: str,
    body: dict,
    db: Session = Depends(get_db),
    hotel: Hotel = Depends(current_hotel),
    user: User = Depends(require("manage_channels")),
):
    platform = _platform(platform)
    try:
        result = install_official_contract(db, platform, body, actor=user.username, hotel_id=hotel.id)
    except ContractValidationError as exc:
        raise HTTPException(status_code=400, detail="；".join(exc.errors or [exc.message])) from exc
    public = _public(db, hotel, platform)
    public.update({k: result[k] for k in result if k not in public})
    return public


@router.delete("/{platform}/contract")
def delete_contract(
    platform: str,
    db: Session = Depends(get_db),
    hotel: Hotel = Depends(current_hotel),
    user: User = Depends(require("manage_channels")),
):
    platform = _platform(platform)
    try:
        result = uninstall_official_contract(db, platform, actor=user.username, hotel_id=hotel.id)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    public = _public(db, hotel, platform)
    public.update({k: result[k] for k in result if k not in public})
    return public
