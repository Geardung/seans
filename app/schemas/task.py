import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateTaskRequest(BaseModel):
    torrent_release_id: uuid.UUID
    file_paths: list[str]


class TaskResponse(BaseModel):
    id: uuid.UUID
    status: str
    reserved_bytes: int
    progress_pct: int
    speed_bps: int
    stage: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskDetailResponse(BaseModel):
    id: uuid.UUID
    status: str
    reserved_bytes: int
    progress_pct: int
    speed_bps: int
    stage: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
