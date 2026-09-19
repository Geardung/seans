import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    media_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_items.id"), nullable=False
    )
    torrent_release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("torrent_releases.id"), nullable=False
    )
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workers.id")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    progress_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    speed_bps: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    stage: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','assigned','downloading','uploading','completed','failed','canceled')",
            name="ck_tasks_status",
        ),
        Index(
            "idx_tasks_claim",
            "status",
            "priority",
            "created_at",
            postgresql_where="status = 'queued'",
        ),
        Index(
            "idx_tasks_lease",
            "lease_expires_at",
            postgresql_where="status IN ('assigned','downloading','uploading')",
        ),
    )
