---
feature: task-tmdb-id-resolution
status: designed
updated: 2026-09-22
branch: feat/tmdb-id-resolution
commits: # leave empty while in progress; fill at delivery
---

# tmdb_id + TMDB резолв

## Report

## [S1] Problem
TheIntroDB (внешний сервис глав/опенингов) идентифицирует медиа по **TMDB ID**.
В Seans хранится только `kp_id` (Кинопоиск). Нужно, чтобы каждый MediaItem
имел `tmdb_id` (nullable), и чтобы он автоматически резолвился при импорте.

## [S2] Design

### Модель
`app/models/media_item.py`: поле `tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)`.
**Не** делать unique constraint — один и тот же фильм может прийти через
разные kp_id (дубли KP). Unique остаётся только у `kp_id`.
Index нужен для будущих JOIN/поисков по `tmdb_id`.

### Миграция
`alembic revision --autogenerate -m "add tmdb_id to media_items"`
или ручная `003` в стиле 001/002: `ALTER TABLE media_items ADD COLUMN tmdb_id INTEGER NULL;`
+ `CREATE INDEX ix_media_items_tmdb_id ON media_items (tmdb_id);`

### Настройки
`app/config.py`: `TMDB_API_TOKEN: str = ""` (v3 API-ключ с themoviedb.org).
`.env.example`: строка `TMDB_API_TOKEN=`.

### TMDB-сервис
Новый `app/services/tmdb.py`. Один публичный метод:

```python
async def resolve_tmdb_id(
    title: str,
    original_title: str | None,
    year: int | None,
    kp_type: str,  # "movie" | "tv"
) -> int | None
```

Логика:
1. Если `TMDB_API_TOKEN` пустой → вернуть `None` (mock-режим, как в kinopoisk.py).
2. Endpoint:
   - `kp_type == "movie"` → `GET /3/search/movie?query={original_title or title}&year={year}`
   - `kp_type == "tv"` → `GET /3/search/tv?query={original_title or title}&first_air_date_year={year}`
3. Искать по `original_title` первым (точнее для TMDB), fallback на `title`.
4. Из ответа взять `results[0]["id"]` (первый результат; TMDB отдаёт по popularity).
5. Если results пустой → попробовать второй вариант запроса (title если original_title не дал результатов, или наоборот; пропускать None/пустые и дубли).
6. Любой exception (timeout, 4xx, 5xx) → `logger.warning` + вернуть `None`.
   **Никогда не блокировать upsert из-за ошибки TMDB.**

Endpoint: `https://api.themoviedb.org/3` · Auth: `api_key=<token>` query param (TMDB v3).
Таймаут: 5 секунд. `httpx.AsyncClient` с `timeout=5`.
`language=en-US` для поиска.

### Интеграция в upsert
`app/services/kinopoisk.py` → `upsert_media_items`: **после** успешного upsert
`await db.commit()`, если у полученного `MediaItem` `tmdb_id is None`:

```python
media_item = row.scalar_one()
if media_item.tmdb_id is None:
    tmdb_id = await resolve_tmdb_id(
        title=media_item.title,
        original_title=media_item.original_title,
        year=media_item.year,
        kp_type=media_item.kp_type,
    )
    if tmdb_id is not None:
        media_item.tmdb_id = tmdb_id
        await db.commit()
```

`resolve_tmdb_id` вызывается **после** upsert и **не** входит в транзакцию upsert.
Если TMDB упал — upsert всё равно прошёл, `tmdb_id` остаётся null.

### Схемы и API
`app/schemas/media.py`: `tmdb_id: int | None = None` после `kp_id` в
`MediaSearchResult` и `MediaDetail`.

`app/routers/library.py`: в `GET /api/library` объект `media_item` — поле `"tmdb_id": media_item.tmdb_id`.

### Mock-фикстуры
`MOCK_FIXTURES` в `kinopoisk.py` + (при необходимости seed) — реальные TMDB ID:
- `kp_id: 11154872` → `tmdb_id: 378527` — Токийский гуль (2017)
- `kp_id: 258687` → `tmdb_id: 157336` — Интерстеллар (2014)
- `kp_id: 464963` → `tmdb_id: 1399` — Игра престолов (2011)

ID вставить в значения upsert (insert `values(...)` уже разворачивает item).
**Не** класть `tmdb_id` в `on_conflict_do_update.set_` из `item.get()` — это
затёрло бы уже разрешённые id при повторном upsert реальных KP-результатов.

### Тесты
Unit `tests/test_tmdb.py` (мок httpx / settings):
- `test_resolve_tmdb_id_movie`
- `test_resolve_tmdb_id_tv`
- `test_resolve_tmdb_id_empty_token` → `None`
- `test_resolve_tmdb_id_no_results` → `None`
- `test_resolve_tmdb_id_http_error` → `None`, не падает
- `test_resolve_tmdb_id_prefers_original_title` — original_title даёт результат; title не вызывается

Integration (мок TMDB + upsert):
- `test_upsert_resolves_tmdb_id` — после upsert `media_item.tmdb_id` заполнен
- `test_upsert_skips_tmdb_when_no_token` — без `TMDB_API_TOKEN` → `tmdb_id is None`

## [S3] Out of Scope
- Background-батч для резолва существующих записей с null `tmdb_id`.
- Worker-эндпоинты (worker не резолвит `tmdb_id`).
- Unique constraint на `tmdb_id` (дубликаты KP допустимы).
- TMDB API v4 (используем v3, query-param auth).

## Tasks
- [ ] T1: Модель MediaItem.tmdb_id + миграция 003 — acceptance: колонка nullable + index; `alembic upgrade head` проходит (covers: S2)
- [ ] T2: config TMDB_API_TOKEN + .env.example — acceptance: поле есть в Settings и .env.example (covers: S2; depends: T1)
- [ ] T3: app/services/tmdb.py + unit-тесты — acceptance: 6 unit-тестов зелёные; ошибки API не роняют resolve (covers: S2; depends: T2)
- [ ] T4: upsert-интеграция + MOCK_FIXTURES.tmdb_id — acceptance: после upsert при token/mocks tmdb_id заполнен; без token остаётся None (covers: S2; depends: T3)
- [ ] T5: schemas media + library router — acceptance: tmdb_id в MediaSearchResult/MediaDetail и в ответе GET /api/library (covers: S2; depends: T4)
- [ ] T6: Verification — acceptance: pytest + ruff + миграция; ручной/локальный search содержит tmdb_id при mock fixtures (covers: S2; depends: T5)
