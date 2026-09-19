import uuid

from pydantic import BaseModel


class TorrentReleaseResponse(BaseModel):
    id: uuid.UUID
    tracker: str
    title: str
    size_bytes: int
    seeders: int
    leechers: int
    quality: str | None
    voiceover: str | None
    magnet: str | None

    model_config = {"from_attributes": True}
