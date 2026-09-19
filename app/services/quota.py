"""Quota service: calculate used/reserved bytes, check limits."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.task_file import TaskFile
from app.models.user import User


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


async def check_quota(db: AsyncSession, user_id: uuid.UUID, needed: int) -> bool:
    """Return True if user has enough quota for `needed` bytes."""
    user_result = await db.execute(select(User.quota_bytes).where(User.id == user_id))
    quota = user_result.scalar()
    if quota is None:
        return False

    used = await get_used_bytes(db, user_id)
    reserved = await get_reserved_bytes(db, user_id)
    return (used + reserved + needed) <= quota
