import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateRoomRequest(BaseModel):
    task_file_id: uuid.UUID


class RoomResponse(BaseModel):
    id: uuid.UUID
    code: str
    ws_url: str


class RoomDetailResponse(BaseModel):
    id: uuid.UUID
    code: str
    host_user_id: uuid.UUID
    is_playing: bool
    current_position: float
    created_at: datetime

    model_config = {"from_attributes": True}
