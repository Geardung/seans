# Промт: Seans Desktop Client (greenfield)

Скопируй целиком в чистый репозиторий.

---

## Роль

Ты собираешь **нативный Windows-клиент** медиасистемы Seans с нуля в этом пустом репо.
Бекенд уже задеплоен — не пиши сервер. Только клиент + его интеграционный контракт.

## Продукт (одним абзацем)

Seans — self-hosted медиасервис: поиск фильмов (Кинопоиск), торрент-релизы,
скачивание воркерами в S3, стрим через presigned URL, watch-party комнаты.
Веб — каталог и аккаунт. **Любой просмотр видео — только в этом десктоп-клиенте.**
Клиент логинится через веб, играет любые форматы через libmpv, открывает комнаты
по `seans://` deep link, часто и почти бесшовно самообновляется.

## Жёсткие ограничения

1. **Стек:** Tauri 2 (Rust shell) + React + TypeScript + Vite + libmpv.
   Не Electron, не Go, не Flutter, не Qt-first.
2. **Антивирусы.** Прошлый опыт: Go-фреймворк докачивал DLL в рантайме →
   ложные срабатывания и платный EV-сертификат. Правила:
   - никаких пакеров (UPX, Themida и т.п.);
   - **никакой докачки** DLL/кодеков/скриптов при первом запуске — всё в бандле;
   - `libmpv-2.dll` и его зависимости — sidecar-ресурсы приложения;
   - чистый VersionInfo (CompanyName, ProductName, FileVersion, ProductVersion);
   - не писать/исполнять ничего из `%TEMP%`, не инжектить в чужие процессы;
   - Authenticode не покупаем, но PE метаданные сразу готовим под подпись.
3. **Обновления — часто и почти бесшовно.** `tauri-plugin-updater` +
   `tauri-plugin-process`. Проверка при старте + раз в 6 часов + ручная кнопка.
   Скачивание в фоне, применение по «Restart now» или при выходе.
   Плеер не должен блокироваться апдейтом.
4. **Платформа v1:** Windows 10/11 x64. Архитектуру не завязывать только на WinAPI
   в UI, но поставляем только Windows.
5. Язык UI и кода — **русский** в интерфейсе, идентификаторы/доки — English.

## Авторизация (через веб, не через форму в клиенте)

В клиенте **нет** поля пароля.

1. Клиент генерирует одноразовый `state`, открывает системный браузер:
   `https://seans.tedeshi.ru/auth?redirect_uri=seans%3A%2F%2Fauth%2Fcallback&state=<state>`
2. Веб логинится через API бекенда и редиректит:
   `seans://auth/callback?access_token=<JWT>&state=<state>&token_type=bearer`
3. Клиент проверяет `state`, кладёт JWT в **Windows Credential Manager** (crate `keyring`),
   дёргает `GET /api/auth/me`.
4. Logout чистит keyring. Любой HTTP 401 → снова веб-логин.

Если auth-страницы ещё нет — допустим fallback на loopback
`http://127.0.0.1:<ephemeral>/callback` как `redirect_uri`, но основной путь — `seans://`.

## Deep links (одна схема `seans://`)

| URL | Действие |
|-----|----------|
| `seans://auth/callback?access_token=&state=` | завершить логин |
| `seans://room/{code}` | открыть комнату `{code}` (path-style; code — 8 символов `A–Z2–9`) |
| `seans://` | фокус приложения / Home |

Плагины: `tauri-plugin-deep-link`, `tauri-plugin-single-instance`
(второй запуск передаёт URL первому процессу). Реестр: `HKCU\Software\Classes\seans`.

## Плеер

- **libmpv** in-process, отрисовка в панель Tauri (`raw-window-handle` / HWND).
- Источник: `GET /api/files/{task_file_id}/url` → `{"url":"...","expires_in":86400}`.
- Нативный decode, **без** клиентского транскода/ffmpeg re-encode в v1.
- HW decode (D3D11/dxva2/nvdec) с автоматическим soft fallback.
- Обязательно проигрывать: mkv/mp4/webm/avi/mov; H.264/H.265/AV1/VP9;
  AAC/AC3/EAC3/TrueHD/FLAC/Opus; субтитры ASS/SSA/SRT (внешние и встроенные);
  выбор аудиодорожки; перемотка; fullscreen; скорость 0.25–2x.
- Если mpv реально не может открыть файл — понятная ошибка, не вечный спиннер.
- Прогресс: `PUT /api/history` каждые 15с, на pause/seek/закрытии.
  При открытии файла — resume из истории (в комнате приоритет у host-sync).

## Watch-party

REST:

- `POST /api/rooms` `{"task_file_id":"<uuid>"}` → `{"id","code","ws_url"}` (создаёт host)
- `GET /api/rooms/{code}` → `{"room":{...},"members":[{"user_id"}]}`

WS: `wss://api.seans.tedeshi.ru/ws/rooms/{code}?token=<JWT>`
(на dev — `ws://localhost:8000/ws/rooms/{code}?token=`).

Клиент → сервер:

```json
{"type":"join"}
{"type":"heartbeat","position":12.5}
{"type":"state","action":"play|pause|seek","position":12.5}
{"type":"sync_request"}
{"type":"leave"}
```

Сервер → клиент:

```json
{"type":"room_state","host_id":"<uuid>","position":12.5,"is_playing":true,"ts":1710000000}
{"type":"state","action":"play|pause|seek","position":12.5,"by":"<uuid>"}
{"type":"member_joined","user":{"user_id":"...","name":"..."}}
{"type":"member_left","user":{"user_id":"...","name":"..."}}
{"type":"error","detail":"Only host can control playback"}
```

Правила: только host шлёт `state`; гости применяют `state`/`room_state` и шлют
`heartbeat`; при уходе host сервер повышает следующего и рассылает `room_state`.
WS close 4001 = unauthorized, 4004 = room not found.
Deep link `seans://room/{code}` — вход гостем (или открыть свою комнату, если host).
Шаринг: кнопка копирует `https://seans.tedeshi.ru/room/{code}` (веб-страница позже
будет кидать в `seans://room/{code}`).

## API (deployed)

Base: `https://api.seans.tedeshi.ru` · `Authorization: Bearer <JWT>`
· OpenAPI: `https://api.seans.tedeshi.ru/openapi.json`
**Worker-эндпоинты клиенту не нужны.**

| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/api/auth/register` | `{email,password,display_name,invite_key}` | `TokenResponse` |
| POST | `/api/auth/login` | `{email,password}` | `TokenResponse` |
| GET | `/api/auth/me` | — | `UserResponse` |
| POST | `/api/auth/invite-keys` | — | `{key,created_at}` |
| GET | `/api/search` | `?q=` | `MediaSearchResult[]` |
| GET | `/api/media/{id}` | — | `MediaDetail` |
| GET | `/api/media/{id}/releases` | `?refresh=bool` | `TorrentReleaseResponse[]` |
| POST | `/api/tasks` | `{torrent_release_id,file_paths[]}` | `TaskResponse` |
| GET | `/api/tasks` | `?active=bool` | `TaskDetailResponse[]` |
| POST | `/api/tasks/{id}/cancel` | — | `TaskDetailResponse` |
| GET | `/api/library` | — | см. ниже |
| GET | `/api/files/{task_file_id}/url` | — | `{url,expires_in}` |
| POST | `/api/rooms` | `{task_file_id}` | `{id,code,ws_url}` |
| GET | `/api/rooms/{code}` | — | `{room,members}` |
| PUT | `/api/history` | `{task_file_id,position_sec,duration_sec}` | `HistoryResponse` |
| GET | `/api/history` | `?limit=1..200` | список continue-watching |
| PUT | `/api/media/{id}/review` | `{score:int,review?:string}` | `ReviewResponse` |
| GET | `/api/media/{id}/reviews` | — | `ReviewResponse[]` |
| GET | `/healthz` | — | ok |

Схемы (существенные поля):

- `TokenResponse` `{access_token, token_type:"bearer", user: UserResponse}`
- `UserResponse` `{id, email, display_name, can_invite, quota_bytes, created_at}`
- `MediaSearchResult` `{id, kp_id, title, year, poster_url, kp_type, rating_kp}`
- `MediaDetail` = search + `{original_title, overview, genres[], updated_at, tmdb_id?}`
- `TorrentReleaseResponse` `{id, tracker, title, size_bytes, seeders, leechers, quality, voiceover, magnet}`
- `TaskResponse`/`TaskDetailResponse` `{id, status, reserved_bytes, progress_pct, speed_bps, stage, error?, created_at, updated_at}`
- `HistoryResponse` `{id, task_file_id, position_sec, duration_sec, completed, updated_at}`
- `ReviewResponse` `{id, user_id, media_item_id, score, review, created_at, updated_at}`
- `GET /api/library` → `[{library_item:{id,status,created_at}, media_item:{id,title,poster_url,kp_type,year}, files:[{id,path,size_bytes,status,season,episode}], total_size, ready}]`

Все id — UUID строкой. `rating_kp`/`position_sec`/`duration_sec` могут приходить как строки-числа — парсь в number.

## TheIntroDB — главы, «Пропустить интро», поп-ап рейтинга при титрах

Внешний API: `https://api.theintrodb.org/v3/media?tmdb_id={id}&season={s}&episode={e}`
· OpenAPI: `https://api.theintrodb.org/v3/openapi.json`
· Без API-ключа для чтения. Лимит: 30 req/10s на IP, 1000 req/день.

TheIntroDB хранит timestamps для 4 типов сегментов:
- `intro` — опенинг (start_ms может быть null = начало файла)
- `recap` — реcap/резюме серии (start_ms может быть null)
- `credits` — титры (end_ms может быть null = до конца файла)
- `preview` — превью следующей серии (end_ms может быть null)

Каждый тип — массив `{start_ms, end_ms}` (может быть несколько сегментов).

**Бекенд-зависимость:** `MediaDetail` должен содержать `tmdb_id` (nullable integer).
Бекенд резолвит tmdb_id при импорте медиа через TMDB API (по title+year или
external_ids). Если `tmdb_id = null` — фича молча выключена для этого медиа.
Для сериалов клиент передаёт `season`/`episode` из `TaskFile.season`/`TaskFile.episode`.

**Поведение при старте плеера:**

1. Читаем `tmdb_id` из `MediaDetail`.
2. GET TheIntroDB segments для этого медиа (+ season/episode для сериалов).
3. Кешируем в память на время сессии (не храним на диск).

**UI плеера:**

- **Метки на seek bar:** тонкие цветные полоски на `start_ms` каждого сегмента.
  Цвета: intro=teal, recap=blue, credits=amber, preview=gray. При hover — лейбл + время.
- **Кнопка «Пропустить интро»:** появляется когда позиция ∈ `[intro.start_ms ?? 0, intro.end_ms]`.
  Клик → seek к `intro.end_ms + 0.3с`. Аналогично «Пропустить recap».
  Автоскрытие через 2с после выхода из диапазона сегмента.
- **Поп-ап при титрах:** когда позиция ≥ `credits[0].start_ms`, показываем
  оверлей **без паузы воспроизведения**:
  - Звёздный рейтинг 1–10 (один тап → submit)
  - Необязательный textarea для текстового отзыва
  - Кнопка «Позже» / закрыть → отложить до следующего открытия файла
  - Submit → `PUT /api/media/{id}/review` с `{score, review}`
  - Поп-ап показывается **один раз** за сессию на медио; не показывается,
    если пользователь уже оставил отзыв на это медио (проверяем `MediaDetail.user_review`).
- **Меню «Главы»:** в контролах плеера дропдаун с списком всех сегментов
  (тип + timestamp). Клик → seek к `start_ms` сегмента.

**Комнаты:** TheIntroDB данные персональные для каждого клиента. Кнопка «Пропустить
интро» индивидуальная, не бродкастится. Host-сик мимо интро бродкастится
обычным `state`-сообщением. Поп-ап рейтинга появляется у каждого зрителя.

## Экраны (паритет с веб-продуктом)

1. Auth gate («Продолжить в браузере», выход, аккаунт)
2. Home / Search — постерная сетка
3. Media detail — инфо, ревью, таблица релизов → выбрать файлы → создать task
4. Tasks — прогресс/скорость/stage/cancel (polling пока active)
5. Library — файлы (season/episode), Play, «Создать комнату»
6. Player — mpv surface + дорожки/сабы/seek/fullscreen + главы на seek bar + «Skip Intro/Recap» + поп-ап рейтинга при титрах
7. Room — тот же player + участники, host-badge, share link
8. History — continue watching
9. Reviews — score 1–10 + текст
10. Settings — HW decode, сабы, проверка обновлений
11. Account — quota, display name, создание invite key (если `can_invite`)

## Дизайн-система (greenfield, общий язык с будущим вебом)

- Токены в `src/design/tokens.css` (или `tokens.ts`): bg/ink/accent/danger,
  space 4/8/12/16/24/32, radii, type scale.
- Light + dark, default — system.
- UI: Inter; акцент — глубокий teal/cyan; нейтральные поверхности; danger — red.
- Сетка медиа: постеры 180–220px; списки 48–64px row.
- На каждом экране: loading / empty / error состояния.
- Веб позже переиспользует эти же токены — не «свой» визуал.

## Сuggested layout

```
src-tauri/          # shell, deep-link, updater, mpv plugin/commands
src/
  api/              # typed Seans API client
  features/         # auth, search, media, tasks, library, player, rooms, history, reviews
  screens/
  design/           # tokens, primitives
docs/               # API contract notes, AV checklist
```

## Milestones (сделай по порядку, каждый — рабочий слайс)

1. Scaffold Tauri 2 + React/TS, `seans://`, single-instance → приложение открывается.
2. API client + JWT keyring + web OAuth login → пользователь залогинен.
3. Design tokens + shell (nav, theme) → все экраны в одном визуальном языке.
4. Search + Media detail + Reviews.
5. Releases + create task + Tasks polling.
6. Library + files.
7. libmpv player (sidecar dll, HW decode, сабы/дорожки) → играет HEVC/ASS из mkv.
8. TheIntroDB: главы на seek bar, «Пропустить интро/recap», поп-ап рейтинга при титрах → работает для медиа с tmdb_id.
9. History resume.
10. Rooms WS + `seans://room/{code}` → два клиента синхронны.
11. Updater + installer + AV checklist.

## Verification (прогони перед «готово»)

- `npm run build` и `npm run tauri build` без ошибок.
- Unit-тесты: API parsing, room reducer, deep-link router, history throttle.
- Manual: логин через браузер; mkv HEVC + ASS; mp4 H.264/AAC; комната host+guest;
  cold-start `seans://room/CODE`; updater dry-run; TheIntroDB главы для медиа с tmdb_id,
  поп-ап рейтинга при титрах; установка на чистый Windows 11
  и отсутствие реакции Defender (или зафиксированный false-positive report).

## Non-goals (v1)

- Воркер/скачивание торрентов (это другой сервис)
- Клиентский транскод / HLS / ffmpeg re-encode
- macOS/Linux/Android/iOS
- Реализация веб-приложения (только контракт и токены)
- DRM, мультипрофили, авто-выбор «лучшего» торрента
- Покупка EV/код-подписи в этой задаче

---

Начни с README (что это, как поднять dev, как собрать), затем milestone 1.
Пиши код сразу в репо, без лишних церемоний. Если API отвечает иначе, чем в
контракте — доверяй `openapi.json` и живым ответам, контракт поправь в `docs/`.
