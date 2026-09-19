"""Task queue: claim via FOR UPDATE SKIP LOCKED, lease management."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.task import Task


async def claim_task(db: AsyncSession, worker_id: uuid.UUID) -> Task | None:
    """Atomically claim the highest-priority queued task. Returns None if queue empty."""
    lease_minutes = settings.LEASE_MINUTES
    now = datetime.now(UTC)
    lease_until = now + timedelta(minutes=lease_minutes)

    # Find and lock a queued task
    result = await db.execute(
        select(Task)
        .where(Task.status == "queued")
        .order_by(Task.priority.desc(), Task.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return None

    # Assign to worker
    task.status = "assigned"
    task.worker_id = worker_id
    task.lease_expires_at = lease_until
    task.attempts += 1
    await db.commit()
    await db.refresh(task)
    return task


async def extend_lease(db: AsyncSession, task: Task) -> None:
    """Extend the lease for an active task."""
    lease_minutes = settings.LEASE_MINUTES
    task.lease_expires_at = datetime.now(UTC) + timedelta(minutes=lease_minutes)
    await db.commit()


async def reclaim_expired_tasks(db: AsyncSession) -> int:
    """Return expired tasks to the queue. Returns count of reclaimed tasks."""
    now = datetime.now(UTC)

    # Reclaim tasks with expired leases
    result = await db.execute(
        update(Task)
        .where(
            Task.status.in_(["assigned", "downloading", "uploading"]),
            Task.lease_expires_at < now,
        )
        .values(status="queued", worker_id=None, lease_expires_at=None)
    )
    reclaimed = result.rowcount

    # Fail tasks that exceeded max attempts
    await db.execute(
        update(Task)
        .where(
            Task.status == "queued",
            Task.attempts >= Task.max_attempts,
        )
        .values(status="failed", reserved_bytes=0, error="Max attempts exceeded")
    )

    await db.commit()
    return reclaimed
