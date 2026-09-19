import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.media_item import MediaItem
from app.models.torrent_release import TorrentRelease
from app.schemas.media import MediaDetail, MediaSearchResult
from app.schemas.releases import TorrentReleaseResponse
from app.services.indexer import get_indexer
from app.services.kinopoisk import search_kinopoisk, upsert_media_items

router = APIRouter(tags=["media"])


@router.get("/api/search", response_model=list[MediaSearchResult])
async def search(q: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)):
    items = await search_kinopoisk(q)
    if not items:
        return []
    media_items = await upsert_media_items(db, items)
    return [MediaSearchResult.model_validate(m) for m in media_items]


@router.get("/api/media/{media_item_id}", response_model=MediaDetail)
async def get_media(media_item_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MediaItem).where(MediaItem.id == media_item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found"
        )
    return MediaDetail.model_validate(item)


@router.get(
    "/api/media/{media_item_id}/releases", response_model=list[TorrentReleaseResponse]
)
async def get_releases(
    media_item_id: str,
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
):
    # Verify media item exists
    result = await db.execute(select(MediaItem).where(MediaItem.id == media_item_id))
    media_item = result.scalar_one_or_none()
    if media_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found"
        )

    # Check cache (6h freshness)
    if not refresh:
        cutoff = datetime.now(UTC) - timedelta(hours=6)
        cached = await db.execute(
            select(TorrentRelease)
            .where(TorrentRelease.media_item_id == media_item_id)
            .where(TorrentRelease.fetched_at > cutoff)
        )
        rows = cached.scalars().all()
        if rows:
            return [TorrentReleaseResponse.model_validate(r) for r in rows]

    # Fetch from indexer
    indexer = get_indexer()
    query = f"{media_item.title} {media_item.year or ''}".strip()
    releases = await indexer.search(query, str(media_item_id))

    # Upsert into DB
    db_releases = []
    for rel in releases:
        stmt = (
            pg_insert(TorrentRelease)
            .values(
                id=uuid.uuid4(),
                media_item_id=media_item_id,
                source=rel.source,
                tracker=rel.tracker,
                title=rel.title,
                info_hash=rel.info_hash,
                size_bytes=rel.size_bytes,
                seeders=rel.seeders,
                leechers=rel.leechers,
                quality=rel.quality,
                voiceover=rel.voiceover,
                magnet=rel.magnet,
            )
            .on_conflict_do_update(
                index_elements=["media_item_id", "info_hash"],
                set_={
                    "seeders": rel.seeders,
                    "leechers": rel.leechers,
                    "fetched_at": "now()",
                },
            )
            .returning(TorrentRelease)
        )
        row = await db.execute(stmt)
        db_releases.append(row.scalar_one())

    await db.commit()
    return [TorrentReleaseResponse.model_validate(r) for r in db_releases]
