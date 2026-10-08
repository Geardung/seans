import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.schemas.auth import (
    AdminUserPatch,
    AdminUserResponse,
    PlanInfo,
    UserResponse,
)
from app.services.auth import require_admin
from app.services.plans import PLANS
from app.services.quota import (
    get_effective_quota_bytes,
    get_reserved_bytes,
    get_used_bytes,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _to_admin_response(
    user: User,
    used_bytes: int = 0,
    reserved_bytes: int = 0,
) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        can_invite=user.can_invite,
        plan=user.plan,
        plan_expires_at=user.plan_expires_at,
        quota_bytes=user.quota_bytes,
        effective_quota_bytes=get_effective_quota_bytes(user),
        used_bytes=used_bytes,
        reserved_bytes=reserved_bytes,
        created_at=user.created_at,
    )


@router.get("/plans", response_model=list[PlanInfo])
async def list_plans(_admin: User = Depends(require_admin)):
    return [
        PlanInfo(code=plan.code, title=plan.title, quota_bytes=plan.quota_bytes)
        for plan in PLANS.values()
    ]


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    out: list[AdminUserResponse] = []
    for user in users:
        used = await get_used_bytes(db, user.id)
        reserved = await get_reserved_bytes(db, user.id)
        out.append(_to_admin_response(user, used, reserved))
    return out


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    used = await get_used_bytes(db, user.id)
    reserved = await get_reserved_bytes(db, user.id)
    return _to_admin_response(user, used, reserved)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def patch_user(
    user_id: uuid.UUID,
    body: AdminUserPatch,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if body.is_admin is False and user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin access",
        )

    if body.plan is not None:
        if body.plan not in PLANS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown plan: {body.plan}",
            )
        user.plan = body.plan
        # Explicit plan_expires_at (including null = permanent) applies only with plan.
        user.plan_expires_at = body.plan_expires_at
        if body.quota_bytes is None:
            user.quota_bytes = PLANS[body.plan].quota_bytes

    if body.quota_bytes is not None:
        user.quota_bytes = body.quota_bytes

    if body.is_admin is not None:
        user.is_admin = body.is_admin
    if body.can_invite is not None:
        user.can_invite = body.can_invite

    await db.commit()
    await db.refresh(user)
    used = await get_used_bytes(db, user.id)
    reserved = await get_reserved_bytes(db, user.id)
    return _to_admin_response(user, used, reserved)


@router.get("/me", response_model=UserResponse)
async def admin_me(admin: User = Depends(require_admin)):
    return UserResponse(
        id=admin.id,
        email=admin.email,
        display_name=admin.display_name,
        is_admin=admin.is_admin,
        can_invite=admin.can_invite,
        plan=admin.plan,
        plan_expires_at=admin.plan_expires_at,
        quota_bytes=get_effective_quota_bytes(admin),
        created_at=admin.created_at,
    )
