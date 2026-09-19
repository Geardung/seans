import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class HistoryUpsertRequest(BaseModel):
    task_file_id: uuid.UUID
    position_sec: float
    duration_sec: float


class HistoryResponse(BaseModel):
    id: uuid.UUID
    task_file_id: uuid.UUID
    position_sec: Decimal
    duration_sec: Decimal
    completed: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
