---
feature: arr-stack
status: delivered
updated: 2026-10-08
branch: feat/arr-stack
commits: 0916176..3d2afb3
---

# arr-stack — Sonarr / Radarr / Bazarr + интеграция

## Report

**What was built** — В compose добавлены Sonarr, Radarr и Bazarr (linuxserver,
shared `arr_data`, без серверного qBittorrent) и Caddy-хосты
sonarr/radarr/bazarr.seans.tedeshi.ru. Локальный JacRed остаётся для
backend-releases; в Sonarr/Radarr как Torznab-индексатор прописан внешний
JacRed `https://api.jacred.su/torznab` (TV/Anime для Sonarr, Movies для
Radarr). Гайд `docs/arr-setup.md` описывает скачивание через **удалённый
qBittorrent на машинах воркеров** (Web API) и заливку в S3 агентом воркера —
без общего filesystem с root folders *arr.

Бекенд отдаёт каталог `/api/arr/series|movies|episodes` (JWT, `?refresh=true`)
через `app/services/arr.py` + process-local `TTLCache` (300s / 1800s для
эпизодов). Сырой JSON Servarr v3 маппится в DTO; 503 без настроек, 502 на
upstream, 404 через `ArrNotFound`. Очередь/hasFile из *arr и смена
worker-протокола — вне скоупа; гибкость озвучек/quality/офлайн описана в
`media-flexibility.md` (status: designed).

**Verification** — `pytest tests/test_arr.py tests/test_arr_cache.py tests/test_arr_router.py -q`: 20 passed. `ruff check app/ tests/`: PASS. `docker compose config --services`: sonarr, radarr, bazarr присутствуют; qbittorrent в compose отсутствует. Полный `pytest tests/` с БД не гонялся (PRE-EXISTING: host `db` / нет docker PostgreSQL на хосте). Ревью: critical «нет router-тестов» закрыт (`test_arr_router.py`); re-review PASS.

**Journey log**
1. `git worktree add` заблокирован сессией — ветка `feat/arr-stack` в текущем checkout (база `production` / 0916176).
2. Первичная спека ошибочно считала воркер sidecar'ом («читает /data/complete»). Уточнение: воркеры — отдельные машины, mount `/data` нет; qBittorrent живёт **на воркере**, *arr шлёт grab через Web API, S3 — presigned PUT с воркера.
3. Серверный qBittorrent убран из compose: без общего FS с *arr он не даёт import в root folders.
4. ArrNotFound нельзя кидать внутри `except httpx.HTTPError` при mock'е httpx (TypeError на except-clause) — 404 проверяется после try.
5. Bazarr на сервере не видит файлы воркеров/S3 — в гайде три варианта (роль subtitle / sync / Bazarr на воркере); UI остаётся для провайдеров.

## [S1] Problem

В Seans нет сервисов агрегации медиатеки (сериалы/фильмы/субтитры). Нужно
поднять Sonarr, Radarr и Bazarr с субдоменами в Caddy, нормально их
настроить (индексатор — внешний JacRed от разработчиков), автоматизировать
поиск и загрузку через qBittorrent, и научить бекенд отдавать каталог
(*arr) клиентам — без частых походов в *arr API (кеш в оперативной памяти).

## [S2] Design

### 2.1 Внешний JacRed (Torznab) — контракт индексатора

Используется **только** в UI Sonarr/Radarr как Torznab-индексатор.
Локальный `jacred` в compose **остаётся как есть** (его продолжает
использовать backend `/api/media/{id}/releases`).

| Поле | Значение |
|------|----------|
| Torznab URL | `https://api.jacred.su/torznab` |
| API Path | `/api` (дефолт Torznab) |
| API Key | `jrs_oywj48MR1kOoq2ZdRupofyswAtVx541MZexccaD4hts` |

Категории:
- **Sonarr** — TV / Anime: `5000, 5030, 5040, 5070` (TV, TV/WEB-DL, TV/HD, TV/Anime)
- **Radarr** — Movies: `2000, 2010, 2020, 2030, 2040, 2050`

### 2.2 Docker Compose

Новые сервисы (linuxserver.io, PUID/PGID `1000:1000`, TZ `Europe/Moscow`):

| Сервис | Образ | Порт (internal) | Config volume | Data |
|--------|-------|-----------------|---------------|------|
| `sonarr` | `lscr.io/linuxserver/sonarr:latest` | 8989 | `sonarr_config:/config` | `arr_data:/data` |
| `radarr` | `lscr.io/linuxserver/radarr:latest` | 7878 | `radarr_config:/config` | `arr_data:/data` |
| `bazarr` | `lscr.io/linuxserver/bazarr:latest` | 6767 | `bazarr_config:/config` | `arr_data:/data` |

- Host-порты *arr **не** публикуются — только через Caddy.
- Named volumes: `sonarr_config`, `radarr_config`, `bazarr_config`, `arr_data`.
- **qBittorrent НЕ на сервере.** Download clients = **удалённые** qBittorrent
  на машинах воркеров (Web API). Образ `lscr.io/linuxserver/qbittorrent`
  в compose для сервера не нужен.
- `caddy` depends_on дополняется новыми сервисами.
- Существующие `db`, `backend`, `adminer`, `jacred`, `frontend` не трогаем.

### 2.3 Топология загрузок (важно)

**Воркеры — отдельные UNIT'ы на других компьютерах.** У них нет mount
`/data` сервера и нет доступа к root folders *arr. Воркер сливает файлы
в S3 по HTTPS (presigned PUT), а не «читает completed» на сервере.

```
[сервер compose]                         [машина воркера]
Sonarr / Radarr                          qBittorrent (Web API)
  │  JacRed (api.jacred.su/torznab)      │
  │  «что хотим скачать»                 │  save path: своя папка
  └────────── add torrent ──────────────►│
                                         │  completed
[сервер compose]                         │
backend /api/arr/*  ◄── HTTP ── *arr     │  агент воркера
каталог в RAM-кеше                       └──── presigned PUT ──► S3
```

- *arr → qBittorrent: **Web API на хосте воркера** (Settings → Download
  Clients → qBittorrent, host = адрес воркера).
- Файл физически создаётся **на диске воркера**.
- Агент воркера (расширение существующего worker-протокола) снимает
  completed из **своего** qBittorrent и заливает в S3.
- Root folders *arr (`/data/media/...`) — **каталожная запись** для
  добавления сериалов/фильмов в UI; воркеры туда не ходят. Импорт
  «download dir → root» через общий FS не используется (remote path
  mapping не требуется, import в S3 идёт мимо *arr).

Пути `/data/...` на сервере — только для будущего server-side импортёра
и для локальной разработки. Это **не** handoff-каталог для воркеров.

### 2.4 Caddy

```
sonarr.seans.tedeshi.ru    → sonarr:8989
radarr.seans.tedeshi.ru    → radarr:7878
bazarr.seans.tedeshi.ru    → bazarr:6767
```

Без блока для qBittorrent (только внутренняя сеть; при необходимости —
отдельной задачей).

### 2.5 Настройка сервисов (гайд `docs/arr-setup.md`)

Отдельные секции: Sonarr, Radarr, Bazarr, **удалённый qBittorrent на
воркере**, JacRed-индексатор, связка *arr ↔ Bazarr, API keys, root folders,
quality profiles, tags, permissions.

Ключевые шаги (полное расписание в гайде):
1. Поднять compose, открыть UI по субдоменам.
2. Взять API keys из *arr Settings → General.
3. На машине воркера: qBittorrent Web API (user/pass или API key), save path
   — локальная папка воркера.
4. Sonarr/Radarr → Download Clients → qBittorrent **на воркере**
   (`host:8080`, категория `seans`).
5. Sonarr/Radarr → Indexers → Torznab (JacRed) — URL/API key/категории выше.
6. Root folders: `/data/media/tv`, `/data/media/movies` (каталог *arr;
   файлы в S3 с воркеров).
7. Bazarr → Sonarr/Radarr (URL + API keys). Субтитры — см. оговорку ниже.
8. Backend `.env`: `SONARR_URL`, `SONARR_API_KEY`, `RADARR_URL`, `RADARR_API_KEY`.

**Bazarr и файлы.** Bazarr по умолчанию читает media с диска рядом с
Sonarr/Radarr. Если видео лежат только на дисках воркеров / в S3, Bazarr
**не увидит** их для встраивания субтитров. Варианты (в гайде): (a) субтитры
через seans/роль `subtitle` из media-flexibility; (b) временный sync на
сервер только для Bazarr; (c) Bazarr на машине воркера. UI Bazarr на
bazarr.seans.tedeshi.ru остаётся для настройки провайдеров/языков.

### 2.6 Backend: клиенты *arr + in-memory cache

**Конфиг** (`app/config.py`, `.env.example`):

```
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=
RADARR_URL=http://radarr:7878
RADARR_API_KEY=
ARR_CACHE_TTL_SECONDS=300
ARR_EPISODE_CACHE_TTL_SECONDS=1800
```

**`app/services/arr_cache.py`** — процессный TTL-кеш (dict, `time.monotonic`),
в одном стиле с `rooms.py` (single uvicorn worker). Не Redis.
- `get_or_set(key, ttl, factory)` — miss → factory → store
- `invalidate(prefix=None)` — очистка (для тестов / refresh)
- ключи: `arr:series:list`, `arr:series:{id}`, `arr:series:{id}:episodes`,
  `arr:movies:list`, `arr:movies:{id}`

**`app/services/arr.py`** — httpx-клиенты к Servarr API v3:
- `get_series() -> list[ArrSeries]`
- `get_series_detail(sonarr_id) -> ArrSeries`
- `get_episodes(sonarr_id) -> list[ArrEpisode]`
- `get_movies() -> list[ArrMovie]`
- `get_movie(radarr_id) -> ArrMovie`
- Auth: header `X-Api-Key`
- Timeout 10s; ошибки → `ArrError` (router мапит в 502/504)
- Пустой `SONARR_URL`/`SONARR_API_KEY` → сервис считается не настроенным
  (endpoint'ы → 503), чтобы dev без *arr не падал

Маппинг raw JSON → DTO (Pydantic), raw-поля *arr наружу не отдаём.

**Схемы** (`app/schemas/arr.py`):

```python
class ArrSeason(BaseModel):
    season_number: int
    monitored: bool
    episode_count: int
    episode_file_count: int

class ArrSeries(BaseModel):
    id: int
    title: str
    year: int | None
    status: str            # continuing | upcoming | ended
    overview: str | None
    poster_url: str | None
    network: str | None
    tvdb_id: int | None
    path: str | None
    seasons: list[ArrSeason]

class ArrEpisode(BaseModel):
    id: int
    season_number: int
    episode_number: int
    title: str | None
    overview: str | None
    air_date: str | None
    has_file: bool
    monitored: bool

class ArrMovie(BaseModel):
    id: int
    title: str
    year: int | None
    overview: str | None
    poster_url: str | None
    status: str
    has_file: bool
    monitored: bool
    tmdb_id: int | None
    path: str | None
```

**Роутер** (`app/routers/arr.py`, prefix `/api/arr`, JWT как в media):

| Метод | Путь | Кеш | TTL |
|-------|------|-----|-----|
| GET | `/series` | list | 300s |
| GET | `/series/{sonarr_id}` | detail | 300s |
| GET | `/series/{sonarr_id}/episodes` | episodes | 1800s |
| GET | `/movies` | list | 300s |
| GET | `/movies/{radarr_id}` | detail | 300s |

- `?refresh=true` — bypass кеша, запись заново.
- 404 если id нет в *arr; 503 если *arr не сконфигурирован; 502 при
  ошибке соединения.
- Регистрация в `app/main.py`.

**Тесты** (`tests/test_arr_cache.py`, `tests/test_arr.py`):
- cache: hit / miss / expiry / refresh / invalidate
- mapper: series, episodes, movies (фикстуры raw JSON)
- router: 200 + cache hit, refresh=true бьёт в factory, 404, 503 без настроек
- unit-тесты без сети (factory подменяется)

### 2.7 Текущий JacRed-флоу в backend

`app/services/indexer.py` и `/api/media/{id}/releases` **не меняются** —
работают от локального `JACRED_URL`. Это отдельный канал релизов для
seans-воркеров.

## [S3] Out of Scope

- Раздельные аудио/видео-дорожки, multi-quality watch-party, офлайн без
  квоты — см. `docs/compose/spec/media-flexibility.md`
- Перенос backend-релизов с локального JacRed на внешний `api.jacred.su`
- Изменение worker-протокола (magnet → qBit-on-worker → S3) и агента
  снятия completed с воркера — контракт в media-flexibility / отдельной задаче
- Синхронизация каталога *arr в таблицу `media_items`
- Download queue/history из *arr, *arr write API (add series/movie)
- Bazarr REST-интеграция в backend (только UI-настройка)
- qBittorrent в Caddy / публичный доступ
- Server-side s3-importer (если qBittorrent позже будет и на сервере)
- Redis или иной распределённый кеш (in-memory, single worker)
- Прокси-сервер / VPN для трекеров

## Tasks

- [x] T1: docker-compose.yml — сервисы sonarr/radarr/bazarr (без серверного qbittorrent), volumes arr_data, depends_on caddy — acceptance: `docker compose config` валиден, сервисы видны, qbittorrent отсутствует (covers: S2.2, S2.3)
- [x] T2: Caddyfile — блоки sonarr/radarr/bazarr — acceptance: три хоста с reverse_proxy на верные порты (covers: S2.4)
- [x] T3: config + .env.example — SONARR_*/RADARR_*/ARR_CACHE_* — acceptance: Settings.load не падает, env-ключи на месте (covers: S2.6)
- [x] T4: app/services/arr_cache.py — TTLCache — acceptance: тесты hit/miss/expiry/invalidate зелёные (covers: S2.6)
- [x] T5: app/schemas/arr.py + app/services/arr.py — DTO, httpx-клиенты, маппинг — acceptance: unit-тесты маппинга и «не настроено» зелёные (covers: S2.6)
- [x] T6: app/routers/arr.py + регистрация в main — acceptance: тесты роутера (200/404/503/refresh) зелёные (covers: S2.6)
- [x] T7: docs/arr-setup.md — гайды Sonarr/Radarr/Bazarr/qBittorrent/JacRed/связки — acceptance: все шаги из S2.5 расписаны, пути S2.3 и API key источники указаны (covers: S2.1, S2.5)
- [x] T8: verify — pytest + ruff — acceptance: новые тесты PASS, lint без новых ошибок (covers: S2.6)
- [x] T9: (изолировано) media-flexibility spec — acceptance: `docs/compose/spec/media-flexibility.md` описывает роли файлов, парные задания video/audio, watch-party варианты, offline storage=local (covers: media-flexibility S2)
