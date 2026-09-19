import logging
import uuid
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.media_item import MediaItem

logger = logging.getLogger(__name__)

KP_API_BASE = "https://kinopoiskapiunofficial.tech/api/v2.1"

MOCK_FIXTURES: list[dict[str, Any]] = [
    {
        "kp_id": 11154872,
        "kp_type": "movie",
        "title": "Токийский гуль",
        "original_title": "Tokyo Ghoul",
        "year": 2017,
        "poster_url": "https://st.kp.yandex.net/images/film_iphone/iphone360_11154872.jpg",
        "overview": "Студент Канеки попадает в мир гулей.",
        "rating_kp": 6.4,
        "genres": ["ужасы", "боевик"],
    },
    {
        "kp_id": 258687,
        "kp_type": "movie",
        "title": "Интерстеллар",
        "original_title": "Interstellar",
        "year": 2014,
        "poster_url": "https://st.kp.yandex.net/images/film_iphone/iphone360_258687.jpg",
        "overview": "Космическая экспедиция через червоточину.",
        "rating_kp": 8.6,
        "genres": ["фантастика", "драма"],
    },
    {
        "kp_id": 464963,
        "kp_type": "tv",
        "title": "Игра престолов",
        "original_title": "Game of Thrones",
        "year": 2011,
        "poster_url": "https://st.kp.yandex.net/images/film_iphone/iphone360_464963.jpg",
        "overview": "Благородные дома Вестероса борются за трон.",
        "rating_kp": 8.7,
        "genres": ["фэнтези", "драма"],
    },
]


async def search_mock(query: str) -> list[dict[str, Any]]:
    q = query.lower()
    return [
        f
        for f in MOCK_FIXTURES
        if q in f["title"].lower() or q in (f.get("original_title") or "").lower()
    ]


async def search_kinopoisk(query: str) -> list[dict[str, Any]]:
    if not settings.KP_API_TOKEN:
        logger.info("KP_API_TOKEN not set, using mock provider")
        return await search_mock(query)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{KP_API_BASE}/films/search-by-keyword",
            params={"keyword": query, "page": 1},
            headers={"X-API-KEY": settings.KP_API_TOKEN},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("films", []):
        kp_type = "tv" if item.get("type") == "TV_SERIES" else "movie"
        results.append(
            {
                "kp_id": item.get("filmId"),
                "kp_type": kp_type,
                "title": item.get("nameRu") or item.get("nameEn") or "",
                "original_title": item.get("nameEn"),
                "year": int(item["year"])
                if item.get("year") and str(item["year"]).isdigit()
                else None,
                "poster_url": item.get("posterUrl"),
                "overview": item.get("description", ""),
                "rating_kp": float(item["rating"]) if item.get("rating") else None,
                "genres": [
                    g["genre"] for g in item.get("genres", []) if g.get("genre")
                ],
            }
        )
    return results


async def upsert_media_items(
    db: AsyncSession, items: list[dict[str, Any]]
) -> list[MediaItem]:
    """Upsert media items by kp_id, return ORM objects."""
    result = []
    for item in items:
        stmt = (
            pg_insert(MediaItem)
            .values(
                id=uuid.uuid4(),
                raw=item,
                **{k: v for k, v in item.items() if k != "raw"},
            )
            .on_conflict_do_update(
                index_elements=["kp_id"],
                set_={
                    "title": item["title"],
                    "original_title": item.get("original_title"),
                    "year": item.get("year"),
                    "poster_url": item.get("poster_url"),
                    "overview": item.get("overview"),
                    "rating_kp": item.get("rating_kp"),
                    "genres": item.get("genres", []),
                    "raw": item,
                    "updated_at": "now()",
                },
            )
            .returning(MediaItem)
        )
        row = await db.execute(stmt)
        result.append(row.scalar_one())
    await db.commit()
    return result
