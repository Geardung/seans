import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str
    invite_key: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    can_invite: bool
    plan: str
    plan_expires_at: datetime | None = None
    quota_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class InviteKeyResponse(BaseModel):
    key: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanInfo(BaseModel):
    code: str
    title: str
    quota_bytes: int


class AdminUserPatch(BaseModel):
    is_admin: bool | None = None
    can_invite: bool | None = None
    plan: str | None = None
    plan_expires_at: datetime | None = None
    quota_bytes: int | None = Field(default=None, ge=0)


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    can_invite: bool
    plan: str
    plan_expires_at: datetime | None = None
    quota_bytes: int
    effective_quota_bytes: int
    used_bytes: int = 0
    reserved_bytes: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}
