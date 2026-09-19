import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MediaSearchResult(BaseModel):
    id: uuid.UUID
    kp_id: int | None
    title: str
    year: int | None
    poster_url: str | None
    kp_type: str
    rating_kp: Decimal | None

    model_config = {"from_attributes": True}


class MediaDetail(BaseModel):
    id: uuid.UUID
    kp_id: int | None
    kp_type: str
    title: str
    original_title: str | None
    year: int | None
    poster_url: str | None
    overview: str | None
    rating_kp: Decimal | None
    genres: list[str]
    updated_at: datetime

    model_config = {"from_attributes": True}
