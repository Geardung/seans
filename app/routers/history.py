from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.media_item import MediaItem
from app.models.task import Task
from app.models.task_file import TaskFile
from app.models.user import User
from app.models.watch_history import WatchHistory
from app.schemas.history import HistoryResponse, HistoryUpsertRequest
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/history", tags=["history"])


@router.put("", response_model=HistoryResponse)
async def upsert_history(
    body: HistoryUpsertRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    completed = (
        body.position_sec >= body.duration_sec * 0.95
        if body.duration_sec > 0
        else False
    )

    stmt = (
        pg_insert(WatchHistory)
        .values(
            id=WatchHistory.id.default.arg()
            if hasattr(WatchHistory.id.default, "arg")
            else None,
            user_id=user.id,
            task_file_id=body.task_file_id,
            position_sec=body.position_sec,
            duration_sec=body.duration_sec,
            completed=completed,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "task_file_id"],
            set_={
                "position_sec": body.position_sec,
                "duration_sec": body.duration_sec,
                "completed": completed,
                "updated_at": func.now(),
            },
        )
        .returning(WatchHistory)
    )
    result = await db.execute(stmt)
    await db.commit()
    entry = result.scalar_one()
    return HistoryResponse.model_validate(entry)


@router.get("", response_model=list[dict])
async def get_history(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WatchHistory, TaskFile, Task, MediaItem)
        .join(TaskFile, TaskFile.id == WatchHistory.task_file_id)
        .join(Task, Task.id == TaskFile.task_id)
        .join(MediaItem, MediaItem.id == Task.media_item_id)
        .where(WatchHistory.user_id == user.id, WatchHistory.completed == False)
        .order_by(WatchHistory.updated_at.desc())
        .limit(limit)
    )
    rows = result.all()

    items = []
    for history, tf, task, media in rows:
        pct = (
            int(history.position_sec / history.duration_sec * 100)
            if history.duration_sec > 0
            else 0
        )
        items.append(
            {
                "history": HistoryResponse.model_validate(history).model_dump(),
                "media": {
                    "id": str(media.id),
                    "title": media.title,
                    "poster_url": media.poster_url,
                },
                "file": {
                    "id": str(tf.id),
                    "path": tf.path,
                },
                "progress_pct": pct,
            }
        )

    return items
