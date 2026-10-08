import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    can_invite: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # Subscription plan code (see app.services.plans.PLANS).
    plan: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="free", default="free"
    )
    # None = plan has no expiry (permanent). When in the past, plan falls back to free.
    plan_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Stored quota limit. When a plan is assigned this is set from the plan;
    # admin may also set a custom value. Effective limit is resolved in quota service.
    quota_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=10737418240
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
