from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.library_item import LibraryItem
from app.models.task import Task
from app.models.torrent_release import TorrentRelease
from app.models.user import User
from app.schemas.task import CreateTaskRequest, TaskDetailResponse, TaskResponse
from app.services.auth import get_current_user
from app.services.quota import check_quota

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: CreateTaskRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify release exists
    result = await db.execute(
        select(TorrentRelease).where(TorrentRelease.id == body.torrent_release_id)
    )
    release = result.scalar_one_or_none()
    if release is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Torrent release not found"
        )

    # Check quota
    if not await check_quota(db, user.id, release.size_bytes):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="quota_exceeded"
        )

    # Create task
    task = Task(
        user_id=user.id,
        media_item_id=release.media_item_id,
        torrent_release_id=release.id,
        reserved_bytes=release.size_bytes,
        status="queued",
    )
    db.add(task)

    # Ensure library item exists
    lib_stmt = select(LibraryItem).where(
        LibraryItem.user_id == user.id,
        LibraryItem.media_item_id == release.media_item_id,
    )
    lib_result = await db.execute(lib_stmt)
    if lib_result.scalar_one_or_none() is None:
        db.add(
            LibraryItem(
                user_id=user.id,
                media_item_id=release.media_item_id,
                source_task_id=task.id,
            )
        )

    await db.commit()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.get("", response_model=list[TaskDetailResponse])
async def list_tasks(
    active: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Task).where(Task.user_id == user.id)
    if active:
        stmt = stmt.where(
            Task.status.in_(["queued", "assigned", "downloading", "uploading"])
        )
    stmt = stmt.order_by(Task.created_at.desc())
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [TaskDetailResponse.model_validate(t) for t in tasks]


@router.post("/{task_id}/cancel", response_model=TaskDetailResponse)
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    if task.status not in ("queued", "assigned"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel task in progress",
        )

    task.status = "canceled"
    task.reserved_bytes = 0
    await db.commit()
    await db.refresh(task)
    return TaskDetailResponse.model_validate(task)
