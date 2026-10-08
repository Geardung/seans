# Настройка Sonarr / Radarr / Bazarr

Практический гайд по подъёму и настройке стека *arr в Seans.

Связано: `docs/compose/spec/arr-stack.md`, `docs/compose/spec/media-flexibility.md`.

## Топология (кратко)

| Где | Что |
|-----|-----|
| Сервер (docker-compose) | Sonarr, Radarr, Bazarr, backend, Caddy, local JacRed |
| Машина воркера | qBittorrent (Web API) + агент заливки в S3 |
| Внешний индексатор | JacRed от разработчиков: `https://api.jacred.su/torznab` |

Воркеры — **отдельные** компьютеры. У них нет доступа к root folders *arr
(`/data/media/...`) и к диску compose-стека. Файл качается **на воркере**,
оттуда уходит в S3.

```
*arr (сервер) --add torrent--> qBittorrent (воркер) --> диск воркера --> S3
```

## Субдомены

| URL | Сервис |
|-----|--------|
| https://sonarr.seans.tedeshi.ru | Sonarr |
| https://radarr.seans.tedeshi.ru | Radarr |
| https://bazarr.seans.tedeshi.ru | Bazarr |

qBittorrent **не** публикуется через Caddy — только Web API на машине
воркера (адрес известен оператору).

## Подъём

```bash
# на сервере
cp .env.example .env   # заполнить секреты
docker compose up -d sonarr radarr bazarr
```

После старта:

1. Открыть `https://sonarr.seans.tedeshi.ru` (и Radarr/Bazarr).
2. Settings → General → **API Key** — скопировать (понадобится бекенду и Bazarr).
3. Прописать в `.env` сервера:

```env
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=<из UI>
RADARR_URL=http://radarr:7878
RADARR_API_KEY=<из UI>
ARR_CACHE_TTL_SECONDS=300
ARR_EPISODE_CACHE_TTL_SECONDS=1800
```

4. Перезапустить backend: `docker compose up -d backend`.

Каталог для клиентов: `GET /api/arr/series`, `/api/arr/movies` и т.д.
(см. спеку). Повторные запросы в течение TTL идут из RAM.

---

## Sonarr (сериалы / аниме)

### Media Management

- **Root Folder**: `/data/media/tv` (и при желании `/data/media/anime`).
  Это **каталожный** путь в UI Sonarr; фактический файл создаётся на диске
  воркера и уходит в S3. Воркеры в этот каталог не заходят.
- **Quality Profiles** — заведите хотя бы:
  - `HD 1080p` — WEB-DL/BluRay 1080p как default;
  - `HD 720p` — для «слабого» канала / партнёра;
  - опционально `Anime` с кастомными тегами озвучки.
- **Language** — English / Russian по необходимости.
- **Root Folders** применить к добавляемым сериалам.

### Download Clients (qBittorrent **на воркере**)

Settings → Download Client → Add → **qBittorrent**

| Поле | Значение |
|------|----------|
| Host | IP/домен машины воркера |
| Port | 8080 (или ваш WEBUI_PORT) |
| Username / Password | из WebUI qBittorrent (или API key) |
| Category | `sonarr` (или `seans`) |
| Use SSL | только если у воркера есть HTTPS |
| Remove Completed / Failed | на усмотрение; для сидов — не удалять сразу |

Добавьте **по одному client на каждый воркер**, которому разрешены
загрузки. Для теста хватит одного.

> Sonarr шлёт .torrent/magnet через Web API qBittorrent. Файл появится
> в `Save path` **на машине воркера**. Импорт Sonarr в root folder
> через общий FS не выполняется — это нормально для схемы «заливка в S3».

### Indexers (внешний JacRed)

Settings → Indexers → Add → **Torznab**

| Поле | Значение |
|------|----------|
| URL | `https://api.jacred.su/torznab` |
| API Path | `/api` |
| API Key | `jrs_oywj48MR1kOoq2ZdRupofyswAtVx541MZexccaD4hts` |
| Categories | `5000, 5030, 5040, 5070` (TV, TV/WEB-DL, TV/HD, TV/Anime) |
| Search Mode | зачастую `tvsearch` / `search` (как принимает JacRed) |

После добавления нажмите **Test**. Ошибки 401 — неверный API key;
таймауты — сеть до `api.jacred.su`.

Локальный `jacred.seans.tedeshi.ru` / `http://jacred:9117` — **отдельный**
канал для backend `/api/media/{id}/releases`. В Sonarr его не добавляйте,
если не нужен fallback.

### Качество и озвучки

- Custom Formats / Release Profiles — теги вида `Дубляж`, `Многоголосый`,
  `LostFilm`, `StudioBand` и т.п., чтобы предпочитать нужную озвучку.
- Один релиз = обычно один MKV с несколькими audio tracks. В плеере Seans
  дорожки переключаются (см. media-flexibility).
- Отдельные audio-файлы/отдельные торренты — **не** через Sonarr, а задачами
  Seans (парные задания video/audio).

### Пользователи

Settings → General → Authentication: оставить за Caddy (не exposed наружу
без TLS). Доступ по субдомену — через общий auth/сеть (по желанию добавить
basic auth в Caddy).

---

## Radarr (фильмы)

### Media Management

- **Root Folder**: `/data/media/movies` (каталожный путь, см. выше).
- **Quality Profiles**: `HD 1080p` (default), `720p`, `UHD` при необходимости.
- **Minimum Availability**: `Released` / `Physical/Web` — как хотите.

### Download Clients

Тот же qBittorrent **на воркере**, категория `radarr` (или `seans`).
Настройки идентичны Sonarr (host воркера, порт WebUI, user/pass).

### Indexers

Torznab (JacRed), **те же** URL / API Path / API Key:

| Поле | Значение |
|------|----------|
| URL | `https://api.jacred.su/torznab` |
| API Path | `/api` |
| API Key | `jrs_oywj48MR1kOoq2ZdRupofyswAtVx541MZexccaD4hts` |
| Categories | `2000, 2010, 2020, 2030, 2040, 2050` (Movies + SD/HD/UHD/BluRay/WEB) |

### Metadata

- **The Movie Database** — ключ TMDB (уже есть `TMDB_API_TOKEN` у Seans,
  можно переиспользовать при желании).
- **Alternative Titles** — для поиска русских названий.

---

## Bazarr (субтитры)

### Связь с Sonarr / Radarr

Settings → Sonarr:

| Поле | Значение |
|------|----------|
| Address | `http://sonarr:8989` (внутри compose-сети) или `https://sonarr.seans.tedeshi.ru` |
| API Key | из Sonarr |

Аналогично Radarr: `http://radarr:7878` / `https://radarr.seans.tedeshi.ru`.

### Языки и провайдеры

- Settings → Languages: добавить нужные (Russian, English).
- Settings → Providers: OpenSubtitles, SubHD, и др. — с учётом API key /
  лимитов. Для большинства хватает `OpenSubtitles.com` + `YifySubtitles`.
- Settings → Anti-Captcha — если провайдер требует.

### Важно: Bazarr и «где лежат файлы»

Bazarr сканирует media **на диске рядом с Sonarr/Radarr**. В текущей
топологии видео лежат на дисках воркеров и в S3 — сервер их не видит.

Практические варианты:

1. **Субтитры как компонент Seans** (роль `subtitle` в media-flexibility):
   воркер/источник приносит .srt/.ass, клиент мержит. Bazarr — только UI
   для провайдеров/истории.
2. **Временный доступ к файлам** (network share / sync) — тогда Bazarr
   сможет писать субтитры рядом с видео и их подхватит заливка в S3.
3. **Bazarr на машине воркера** — полноценный pipeline, но субдомен
   `bazarr.seans.tedeshi.ru` останется для единого UI (reverse proxy на
   воркер или централизованный инстанс без доступа к файлам).

До выбора одного из вариантов считайте Bazarr **конфигурационным UI**
(провайдеры, языки, интеграция *arr), без обработки файлов на сервере.

---

## Воркер и qBittorrent (оператору)

На машине воркера:

1. qBittorrent Web UI включён (порт 8080), задан user/password или API key.
2. `Save path` / категории: например `/var/seans/torrents/{sonarr,radarr}`.
3. Агент воркера:
   - слушает завершения в **своём** qBittorrent (API или папка);
   - заливает файлы в S3 по presigned PUT (протокол Seans worker);
   - **не** обращается к `/data` сервера и к root folders *arr.
4. В Sonarr/Radarr Download Client указан host **этой** машины.

Регистрация воркера в Seans — как сейчас: `POST /api/worker/register`.

---

## Проверка после настройки

| Шаг | Ожидание |
|-----|----------|
| `curl https://sonarr.seans.tedeshi.ru/ping` | pong / 200 |
| Sonarr → Indexers → Test (JacRed) | OK |
| Sonarr → Download Client → Test | OK (до воркера) |
| `curl -H "Authorization: Bearer <jwt>" https://api.seans.tedeshi.ru/api/arr/series` | JSON списка |
| Повторный curl в течение TTL | быстро (из RAM), qBit/*arr не дёргаются |

## Типовые проблемы

| Симптом | Что проверить |
|---------|----------------|
| Indexer Test: unauthorized | API key JacRed, URL `https://api.jacred.su/torznab` |
| Download Client Test: timeout | firewall на воркере, порт WebUI, хост из настроек |
| Grab скачал, в Sonarr «no file» | ожидаемо без общего FS; смотрите S3 / лог агента воркера |
| Bazarr не видит эпизоды | нет файлов на диске сервера — см. «Bazarr и файлы» |
| `/api/arr/*` → 503 | не заполнены `SONARR_*` / `RADARR_*` в `.env` |
| `/api/arr/*` → 502 | backend не достучался до `sonarr`/`radarr` (compose-сеть) |
