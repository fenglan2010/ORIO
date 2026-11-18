"""Operator / maintenance APIs. Hotel tokens cannot access these routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.adapters.ota.official_http import ContractValidationError, PLATFORMS, set_platform_write_enabled
from app.auth import SCOPE_OPS, create_token, get_current_operator, is_operator_user, verify_password
from app.database import get_db
from app.models import Hotel, User
from app.services.channels import (
    list_ops_channels,
    ops_public_channel,
    save_official_api_credentials,
)
from app.services.official_contracts import (
    install_official_contract,
    uninstall_official_contract,
    validation_report,
)
from app.services.tenancy import public_hotel
from app.services.workflow import write_audit

router = APIRouter(prefix="/api/ops", tags=["ops"])


class OpsLoginRequest(BaseModel):
    username: str
    password: str


class OfficialCredentialsBody(BaseModel):
    key: str | None = Field(default=None, description="Official API key; omitted keeps the stored value, empty clears it.")
    secret: str | None = None
    token: str | None = None
    session: str | None = None


class WriteFlagBody(BaseModel):
    enabled: bool


def _platform(platform: str) -> str:
    value = (platform or "").strip().lower()
    if value not in PLATFORMS:
        raise HTTPException(status_code=404, detail="仅支持携程、美团、飞猪渠道")
    return value


def _hotel(db: Session, hotel_id: int) -> Hotel:
    hotel = db.get(Hotel, hotel_id)
    if hotel is None:
        raise HTTPException(status_code=404, detail="酒店不存在")
    return hotel


@router.post("/auth/login")
def login(body: OpsLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if getattr(user, "disabled", False):
        raise HTTPException(status_code=401, detail="账号已停用，无法登录")
    if not is_operator_user(user):
        raise HTTPException(status_code=403, detail="请使用运维账号从运维端登录")
    return {
        "access_token": create_token(user, scope=SCOPE_OPS),
        "token_type": "bearer",
        "display_name": user.display_name,
        "role": "operator",
        "role_label": "运维管理员",
        "scope": SCOPE_OPS,
    }


@router.get("/auth/me")
def me(user: User = Depends(get_current_operator)):
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": "operator",
        "role_label": "运维管理员",
        "scope": SCOPE_OPS,
        "disabled": bool(getattr(user, "disabled", False)),
    }


@router.get("/hotels")
def list_hotels(db: Session = Depends(get_db), user: User = Depends(get_current_operator)):
    rows = db.query(Hotel).order_by(Hotel.id.asc()).all()
    return {"hotels": [public_hotel(row) for row in rows]}


@router.get("/hotels/{hotel_id}/channels")
def list_channels(hotel_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_operator)):
    hotel = _hotel(db, hotel_id)
    return {"hotel": public_hotel(hotel), "channels": list_ops_channels(db, hotel.id)}


@router.get("/hotels/{hotel_id}/channels/{platform}")
def get_channel(
    hotel_id: int,
    platform: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_operator),
):
    hotel = _hotel(db, hotel_id)
    return ops_public_channel(db, hotel.id, _platform(platform))


@router.post("/hotels/{hotel_id}/channels/{platform}/contract/validate")
def validate_contract(
    hotel_id: int,
    platform: str,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_operator),
):
    _hotel(db, hotel_id)
    report = validation_report(body, _platform(platform))
    if not report["valid"]:
        raise HTTPException(status_code=400, detail="；".join(report["errors"] or [report["message"]]))
    return report


@router.put("/hotels/{hotel_id}/channels/{platform}/contract")
def put_contract(
    hotel_id: int,
    platform: str,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_operator),
):
    hotel = _hotel(db, hotel_id)
    platform = _platform(platform)
    try:
        result = install_official_contract(db, platform, body, actor=user.username, hotel_id=hotel.id)
    except ContractValidationError as exc:
        raise HTTPException(status_code=400, detail="；".join(exc.errors or [exc.message])) from exc
    public = ops_public_channel(db, hotel.id, platform)
    public.update({k: result[k] for k in result if k not in {"headers", "contract", "auth_header", "key_header", "request_template", "base_url"}})
    return public


@router.delete("/hotels/{hotel_id}/channels/{platform}/contract")
def delete_contract(
    hotel_id: int,
    platform: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_operator),
):
    hotel = _hotel(db, hotel_id)
    platform = _platform(platform)
    try:
        result = uninstall_official_contract(db, platform, actor=user.username, hotel_id=hotel.id)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    public = ops_public_channel(db, hotel.id, platform)
    public.update({k: result[k] for k in result if k not in public})
    return public


@router.put("/hotels/{hotel_id}/channels/{platform}/write-flag")
def put_write_flag(
    hotel_id: int,
    platform: str,
    body: WriteFlagBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_operator),
):
    hotel = _hotel(db, hotel_id)
    platform = _platform(platform)
    enabled = set_platform_write_enabled(db, hotel.id, platform, body.enabled)
    write_audit(
        db,
        actor=user.username,
        action="ops_write_flag",
        entity_type="channel_connection",
        entity_id=f"{hotel.id}:{platform}",
        hotel_id=hotel.id,
        after={"platform": platform, "write_flag_enabled": enabled},
        reason="运维端更新渠道写入开关（不会单独发起出站请求）",
    )
    return ops_public_channel(db, hotel.id, platform)


@router.put("/hotels/{hotel_id}/channels/{platform}/official-credentials")
def put_official_credentials(
    hotel_id: int,
    platform: str,
    body: OfficialCredentialsBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_operator),
):
    hotel = _hotel(db, hotel_id)
    platform = _platform(platform)
    stored = save_official_api_credentials(db, hotel.id, platform, body.model_dump(exclude_unset=True))
    write_audit(
        db,
        actor=user.username,
        action="ops_official_credentials",
        entity_type="channel_connection",
        entity_id=f"{hotel.id}:{platform}",
        hotel_id=hotel.id,
        after={"platform": platform, "has_official_credentials": bool(stored)},
        reason="运维端保存官方接口凭证（密钥不写入审计，也不回显）",
    )
    return ops_public_channel(db, hotel.id, platform)
