---
feature: seans-backend
status: in-progress
updated: 2026-09-20
branch: feat/seans-backend
commits: (pending)
---

# Seans Backend — self-hosted media system

## Report

(empty — not yet delivered)

## [S1] Problem

Self-hosted media service: search movies/series (Kinopoisk), search torrents,
auto-download via workers to S3, stream via presigned URLs, synchronized
watch-party via WebSocket. This repo = backend + DB only. Clients and
worker-agents are separate projects; their protocols are specified here.

## [S2] Design

### Stack (fixed)

- Python 3.12, FastAPI, Pydantic v2 + pydantic-settings
- SQLAlchemy 2.0 async (asyncpg), Alembic (sync driver psycopg2-binary)
- PostgreSQL 16 (docker)
- boto3 for S3 (Reg.ru S3, endpoint https://s3.regru.cloud, bucket `seans`, path-style)
- JWT (pyjwt), passwords — passlib[bcrypt]
- Tests: pytest + pytest-asyncio + httpx ASGI
- No Redis/Celery/RabbitMQ — queue in PostgreSQL via SELECT ... FOR UPDATE SKIP LOCKED
- Package manager: **uv** (pyproject.toml + uv.lock)
- Code, identifiers, docstrings — English; README — Russian

### Database schema

11 tables: users, workers, media_items, torrent_releases, tasks, task_files,
library_items, watch_history, reviews, rooms, room_members.

Full DDL in user's master spec (§ Schema).

### REST API

8 route modules: auth, media, tasks, library, history, reviews, rooms, worker.

Auth: Bearer JWT for users, X-Worker-Token for workers.

Full endpoint contracts in user's master spec (§ REST API).

### WebSocket (rooms)

In-memory room state, messages: join/heartbeat/state/sync_request/leave.
Host controls play/pause/seek; host-leave promotes first guest.

Full protocol in user's master spec (§ WebSocket).

### Services

- S3: boto3 client with path-style, presign_get (24h), presign_put (6h), head
- Quota: used (uploaded task_files) + reserved (active tasks) vs user quota
- Task queue: claim via FOR UPDATE SKIP LOCKED, lease with expiry
- Kinopoisk: KP_API_TOKEN provider or mock fixtures
- Indexer: mock (deterministic fixtures) or Jackett (Torznab XML)
- Quality parser: regex extraction of resolution/source/voiceover from titles
- Rooms: in-memory dict, broadcast, host promotion
- Reaper: asyncio background task, 60s cycle, reclaims expired leases

### Docker Compose (dev)

3 services: db (postgres:16-alpine), backend (build + alembic + uvicorn),
adminer. Single uvicorn worker (in-memory WS state).

### Milestones

| # | Scope | Acceptance |
|---|-------|------------|
| M1 | Repo skeleton, docker-compose, Dockerfile, healthcheck | `make up` + `curl localhost:8000/healthz` |
| M2 | SQLAlchemy models, Alembic migration, seed script | `make migrate` creates tables, seed idempotent |
| M3 | Auth: register/login/me, bcrypt, JWT | test_auth.py green |
| M4 | S3 service + presign + dev check endpoint | s3-check works against real bucket |
| M5 | Kinopoisk provider + cache + /api/search, /api/media/{id} | Search returns results, cached on repeat |
| M6 | Indexer (mock+jackett) + quality.py + /api/media/{id}/releases | Quality parser tests; mock releases work |
| M7 | Tasks + worker protocol + reaper + quota + library + files/url | test_tasks_flow.py full cycle including lease expiry |
| M8 | Rooms WS + history + reviews | test_rooms_ws.py two clients, host commands, promotion |

## [S3] Out of Scope

- Frontend, desktop client, real worker with qBittorrent
- Transcoding, HLS, ffmpeg
- Redis, RabbitMQ, Celery, Docker Swarm, k8s
- Multipart upload (MVP)
- Auto-selection of "best" torrent
- Secrets in code — only via settings from .env

## Tasks

### M1 — Skeleton
- [x] T1.1: Create project structure (pyproject.toml, uv.lock, Makefile, .env.example, .gitignore) — acceptance: `uv sync` installs deps (covers: S2 stack)
- [x] T1.2: Write Dockerfile (python:3.12-slim + uv) — acceptance: `docker build .` succeeds (covers: S2 stack)
- [x] T1.3: Write docker-compose.yml (db, backend, adminer) — acceptance: `make up` starts all 3 services (covers: S2 docker)
- [x] T1.4: Write app/main.py with GET /healthz, CORS, lifespan stub — acceptance: `curl localhost:8000/healthz` returns `{"status":"ok"}` (covers: S2 API)
- [x] T1.5: Write app/config.py with pydantic-settings — acceptance: settings load from .env (covers: S2 stack)
- [x] T1.6: Write app/db.py with async engine + Base — acceptance: import succeeds (covers: S2 stack)
- [x] T1.7: Write README.md (Russian, how to run) — acceptance: file exists (covers: S2)

### M2 — Models + Migration + Seed
- [x] T2.1: Write all SQLAlchemy models (11 tables) — acceptance: import succeeds, all models present (covers: S2 schema)
- [x] T2.2: Configure Alembic (alembic.ini, env.py) — acceptance: `alembic init` configured (covers: S2 schema)
- [x] T2.3: Generate initial migration — acceptance: `alembic upgrade head` creates all tables (covers: S2 schema)
- [x] T2.4: Write scripts/seed.py (demo user + 3 media_items) — acceptance: idempotent, creates demo@seans.local (covers: S2 schema)

### M3 — Auth
- [x] T3.1: Write auth schemas (RegisterRequest, LoginResponse, UserResponse) — acceptance: schemas validate correctly (covers: S2 API)
- [x] T3.2: Write auth service (register, login, verify_token) — acceptance: unit logic works (covers: S2 API)
- [x] T3.3: Write auth router (/api/auth/register, /login, /me) — acceptance: endpoints respond (covers: S2 API)
- [x] T3.4: Write test_auth.py — acceptance: tests green (covers: S2 API)

### M4 — S3
- [x] T4.1: Write S3 service (boto3 client, presign_get, presign_put, head) — acceptance: imports succeed (covers: S2 services)
- [x] T4.2: Write /api/dev/s3-check endpoint (dev only) — acceptance: roundtrip PUT+GET+DELETE against real bucket (covers: S2 services)

### M5 — Kinopoisk + Search
- [x] T5.1: Write Kinopoisk provider (real API + mock fallback) — acceptance: mock returns fixtures without token (covers: S2 services)
- [x] T5.2: Write /api/search endpoint with upsert cache — acceptance: search caches in media_items (covers: S2 API)
- [x] T5.3: Write /api/media/{id} endpoint — acceptance: returns full record + user review (covers: S2 API)

### M6 — Indexer + Quality
- [x] T6.1: Write quality.py parser (resolution, source, voiceover) — acceptance: unit tests pass (covers: S2 services)
- [x] T6.2: Write IndexerProvider (mock + Jackett) — acceptance: mock returns deterministic fixtures (covers: S2 services)
- [x] T6.3: Write /api/media/{id}/releases endpoint — acceptance: returns releases, respects 6h cache (covers: S2 API)

### M7 — Tasks + Worker + Core
- [x] T7.1: Write task queue service (claim, reaper logic) — acceptance: SKIP LOCKED claim works (covers: S2 services)
- [x] T7.2: Write quota service (used, reserved, check) — acceptance: correct calculation (covers: S2 services)
- [x] T7.3: Write task schemas — acceptance: schemas validate (covers: S2 API)
- [x] T7.4: Write task router (POST /tasks, GET /tasks, POST /tasks/{id}/cancel) — acceptance: endpoints work (covers: S2 API)
- [x] T7.5: Write worker router (register, claim, manifest, heartbeat, complete, fail) — acceptance: full protocol (covers: S2 API)
- [x] T7.6: Write library router (GET /library, GET /files/{id}/url) — acceptance: lists library, presigned URL (covers: S2 API)
- [x] T7.7: Write reaper background task — acceptance: reclaims expired leases (covers: S2 services)
- [x] T7.8: Write scripts/fake_worker.py — acceptance: completes full cycle claim→manifest→heartbeat→complete (covers: S2)
- [x] T7.9: Write test_tasks_flow.py — acceptance: tests green, covers lease expiry + quota exceeded (covers: S2 API)

### M8 — Rooms + History + Reviews
- [x] T8.1: Write rooms service (in-memory state, broadcast) — acceptance: room create/join/leave works (covers: S2 services)
- [x] T8.2: Write rooms router (POST /rooms, GET /rooms/{code}) — acceptance: endpoints work (covers: S2 API)
- [x] T8.3: Write WebSocket handler (/ws/rooms/{code}) — acceptance: connect, join, play/pause/seek broadcast (covers: S2 WebSocket)
- [x] T8.4: Write history router (PUT /history, GET /history) — acceptance: upsert + continue watching (covers: S2 API)
- [x] T8.5: Write reviews router (PUT /review, GET /reviews) — acceptance: upsert + list (covers: S2 API)
- [x] T8.6: Write test_rooms_ws.py — acceptance: tests green, two clients, host promotion (covers: S2 WebSocket)