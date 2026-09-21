import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.invite_key import InviteKey
from app.models.user import User
from app.schemas.auth import (
    InviteKeyResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    result = await db.execute(
        select(InviteKey).where(InviteKey.key == body.invite_key, InviteKey.used_by.is_(None))
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already used invite key"
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    await db.flush()

    invite.used_by = user.id
    invite.used_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.post(
    "/invite-keys",
    response_model=InviteKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite_key(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.can_invite:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You cannot generate invite keys"
        )

    invite = InviteKey(
        key=uuid.uuid4().hex,
        created_by=user.id,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return InviteKeyResponse.model_validate(invite)
