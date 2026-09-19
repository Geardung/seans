import uuid
from datetime import datetime

from pydantic import BaseModel


class ReviewUpsertRequest(BaseModel):
    score: int
    review: str | None = None


class ReviewResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    media_item_id: uuid.UUID
    score: int
    review: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
