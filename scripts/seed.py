"""Seed demo data: demo user + 3 media items. Idempotent."""

import asyncio
import uuid

from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import async_session, engine
from app.models import MediaItem, User

DEMO_EMAIL = "demo@seans.local"
DEMO_PASSWORD = "demo12345"

MEDIA_FIXTURES = [
    {
        "kp_id": 11154872,
        "kp_type": "movie",
        "title": "Токийский гуль",
        "original_title": "Tokyo Ghoul",
        "year": 2017,
        "poster_url": "https://st.kp.yandex.net/images/film_iphone/iphone360_11154872.jpg",
        "overview": "Студент Канеки попадает в мир гулей — существ, питающихся человеческой плотью.",
        "rating_kp": 6.4,
        "genres": ["ужасы", "боевик", "фэнтези"],
    },
    {
        "kp_id": 258687,
        "kp_type": "movie",
        "title": "Интерстеллар",
        "original_title": "Interstellar",
        "year": 2014,
        "poster_url": "https://st.kp.yandex.net/images/film_iphone/iphone360_258687.jpg",
        "overview": "Космическая экспедиция через червоточину в поисках нового дома для человечества.",
        "rating_kp": 8.6,
        "genres": ["фантастика", "драма", "приключения"],
    },
    {
        "kp_id": 464963,
        "kp_type": "tv",
        "title": "Игра престолов",
        "original_title": "Game of Thrones",
        "year": 2011,
        "poster_url": "https://st.kp.yandex.net/images/film_iphone/iphone360_464963.jpg",
        "overview": "Благородные дома Вестероса ведут борьбу за Железный трон.",
        "rating_kp": 8.7,
        "genres": ["фэнтези", "драма", "боевик"],
    },
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Demo user
        existing = await session.execute(select(User).where(User.email == DEMO_EMAIL))
        if not existing.scalar_one_or_none():
            session.add(
                User(
                    email=DEMO_EMAIL,
                    password_hash=bcrypt.hash(DEMO_PASSWORD),
                    display_name="Demo User",
                )
            )
            print(f"Created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"Demo user already exists: {DEMO_EMAIL}")

        # Media items (upsert by kp_id)
        for item in MEDIA_FIXTURES:
            stmt = (
                pg_insert(MediaItem)
                .values(id=uuid.uuid4(), **item, raw=item)
                .on_conflict_do_update(
                    index_elements=["kp_id"],
                    set_={"title": item["title"], "updated_at": "now()"},
                )
            )
            await session.execute(stmt)
        print(f"Upserted {len(MEDIA_FIXTURES)} media items")

        await session.commit()


if __name__ == "__main__":
    from app.db import Base

    asyncio.run(seed())
