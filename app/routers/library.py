from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.library_item import LibraryItem
from app.models.media_item import MediaItem
from app.models.task import Task
from app.models.task_file import TaskFile
from app.models.user import User
from app.services.auth import get_current_user
from app.services.s3 import presign_get

router = APIRouter(tags=["library"])


@router.get("/api/library")
async def get_library(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LibraryItem, MediaItem)
        .join(MediaItem, MediaItem.id == LibraryItem.media_item_id)
        .where(LibraryItem.user_id == user.id)
        .order_by(LibraryItem.created_at.desc())
    )
    rows = result.all()

    library = []
    for lib_item, media_item in rows:
        # Get files for this library item
        files_result = await db.execute(
            select(TaskFile)
            .join(Task, Task.id == TaskFile.task_id)
            .where(
                Task.user_id == user.id,
                Task.media_item_id == lib_item.media_item_id,
                TaskFile.status == "uploaded",
            )
        )
        files = files_result.scalars().all()
        total_size = sum(f.size_bytes for f in files)

        library.append(
            {
                "library_item": {
                    "id": str(lib_item.id),
                    "status": lib_item.status,
                    "created_at": lib_item.created_at.isoformat(),
                },
                "media_item": {
                    "id": str(media_item.id),
                    "title": media_item.title,
                    "poster_url": media_item.poster_url,
                    "kp_type": media_item.kp_type,
                    "year": media_item.year,
                },
                "files": [
                    {
                        "id": str(f.id),
                        "path": f.path,
                        "size_bytes": f.size_bytes,
                        "status": f.status,
                        "season": f.season,
                        "episode": f.episode,
                    }
                    for f in files
                ],
                "total_size": total_size,
                "ready": lib_item.status == "ready",
            }
        )

    return library


@router.get("/api/files/{task_file_id}/url")
async def get_file_url(
    task_file_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify ownership through library_items
    result = await db.execute(
        select(TaskFile, Task)
        .join(Task, Task.id == TaskFile.task_id)
        .where(TaskFile.id == task_file_id, Task.user_id == user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    tf, _task = row
    if tf.status != "uploaded" or not tf.s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not yet uploaded"
        )

    url = presign_get(tf.s3_key)
    return {"url": url, "expires_in": 86400}
