import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models.library_item import LibraryItem
from app.models.task import Task
from app.models.task_file import TaskFile
from app.models.torrent_release import TorrentRelease
from app.models.worker import Worker
from app.services.s3 import presign_put
from app.services.task_queue import claim_task, extend_lease

router = APIRouter(prefix="/api/worker", tags=["worker"])


async def get_worker(
    x_worker_token: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Worker:
    token_hash = hashlib.sha256(x_worker_token.encode()).hexdigest()
    result = await db.execute(select(Worker).where(Worker.token_hash == token_hash))
    worker = result.scalar_one_or_none()
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid worker token"
        )
    worker.last_seen_at = datetime.now(UTC)
    await db.commit()
    return worker


@router.post("/register")
async def register_worker(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    name = body.get("name")
    reg_secret = body.get("reg_secret")
    if not name or reg_secret != settings.WORKER_REG_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid registration secret",
        )

    worker_token = uuid.uuid4().hex + uuid.uuid4().hex[:8]  # 40 hex chars
    token_hash = hashlib.sha256(worker_token.encode()).hexdigest()

    worker = Worker(
        id=uuid.uuid4(),
        name=name,
        token_hash=token_hash,
    )
    db.add(worker)
    await db.commit()

    return {"worker_token": worker_token}


@router.post("/claim")
async def worker_claim(
    db: AsyncSession = Depends(get_db),
    worker: Worker = Depends(get_worker),
):
    task = await claim_task(db, worker.id)
    if task is None:
        return None  # 204 No Content

    # Get release info for magnet
    release_result = await db.execute(
        select(TorrentRelease).where(TorrentRelease.id == task.torrent_release_id)
    )
    release = release_result.scalar_one()

    # Generate presigned PUT URLs for upload slots
    # (simplified: one slot per task, actual files come via manifest)
    upload_slots = []
    # We'll generate slots after manifest; for now return task info

    return {
        "task_id": str(task.id),
        "media": {
            "title": release.title if release else "",
            "kp_id": None,
        },
        "magnet": release.magnet if release else None,
        "file_paths": [],  # Worker discovers files from torrent metadata
        "lease_minutes": settings.LEASE_MINUTES,
        "upload_slots": upload_slots,
    }


@router.post("/manifest")
async def worker_manifest(
    body: dict,
    db: AsyncSession = Depends(get_db),
    worker: Worker = Depends(get_worker),
):
    task_id = body.get("task_id")
    files = body.get("files", [])

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    # Create task_files
    total_size = 0
    for f in files:
        s3_key = f"users/{task.user_id}/{task.media_item_id}/{f['path'].split('/')[-1]}"
        tf = TaskFile(
            task_id=task.id,
            path=f["path"],
            size_bytes=f.get("size_bytes", 0),
            s3_key=s3_key,
        )
        db.add(tf)
        total_size += f.get("size_bytes", 0)

    # Recalculate reserved_bytes (only downward)
    task.reserved_bytes = min(task.reserved_bytes, total_size)

    task.status = "downloading"
    await db.commit()

    # Return presigned PUT URLs for each file
    upload_slots = []
    tf_result = await db.execute(select(TaskFile).where(TaskFile.task_id == task.id))
    for tf in tf_result.scalars().all():
        put_url = presign_put(tf.s3_key)
        upload_slots.append(
            {
                "path": tf.path,
                "s3_key": tf.s3_key,
                "put_url": put_url,
                "headers": {"Content-Type": "application/octet-stream"},
            }
        )

    return {"task_id": str(task.id), "upload_slots": upload_slots}


@router.post("/heartbeat")
async def worker_heartbeat(
    body: dict,
    db: AsyncSession = Depends(get_db),
    worker: Worker = Depends(get_worker),
):
    task_id = body.get("task_id")
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    if task.worker_id != worker.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task not assigned to this worker",
        )

    # Check lease
    if task.lease_expires_at and task.lease_expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Lease expired"
        )

    task.progress_pct = body.get("progress_pct", task.progress_pct)
    task.speed_bps = body.get("speed_bps", task.speed_bps)
    task.stage = body.get("stage", task.stage)
    await extend_lease(db, task)

    return {"ok": True}


@router.post("/complete")
async def worker_complete(
    body: dict,
    db: AsyncSession = Depends(get_db),
    worker: Worker = Depends(get_worker),
):
    task_id = body.get("task_id")
    files = body.get("files", [])

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    if task.worker_id != worker.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task not assigned to this worker",
        )

    # Update task_files
    for f in files:
        tf_result = await db.execute(
            select(TaskFile).where(
                TaskFile.task_id == task.id, TaskFile.path == f["path"]
            )
        )
        tf = tf_result.scalar_one_or_none()
        if tf:
            tf.status = "uploaded"
            tf.s3_key = f.get("s3_key", tf.s3_key)
            tf.size_bytes = f.get("size_bytes", tf.size_bytes)
            tf.uploaded_at = datetime.now(UTC)

    # Mark task completed
    task.status = "completed"
    task.reserved_bytes = 0
    task.progress_pct = 100

    # Update library item to ready
    lib_result = await db.execute(
        select(LibraryItem).where(
            LibraryItem.user_id == task.user_id,
            LibraryItem.media_item_id == task.media_item_id,
        )
    )
    lib = lib_result.scalar_one_or_none()
    if lib:
        lib.status = "ready"

    await db.commit()
    return {"ok": True}


@router.post("/fail")
async def worker_fail(
    body: dict,
    db: AsyncSession = Depends(get_db),
    worker: Worker = Depends(get_worker),
):
    task_id = body.get("task_id")
    error = body.get("error", "Unknown error")

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    if task.worker_id != worker.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task not assigned to this worker",
        )

    if task.attempts < task.max_attempts:
        task.status = "queued"
        task.worker_id = None
        task.lease_expires_at = None
    else:
        task.status = "failed"
        task.reserved_bytes = 0

    task.error = error
    await db.commit()
    return {"ok": True}
