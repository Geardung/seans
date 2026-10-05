---
feature: seans-client-app
status: designed
updated: 2026-09-20
branch: feat/seans-client-app
commits: 
---

# Seans Client App — native desktop player + full catalog

## Report

## [S1] Problem

Seans backend already streams media via presigned S3 URLs and hosts watch-party
rooms, but a browser is a bad player: codecs, subtitles, seeking, HW decode,
long sessions. Users need a **native client** that:

1. authenticates through the web (no password form in-app),
2. browses the full catalog parity with the web product,
3. plays **any** audio/video container the backend can store,
4. opens shared rooms via `seans://` deep links on the device,
5. updates itself often and almost seamlessly,
6. does **not** trip antivirus false positives (prior trauma: Go stack
   downloading DLLs at runtime → heuristics + paid EV cert).

Web stays for browsing/account, but **playback always happens in this client**.

## [S2] Design

### Stack (fixed)

| Layer | Choice | Why |
|-------|--------|-----|
| Shell | **Tauri 2** (Rust) | small binary, system WebView2, no packer, clean PE |
| UI | React + TypeScript + Vite | shared design system with future web |
| Player | **libmpv** (`libmpv-2.dll` sidecar) | decodes virtually everything natively |
| HTTP/WS | Rust `reqwest` + `tokio-tungstenite` via Tauri commands | token never in JS if we want; fine either way |
| Updates | `tauri-plugin-updater` + `tauri-plugin-process` | silent frequent releases |
| Deep links | `tauri-plugin-deep-link` | `seans://` protocol |
| Storage | `keyring` / Windows Credential Manager for JWT | no plaintext token files |

**Antivirus hygiene (hard rules):**

- No UPX / Themida / any runtime packer.
- No downloading DLLs, codecs, or scripts at first run. Everything ships in the
  installer / app bundle (`libmpv-2.dll`, ffmpeg-related mpv deps as sidecar).
- Stable VersionInfo (Company, ProductName, FileVersion, ProductVersion).
- Prefer Authenticode later; structure PE metadata for it from day one.
- Never inject, never spawn unsigned helpers from `%TEMP%`.
- Installer: NSIS or MSI via Tauri bundler. Portable build is a secondary artifact.

### Auth (web login → native session)

No password UI in the client. Flow:

1. Client generates `state` (random, PKCE-like single-use) and opens system browser:
   `https://seans.tedeshi.ru/auth?redirect_uri=seans%3A%2F%2Fauth%2Fcallback&state=<state>`
2. Web authenticates via existing `POST /api/auth/login` (or register with invite).
3. Web redirects: `seans://auth/callback?access_token=<JWT>&state=<state>&token_type=bearer`
4. Client validates `state`, stores JWT in OS keyring, calls `GET /api/auth/me`.
5. Manual logout clears keyring. 401 → re-run web login.

Interim fallback (only if auth page is not ready): local loopback
`http://127.0.0.1:<ephemeral>/callback` as `redirect_uri`. Prefer `seans://`.

### Deep links (one custom scheme)

| URL | Behavior |
|-----|----------|
| `seans://auth/callback?access_token=&state=` | finish login |
| `seans://room/{code}` | open room `{code}` (path-style; `code` is the 8-char A–Z/2–9 string) |
| `seans://` | focus app / home |

Windows: register protocol under `HKCU\Software\Classes\seans`.
Single-instance plugin: second launch forwards argv deep link to the first process.

### Player (native decode, no client re-encode)

- libmpv in-process, rendered into a Tauri panel (HWND / `raw-window-handle`).
- Source: `GET /api/files/{task_file_id}/url` → `{ "url": "...", "expires_in": 86400 }`.
- Prefer HW decode (D3D11 / dxva2 / nvdec). Soft decode fallback automatic.
- Support: mkv/mp4/avi/webm/mov, H.264/H.265/AV1/VP9, AAC/AC3/EAC3/TrueHD/FLAC/Opus,
  embedded + external subs (ASS/SSA/SRT), multi-audio tracks.
- On format mpv truly cannot open: surface a clear error + “report file”.
  Do **not** implement client-side ffmpeg transcoding in v1.
- Persist progress via `PUT /api/history` (every 15s + on pause/seek/close).
- Resume from history on open (unless room sync overrides).

### TheIntroDB integration (chapters, skip intro, credits popup)

Source: `GET https://api.theintrodb.org/v3/media?tmdb_id={id}&season={s}&episode={e}`

Returns per-media arrays of segment timestamps `{start_ms, end_ms}` for four
segment types: `intro`, `recap`, `credits`, `preview`. Null start = begins at 0;
null credits end = runs to end of file. Rate limit: 30 req/10s per IP, 1000
req/day (no API key for read-only).

**Backend dependency:** `MediaDetail` must carry `tmdb_id` (nullable integer).
Backend resolves tmdb_id during media import via TMDB API (search by title+year
or external_ids). Client passes `season`/`episode` for TV episodes (available
from file path in `TaskFile.season`/`TaskFile.episode`). If `tmdb_id` is null,
all TheIntroDB features are silently disabled for that item.

**Client behavior on play start:**

1. Read `tmdb_id` from `MediaDetail`.
2. Fetch TheIntroDB segments for the media (+ season/episode for TV).
3. Cache result in memory for the current session.

**Player UI features:**

- **Chapter markers on seek bar**: thin colored ticks at `start_ms` of each
  segment (intro=teal, recap=blue, credits=amber, preview=gray). Hovering a
  tick shows label + timestamp.
- **"Skip Intro" button**: a floating action appears when playback position is
  within `[intro.start_ms ?? 0, intro.end_ms]`. Click → seek to `intro.end_ms + 0.3s`.
  Same for recap ("Skip Recap"). Auto-hide 2s after leaving segment.
- **Credits popup**: when playback position ≥ `credits[0].start_ms` (first
  credits segment), show a modal overlay (does NOT pause playback):
  - Star rating 1–10 (single tap/select + submit)
  - Optional textarea for review text
  - "Позже" / close → dismiss, don't ask again this session
  - Submit → `PUT /api/media/{id}/review` with `{score, review}`
  - The popup appears once per media per session; not shown if user already
    reviewed this media (check `MediaDetail.user_review`).
- **Chapter list menu**: in player controls, "Chapters" dropdown lists all
  segments with type + timestamp. Click → seek to that segment's start.

**Room sync caveat:** in a room, TheIntroDB data is per-client (host and guests
fetch independently). The credits popup still appears for each viewer; skip-intro
is individual and not broadcast (host seeking past intro broadcasts naturally
via `state`).

OpenAPI: `https://api.theintrodb.org/v3/openapi.json` (full spec).

### Watch-party rooms

REST:

- `POST /api/rooms` body `{task_file_id}` → `{id, code, ws_url}` — host creates.
- `GET /api/rooms/{code}` → `{room, members:[{user_id}]}` (public-ish lookup).

WS: `GET /ws/rooms/{code}?token=<JWT>` (use `wss://` on prod).

Client → server:

```json
{"type":"join"}
{"type":"heartbeat","position":12.5}
{"type":"state","action":"play|pause|seek","position":12.5}
{"type":"sync_request"}
{"type":"leave"}
```

Server → client:

```json
{"type":"room_state","host_id":"<uuid>","position":12.5,"is_playing":true,"ts":0}
{"type":"state","action":"play|pause|seek","position":12.5,"by":"<uuid>"}
{"type":"member_joined","user":{"user_id":"...","name":"..."}}
{"type":"member_left","user":{"user_id":"...","name":"..."}}
{"type":"error","detail":"Only host can control playback"}
```

Rules: only host mutates playback (`state`); guests apply `state`/`room_state`
and send `heartbeat`; host leave → server promotes and broadcasts `room_state`.
Close WS code 4001 = unauthorized, 4004 = room not found.

Deep link `seans://room/{code}` joins as guest if not host.

### Updates (frequent, almost seamless)

- `tauri-plugin-updater` pointed at `https://seans.tedeshi.ru/desktop/latest.json`
  (or GitHub Releases `latest.json`).
- Check: on startup + every 6h + manual “Check for updates”.
- Download in background; apply on quit or “Restart now” dialog.
- Semver + build number; never block playback on update.
- Endpoint format (Tauri updater v2): version, pub_date, url (installer), signature.

### REST API contract (deployed: `https://api.seans.tedeshi.ru`)

Base: `https://api.seans.tedeshi.ru` · Auth: `Authorization: Bearer <JWT>`
(rooms WS uses `?token=`). Worker endpoints are **not** used by this client.

| Method | Path | Body / Query | Returns |
|--------|------|--------------|---------|
| POST | `/api/auth/register` | `{email,password,display_name,invite_key}` | `TokenResponse` |
| POST | `/api/auth/login` | `{email,password}` | `TokenResponse` |
| GET | `/api/auth/me` | — | `UserResponse` |
| POST | `/api/auth/invite-keys` | — | `{key, created_at}` |
| GET | `/api/search` | `?q=` | `MediaSearchResult[]` |
| GET | `/api/media/{id}` | — | `MediaDetail` |
| GET | `/api/media/{id}/releases` | `?refresh=bool` | `TorrentReleaseResponse[]` |
| POST | `/api/tasks` | `{torrent_release_id, file_paths[]}` | `TaskResponse` |
| GET | `/api/tasks` | `?active=bool` | `TaskDetailResponse[]` |
| POST | `/api/tasks/{id}/cancel` | — | `TaskDetailResponse` |
| GET | `/api/library` | — | `[{library_item, media_item, files[], total_size, ready}]` |
| GET | `/api/files/{task_file_id}/url` | — | `{url, expires_in}` |
| POST | `/api/rooms` | `{task_file_id}` | `{id, code, ws_url}` |
| GET | `/api/rooms/{code}` | — | `{room, members}` |
| PUT | `/api/history` | `{task_file_id, position_sec, duration_sec}` | `HistoryResponse` |
| GET | `/api/history` | `?limit=` | continue-watching list |
| PUT | `/api/media/{id}/review` | `{score, review?}` | `ReviewResponse` |
| GET | `/api/media/{id}/reviews` | — | `ReviewResponse[]` |
| GET | `/healthz` | — | ok |

Shapes (abridged):

- `TokenResponse`: `{access_token, token_type="bearer", user}`
- `UserResponse`: `{id, email, display_name, can_invite, quota_bytes, created_at}`
- `MediaSearchResult`: `{id, kp_id, title, year, poster_url, kp_type, rating_kp}`
- `MediaDetail`: search fields + `original_title, overview, genres[], updated_at, tmdb_id?`
- `TorrentReleaseResponse`: `{id, tracker, title, size_bytes, seeders, leechers, quality, voiceover, magnet}`
- `TaskResponse` / `TaskDetailResponse`: `{id, status, reserved_bytes, progress_pct, speed_bps, stage, error?, created_at, updated_at}`
- `HistoryResponse`: `{id, task_file_id, position_sec, duration_sec, completed, updated_at}`
- `ReviewResponse`: `{id, user_id, media_item_id, score, review, created_at, updated_at}`

OpenAPI live: `https://api.seans.tedeshi.ru/openapi.json`.

### Screens (full parity with web product)

1. **Auth gate** — “Continue in browser” / logout / account.
2. **Home / Search** — query → poster grid, year, rating.
3. **Media detail** — poster, overview, genres, reviews, releases table
   (tracker, size, seeders, quality, voiceover), pick files → `POST /api/tasks`.
4. **Tasks** — progress, speed, stage, cancel; poll while active.
5. **Library** — items + files (season/episode), Play, “Start room”.
6. **Player** — mpv surface, track/sub menus, seek, next/prev episode if present,
   chapter markers on seek bar, "Skip Intro/Recap" floating button,
   credits popup → star rating + review submit.
7. **Room** — same player + participant list, host badge, share link
   `https://seans.tedeshi.ru/room/{code}` (web page should deep-link into app).
8. **History** — continue watching.
9. **Reviews** — score 1–10 + text on media detail.
10. **Settings** — update channel, HW decode toggle, subtitle prefs, clear cache.
11. **Account** — quota, display name, invite key create (if `can_invite`).

### Design system (greenfield, shared with future web)

- Tokens: color (bg/ink/accent/danger), space scale (4/8/12/16/24/32), radii, type scale.
- Light + dark, system-follow default.
- Typography: Inter (UI) + optional display face for titles.
- Accent: deep teal/cyan for primary actions; neutral gray surfaces; one danger red.
- Density: media grid 180–220px posters; lists 48–64px rows.
- Empty/error/loading states defined for every screen.
- Client UI must feel like the same product as web — same tokens package
  (e.g. `packages/ui` if monorepo later, or `src/design/tokens.css` now).

### Repo layout (clean repo, suggested)

```
src-tauri/           # Rust shell, deep-link, updater, mpv plugin
  capabilities/
  icons/
src/                 # React UI
  screens/
  features/          # auth, search, library, player, rooms, tasks
  design/            # tokens, primitives
  api/               # typed client for Seans API
docs/                # this contract + ADRs
```

### Testing boundaries

- Unit: API client parsing, room message reducer, history throttle, deep-link router.
- Integration: Tauri command layer with mocked HTTP.
- Manual E2E checklist: login via browser, play mkv/hevc/ass, room host+guest,
  deep link cold-start, updater dry-run, Windows Defender scan of installer.

## [S3] Out of Scope

- Worker/torrent download agent (already separate).
- Client-side transcoding / HLS packaging / ffmpeg re-encode (v1).
- macOS/Linux/Android/iOS builds (architecture may keep ports open; not delivered).
- Web app implementation (contract + design tokens only).
- DRM, multi-account profiles, parental controls.
- Auto-pick “best” torrent.
- Code-signing purchase/CI issuance (structure ready; procurement is ops).

## Tasks

- [ ] T1: Scaffold Tauri 2 + React/TS + Vite, single-instance, `seans://` registration — acceptance: `npm run tauri dev` launches, `seans://` opens app (covers: S2 stack, S2 deep links)
- [ ] T2: Typed API client for all non-worker endpoints + JWT storage in keyring — acceptance: unit tests cover parse of every response schema (covers: S2 API)
- [ ] T3: Web OAuth login via `seans://auth/callback` with `state` validation — acceptance: browser login lands token in app; wrong state rejected (covers: S2 auth)
- [ ] T4: Design tokens + app shell (nav, theme light/dark) — acceptance: all screens share tokens; theme toggle works (covers: S2 design system)
- [ ] T5: Search + Media detail + reviews screens — acceptance: search/detail/review upsert against live or mock API (covers: S2 screens, S2 API)
- [ ] T6: Releases + create task + tasks list/cancel with polling — acceptance: create task shows progress updates (covers: S2 screens, S2 API)
- [ ] T7: Library + files list — acceptance: library renders files with season/episode and play affordance (covers: S2 screens)
- [ ] T8: libmpv player integration (sidecar dlls, HW decode, tracks/subs) — acceptance: plays mkv HEVC + ASS and mp4 AAC without system codecs install (covers: S2 player)
- [ ] T9: History resume + throttle upsert — acceptance: quit/reopen resumes near last position (covers: S2 player)
- [ ] T10: Rooms: create, share link, WS sync host/guest, deep link `seans://room/{code}` — acceptance: two clients play/pause/seek in sync; host promotion visible (covers: S2 rooms, S2 deep links)
- [ ] T11: Tauri updater + latest.json + silent apply path — acceptance: bump version → client downloads and applies on restart (covers: S2 updates)
- [ ] T12: Installer (NSIS/MSI), VersionInfo, Defender/manual AV checklist doc — acceptance: installer runs clean on stock Windows 11 VM (covers: S2 stack hygiene)
- [ ] T13: TheIntroDB client — fetch segments on play, cache per session, graceful skip when tmdb_id absent — acceptance: plays media with tmdb_id and shows chapters on seek bar (covers: S2 TheIntroDB)
- [ ] T14: Skip Intro/Recap floating button — appears in segment range, seeks on click, auto-hide — acceptance: button visible during intro, gone after end_ms (covers: S2 TheIntroDB)
- [ ] T15: Credits popup → rating + review — triggers at credits.start_ms, submits via PUT /api/media/{id}/review, once per session per media — acceptance: popup appears, submit persists review (covers: S2 TheIntroDB)
- [ ] T16: Chapter list dropdown in player — lists all segments with labels + timestamps, click to seek — acceptance: chapters menu navigates correctly (covers: S2 TheIntroDB)
