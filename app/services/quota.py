"""Quota service: calculate used/reserved bytes, check limits."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.task_file import TaskFile
from app.models.user import User
from app.services.plans import FREE_PLAN, is_plan_expired


async def get_used_bytes(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Sum of uploaded file sizes for the user."""
    result = await db.execute(
        select(func.coalesce(func.sum(TaskFile.size_bytes), 0))
        .select_from(TaskFile)
        .join(Task, Task.id == TaskFile.task_id)
        .where(Task.user_id == user_id, TaskFile.status == "uploaded")
    )
    return int(result.scalar())


async def get_reserved_bytes(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Sum of reserved bytes for active tasks."""
    result = await db.execute(
        select(func.coalesce(func.sum(Task.reserved_bytes), 0)).where(
            Task.user_id == user_id,
            Task.status.in_(["queued", "assigned", "downloading", "uploading"]),
        )
    )
    return int(result.scalar())


def get_effective_quota_bytes(user: User) -> int:
    """Limit that applies right now.

    An expired plan falls back to free. Otherwise the stored quota_bytes wins
    (set from the plan on assign, or as a custom admin override).
    """
    if is_plan_expired(user):
        return FREE_PLAN.quota_bytes
    return user.quota_bytes


async def check_quota(db: AsyncSession, user_id: uuid.UUID, needed: int) -> bool:
    """Return True if user has enough quota for `needed` bytes."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        return False

    used = await get_used_bytes(db, user_id)
    reserved = await get_reserved_bytes(db, user_id)
    limit = get_effective_quota_bytes(user)
    return (used + reserved + needed) <= limit


async def get_quota_usage(db: AsyncSession, user_id: uuid.UUID) -> tuple[int, int, int]:
    """Return (used_bytes, reserved_bytes, effective_quota_bytes)."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        return 0, 0, 0
    used = await get_used_bytes(db, user_id)
    reserved = await get_reserved_bytes(db, user_id)
    return used, reserved, get_effective_quota_bytes(user)
