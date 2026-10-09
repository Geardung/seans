/compose-next Обязательно изучи репозиторий бекенда D:\\projects\\tedeshi\\seans



Отличные новости: воркер можно строить \*\*первым\*\*, до готовности бэкенда — в репо воркера делаем mock-backend, и ты сразу сможешь гонять полный цикл «задача → qBittorrent → S3» на реальном железе. Когда напишем настоящий бэкенд, просто поменяем `BACKEND\_URL`.



Три решения, зафиксированные в промте (объясню кратко):



1\. \*\*S3-доступ воркера — через rclone с ключами, а не presigned.\*\* Воркер — наш доверенный компонент в нашей инфраструктуре, ему нужен полный multipart upload больших файлов. Presigned URLs оставляем для того, для чего они созданы — клиентских плееров (mpv). Если reg.ru позволяет создать ключ с правом только на бакет `seans` — сделай это.

2\. \*\*rclone как subprocess, а не S3 SDK\*\* — из коробки получает multipart, ретраи, параллельную заливку; агент только готовит конфиг и вызывает команду.

3\. \*\*Pull-модель + lease/heartbeat\*\* — как обсуждали, воркер сам приходит за задачами и сам сообщает прогресс.



\---



\## Промт для кодинг-агента



Скопируй всё между маркерами (включительно):



````markdown

\# Задача: реализовать Worker для self-hosted медиасервиса «Seans»



\## Контекст проекта



Seans — self-hosted сервис: пользователь выбирает фильм/сериал, система ищет торренты,

worker'ы скачивают выбранные раздачи и заливают файлы в S3, клиенты (десктопное

приложение с mpv) стримят напрямую из S3 по pre-signed URLs, минуя backend.



Компоненты системы:

\- \*\*Backend\*\* (API + PostgreSQL) на дешёвом VPS — домен `api.seans.tedeshi.ru`.

&#x20; ЕЩЁ НЕ НАПИСАН. Ты его НЕ реализуешь (кроме mock-заглушки для разработки, см. ниже).

\- \*\*Worker\*\* (этот компонент) — прерываемый сервер с быстрым каналом и большим диском.

&#x20; Может быть развёрнут в нескольких экземплярах, работает параллельно с другими worker'ами.

\- \*\*S3\*\*: AWS-совместимое хранилище (buckets.ru):

&#x20; - endpoint: `https://s3.buckets.ru/`

&#x20; - bucket: `seans`

&#x20; - path-style addressing (использовать `force\_path\_style = true`)

\- \*\*qBittorrent\*\*: запускается рядом с worker'ом в docker compose, управляется через Web API v2.



Путь файла в S3: `media/users/{user\_id}/{media\_id}/.../{filename}` — backend передаёт

worker'у готовый префикс `dest\_prefix`, worker приписывает к нему относительный путь файла.



\## Требования к стеку (зафиксировано, не менять)



\- \*\*Go 1.23+\*\*, стандартная библиотека: `net/http`, `encoding/json`, `log/slog`,

&#x20; `os/signal`, `context`. Без тяжёлых фреймворков.

\- \*\*rclone\*\* — вызывается как subprocess для заливки в S3. Конфиг rclone генерирует

&#x20; сам агент при старте (пишет INI-файл в volume `/state`), НЕ через `rclone config create`.

\- \*\*qBittorrent\*\* — образ `lscr.io/linuxserver/qbittorrent:latest`, управление через

&#x20; Web API v2.

\- Docker + docker compose для запуска.

\- Тесты: stdlib `testing` + `httptest`.

\- Весь код, идентификаторы и комментарии — на английском. README — на русском.



\## Жизненный цикл worker'а



1\. \*\*Startup\*\*: прочитать конфиг из env, сгенерировать `rclone.conf` в `/state`,

&#x20;  проверить доступность qBittorrent (login), зарегистрироваться на backend.

2\. \*\*Claim loop\*\*: пока не получен SIGTERM — каждые `CLAIM\_INTERVAL\_SEC` секунд

&#x20;  запрашивать задачу, если активных задач < `MAX\_CONCURRENT\_TASKS`.

3\. \*\*Выполнение задачи\*\* (state machine: `preparing → downloading → uploading → done`).

4\. \*\*Heartbeat\*\*: каждые `HEARTBEAT\_INTERVAL\_SEC` отправлять прогресс всех активных задач.

5\. \*\*Graceful shutdown\*\* по SIGTERM/SIGINT (см. отдельный раздел).



Регистрация идемпотентна: при каждом старте worker вызывает `POST /v1/workers/register`

с общим секретом `WORKER\_REGISTER\_TOKEN`; backend возвращает `worker\_id` и `worker\_token`

(в память, не на диск). При 401 на любых запросах — перерегистрация один раз, при

повторном 401 — экспоненциальный бэкофф и продолжение попыток (не падать).



\## Контракты Backend API (зафиксировать как есть)



Все запросы — JSON, кроме оговорённых. Base URL — из `BACKEND\_URL`.



\### POST /v1/workers/register

```

Authorization: Bearer ${WORKER\_REGISTER\_TOKEN}

Body:   {"hostname":"worker-01","version":"0.1.0","max\_concurrent\_tasks":1,"disk\_free\_gb":220.5}

200:    {"worker\_id":"w\_abc","worker\_token":"jwt...","heartbeat\_interval\_sec":60}

```



\### POST /v1/workers/{worker\_id}/heartbeat

```

Authorization: Bearer ${worker\_token}

Body: {"tasks":\[{"task\_id":"tsk\_1","stage":"downloading","progress\_pct":45.2,

&#x20;      "speed\_mbps":12.4,"eta\_min":8,"message":""}],

&#x20;      "disk\_free\_gb":210.5}

200: {}

```

Ошибка heartbeat НЕ фейлит задачу. 3 неудачных подряд — логировать и продолжать работу.



\### POST /v1/workers/{worker\_id}/claim

```

Authorization: Bearer ${worker\_token}

Body: {"max\_tasks":1}

200: {"task":null}

или

200: {"task":{

&#x20; "task\_id":"tsk\_01HXYZ",

&#x20; "torrent":{"kind":"magnet","data":"magnet:?xt=urn:btih:..."},

&#x20; "select\_files":\["Show/Season 1/E01.mkv"],   // null => качать все файлы

&#x20; "dest\_prefix":"media/users/u\_42/md\_tokyo\_ghoul/s1/",

&#x20; "max\_bytes":2147483648,

&#x20; "lease\_minutes":10

}}

```

`torrent.kind`: `"magnet"` (data — magnet-ссылка) или `"file\_b64"` (data — base64

содержимое .torrent файла, декодировать во временный файл).

`select\_files` — точные пути файлов внутри торрента, которые нужно скачать и залить.

Остальные файлы торрента качать НЕ нужно (file priority 0).



\### POST /v1/tasks/{task\_id}/complete

```

Authorization: Bearer ${worker\_token}

Body: {"files":\[{"s3\_key":"media/users/u\_42/md\_tokyo\_ghoul/s1/Show/Season 1/E01.mkv",

&#x20;       "size":734003200}],

&#x20;      "stats":{"download\_seconds":412,"upload\_seconds":190}}

200: {}

```



\### POST /v1/tasks/{task\_id}/fail

```

Authorization: Bearer ${worker\_token}

Body: {"reason":"stalled: no download progress for 30m","permanent":true}

200: {}

```

`permanent=true` — повтор задачи бессмыслен (нет сидов, quota exceeded, битый торрент).

`permanent=false` — временная ошибка (сеть, S3 недоступен), backend может пере-выдать.



\### Ошибки HTTP

\- 401 → перерегистрация (см. выше).

\- 409/410 на задачах → задача больше не наша, локально забыть и почистить.

\- 5xx / сеть → retry с экспоненциальным бэкоффом (1s, 2s, 4s ... max 5m), не падать.



\## Выполнение задачи — пошагово



\### preparing

1\. `rm -rf` и пересоздать каталог `/staging/{task\_id}/` (идемпотентность при повторе задачи).

2\. Проверить в qBittorrent, нет ли хвостов от предыдущей попытки: найти торрент с

&#x20;  savepath равным `QBIT\_DOWNLOADS/{task\_id}` (категория `seans`) — если есть, удалить

&#x20;  с `deleteFiles=true`.

3\. Добавить торрент:

&#x20;  - `kind=file\_b64` → POST `/api/v2/torrents/add`, multipart/form-data, поле

&#x20;    `torrents` с файлом, параметры `savepath={QBIT\_DOWNLOADS}/{task\_id}`,

&#x20;    `category=seans`, `paused=false`.

&#x20;  - `kind=magnet` → тот же endpoint, поле `urls` с magnet-ссылкой.

&#x20;  Ответ `Ok.` / `Fails.` — при `Fails.` немедленно fail(permanent=true).

4\. Дождаться появления торрента в `GET /api/v2/torrents/info?category=seans`

&#x20;  (match по savepath). Получить `hash`.

5\. Если magnet и торрент в состоянии `metaDL` (метаданные качаются) — ждать появления

&#x20;  файлов до 5 минут (`TORRENT\_METADATA\_TIMEOUT`). Не появились → fail(permanent=false).

6\. Прочитать `GET /api/v2/torrents/files?hash={hash}`. Получить список файлов торрента.

7\. \*\*Проверка размера\*\*: суммарный размер выбранных файлов (учитывая `select\_files`)

&#x20;  > `max\_bytes` → fail(permanent=true, "quota exceeded").

8\. Если `select\_files` не null — выставить приоритеты: ненужным файлам `priority=0`

&#x20;  (skip), нужным `priority=1` (normal). Сопоставление путей: сначала exact match

&#x20;  по полному `name`; если exact не нашёл ни одного файла — суффиксный матч по basename

&#x20;  (толерантность к различиям структуры каталогов), логировать fallback.



\### downloading

1\. Poll `GET /api/v2/torrents/info` по hash каждые 5 сек: `progress`, `dlspeed`,

&#x20;  `downloaded`, `state`.

2\. \*\*Stall detection\*\*: если `downloaded` не растёт дольше

&#x20;  `DOWNLOAD\_STALL\_TIMEOUT\_MIN` (по умолчанию 30 мин) — fail(permanent=true, "stalled").

3\. \*\*Общий таймаут задачи\*\* `TASK\_MAX\_HOURS` (по умолчанию 12 ч) → fail(permanent=false).

4\. Завершённость: `progress >= 1.0` и state в

&#x20;  `\["stoppedUP","stoppedDL","uploading","stalledUP","pausedUP"]` (qBittorrent

&#x20;  в разных версиях зовёт finished по-разному; надёжный критерий — progress>=1.0

&#x20;  и отсутствие активной закачки).



\### uploading

1\. Вычислить список файлов к заливке: для каждого выбранного файла

&#x20;  `s3\_key = dest\_prefix + relative\_path\_within\_torrent`,

&#x20;  `local\_path = /staging/{task\_id}/ + relative\_path\_within\_torrent`.

2\. Заливка одной командой rclone (move удаляет локальные файлы после успешного upload):

&#x20;  ```

&#x20;  RCLONE\_CONFIG=/state/rclone.conf rclone move \\

&#x20;    /staging/{task\_id}/ seans:seans/{dest\_prefix} \\

&#x20;    --transfers 4 --checkers 8 \\

&#x20;    --s3-chunk-size 64M --s3-upload-concurrency 4 \\

&#x20;    --s3-acl private --fast-list -v --stats 15s --log-file /state/rclone.log

&#x20;  ```

3\. Retry rclone до 3 попыток. После 3 неудач → fail(permanent=false).

4\. После успеха: `rm -rf /staging/{task\_id}/` (пустые каталоги-хвосты).

5\. Удалить торрент из qBittorrent: `POST /api/v2/torrents/delete`,

&#x20;  form `hashes={hash}\&deleteFiles=true`.

6\. `POST /v1/tasks/{task\_id}/complete` со списком файлов и статистикой.



\### Конфигурация rclone (/state/rclone.conf, генерируется при старте)

```ini

\[seans]

type = s3

provider = Other

access\_key\_id = ${S3\_ACCESS\_KEY}

secret\_access\_key = ${S3\_SECRET\_KEY}

endpoint = https://s3.buckets.ru/

force\_path\_style = true

acl = private

```



\### Mock-режим S3 (для разработки без S3)

Если `MOCK\_S3=true` — вместо удалённого remote использовать локальный путь:

`rclone move /staging/{task\_id}/ /tmp/seans-s3-mock/{dest\_prefix}` (remote типа local).

Реально S3 не трогается. Полезно для CI и первых прогонов.



\## Heartbeat и lease



\- Heartbeat — отдельная горутина, тик каждые `HEARTBEAT\_INTERVAL\_SEC`

&#x20; (значение из ответа register, по умолчанию 60).

\- В heartbeat идут ВСЕ активные задачи с их stage/progress.

\- Worker НЕ управляет lease сам — backend продлевает lease на основании heartbeat.

\- `disk\_free\_gb` — свободное место на `/staging` (syscall statfs).



\## Graceful shutdown (критично: воркеры прерываемые)



По SIGTERM/SIGINT:

1\. Остановить claim loop (новые задачи не брать).

2\. Если `DRAIN\_ON\_SHUTDOWN=true` — дождаться завершения активных задач (до

&#x20;  `DRAIN\_TIMEOUT\_SEC`, по умолчанию 3600), затем перейти к п.4.

3\. Иначе: для каждой активной задачи отправить `fail(permanent=false, reason

&#x20;  "worker shutting down")`, остановить торренты в qbit (`torrents/pause`), чтобы

&#x20;  backend не ждал lease.

4\. Финальный heartbeat, закрыть http-клиенты, exit 0.

По SIGKILL ничего не делаем — backend восстановится через lease-таймаут самостоятельно.



\## Конфигурация (env, обязательный .env.example)



| Переменная | По умолчанию | Описание |

|---|---|---|

| `BACKEND\_URL` | — | URL backend API |

| `WORKER\_REGISTER\_TOKEN` | — | общий секрет для register |

| `WORKER\_NAME` | hostname ОС | имя воркера |

| `QBIT\_URL` | `http://qbittorrent:8080` | Web API qBittorrent |

| `QBIT\_USER` | `admin` | |

| `QBIT\_PASS` | — | пароль Web UI |

| `QBIT\_DOWNLOADS` | `/downloads` | путь загрузок ВНУТРИ контейнера qbit |

| `STAGING\_DIR` | `/staging` | тот же host-каталог, видимый агенту |

| `S3\_ACCESS\_KEY` / `S3\_SECRET\_KEY` | — | ключи reg.ru S3 |

| `MOCK\_S3` | `false` | заливка в локальный каталог вместо S3 |

| `CLAIM\_INTERVAL\_SEC` | `10` | |

| `MAX\_CONCURRENT\_TASKS` | `1` | |

| `HEARTBEAT\_INTERVAL\_SEC` | `60` | |

| `DOWNLOAD\_STALL\_TIMEOUT\_MIN` | `30` | |

| `TORRENT\_METADATA\_TIMEOUT` | `5m` | |

| `TASK\_MAX\_HOURS` | `12` | |

| `DRAIN\_ON\_SHUTDOWN` | `false` | |

| `DRAIN\_TIMEOUT\_SEC` | `3600` | |

| `STATE\_DIR` | `/state` | rclone.conf, логи rclone |



Агент в контейнере видит каталог загрузок как `STAGING\_DIR`, qBittorrent пишет в

`QBIT\_DOWNLOADS` — это ОДИН и тот же host-каталог, смонтированный в оба контейнера

под разными именами. В коде локальный путь файла = `STAGING\_DIR/{task\_id}/...`.



\## Структура проекта



```

worker/

├── cmd/

│   ├── agent/main.go           # entrypoint воркера

│   └── mockbackend/main.go     # mock backend для разработки

├── internal/

│   ├── config/config.go        # env → struct, валидация

│   ├── backend/client.go       # HTTP клиент к backend API (register/claim/heartbeat/complete/fail)

│   ├── qbit/client.go          # клиент qBittorrent Web API v2

│   ├── engine/engine.go        # цикл worker'а: claim loop, пул задач, heartbeat

│   ├── engine/task.go          # state machine задачи (preparing→downloading→uploading→done)

│   ├── s3uploader/rclone.go    # генерация rclone.conf, вызов rclone move, retry

│   └── sysutil/disk.go         # statfs для disk\_free\_gb

├── docker/

│   ├── Dockerfile

│   └── docker-compose.yml

├── .env.example

├── Makefile                    # build / test / lint / compose-up / compose-down

├── go.mod

└── README.md                   # на русском: как работает, деплой нового воркера, переменные

```



\## Mock backend (cmd/mockbackend)



Минимальный HTTP-сервер (stdlib), реализующий ВСЕ эндпоинты контракта выше:

\- держит 1 фейковую задачу в памяти (едиождовый claim),

\- параметры задачи — из env: `MOCK\_TORRENT\_KIND` (magnet|file\_b64),

&#x20; `MOCK\_TORRENT\_DATA` (magnet-строка или URL .torrent — во втором случае mock сам

&#x20; скачает и отдаст base64), `MOCK\_SELECT\_FILES`, `MOCK\_DEST\_PREFIX`, `MOCK\_MAX\_BYTES`.

\- все heartbeat/complete/fail печатает в stdout в человекочитаемом виде,

\- `MOCK\_S3=true` рекомендован вместе с этим режимом.

Тестовый торрент для разработки: официальный образ Ubuntu —

`https://releases.ubuntu.com/24.04/ubuntu-24.04.3-desktop-amd64.iso.torrent`

(проверь актуальную ссылку на releases.ubuntu.com при написании README; легальный

контент с быстрыми сидами).



\## Docker



\### docker/Dockerfile (multi-stage, финальный образ \~30 MB)

```dockerfile

FROM golang:1.23-alpine AS build

WORKDIR /src

COPY go.mod go.sum ./

RUN go mod download

COPY . .

ARG VERSION=dev

RUN CGO\_ENABLED=0 go build -ldflags "-s -w -X main.version=${VERSION}" \\

&#x20;   -o /out/agent ./cmd/agent



FROM alpine:3.20

RUN apk add --no-cache rclone ca-certificates

COPY --from=build /out/agent /usr/local/bin/agent

USER nobody

ENTRYPOINT \["agent"]

```



\### docker/docker-compose.yml

```yaml

services:

&#x20; qbittorrent:

&#x20;   image: lscr.io/linuxserver/qbittorrent:latest

&#x20;   container\_name: seans-worker-qbit

&#x20;   environment:

&#x20;     - PUID=1000

&#x20;     - PGID=1000

&#x20;     - TZ=Europe/Moscow

&#x20;     - WEBUI\_PORT=8080

&#x20;     - TORRENTING\_PORT=6881

&#x20;   ports:

&#x20;     - "6881:6881"

&#x20;     - "6881:6881/udp"

&#x20;   volumes:

&#x20;     - ./qbit-config:/config

&#x20;     - ${STAGING\_HOST\_DIR}:/downloads

&#x20;   restart: unless-stopped

&#x20;   mem\_limit: 1g



&#x20; agent:

&#x20;   build:

&#x20;     context: ..

&#x20;     dockerfile: docker/Dockerfile

&#x20;   container\_name: seans-worker-agent

&#x20;   env\_file: ../.env

&#x20;   volumes:

&#x20;     - ${STAGING\_HOST\_DIR}:/staging

&#x20;     - agent-state:/state

&#x20;   restart: unless-stopped

&#x20;   mem\_limit: 128m

&#x20;   depends\_on:

&#x20;     - qbittorrent



volumes:

&#x20; agent-state:

```

`STAGING\_HOST\_DIR` — абсолютный host-путь (например `/mnt/staging`), задаётся в `.env`.

Обрати внимание: `/downloads` у qbit и `/staging` у агента — один host-каталог.



Первый запуск qBittorrent: взять временный пароль из `docker compose logs qbittorrent`,

вписать в `.env` как `QBIT\_PASS`, перезапустить агент. Описать этот шаг в README.



\## Надёжность и правила реализации



\- Ни один путь не должен паниковать воркер целиком: задача фейлится, воркер живёт.

\- Все ошибки — обёрнутые `%w`, логи — структурные slog (key=value), уровни:

&#x20; DEBUG для poll-циклов, INFO для смен стадий, WARN для ретраев, ERROR для fail.

\- Лог каждой задачи должен начинаться строкой с task\_id и prefetch контекста.

\- Идемпотентность: повтор задачи с тем же task\_id должен завершаться успехом

&#x20; (cleanup в preparing это обеспечивает).

\- Контекст задачи отменяется через context.Context при shutdown.

\- Не хранить секреты в логах.

\- Версия бинаря: `-ldflags "-X main.version=..."`, выводится в логе при старте и

&#x20; отправляется в register.



\## Тесты



\- `qbit/client\_test.go`: httptest-сервер, эмулирующий auth + add + info + files +

&#x20; filePrio + delete; проверить login-куку, выставление priority=0/1, обработку `Fails.`

\- `engine/task\_test.go`: state machine на фейковых qbit/backend клиентах (интерфейсы),

&#x20; сценарии: успех, stall timeout, quota exceeded, metadata timeout.

\- `backend/client\_test.go`: register→claim→heartbeat→complete happy path + 401

&#x20; re-register retry.

\- Минимум: `go vet` чистый, `go test ./...` зелёный.



\## Критерии приёмки



1\. `make build` собирает агент; `make test` зелёный.

2\. `docker compose -f docker/docker-compose.yml up -d` поднимает qbit + agent.

3\. С `.env` для mock (mockbackend на `BACKEND\_URL`, `MOCK\_S3=true`): задача с ubuntu

&#x20;  .torrent скачивается, ненужные файлы skip'аются, файл появляется в

&#x20;  `/tmp/seans-s3-mock/{dest\_prefix}/`, complete уходит в mock backend.

4\. С реальными ключами reg.ru S3 файл появляется в bucket `seans` по заданному префиксу.

5\. Heartbeats видны в логах mock backend каждые \~60 сек с корректным прогрессом.

6\. `kill -TERM` агенту: без DRAIN — задачи fail(permanent=false) на backend; с

&#x20;  `DRAIN\_ON\_SHUTDOWN=true` — воркер дорабатывает текущую задачу и выходит.

7\. README позволяет развернуть новый воркер с нуля за 3 команды и содержит таблицу

&#x20;  всех env-переменных.

````



\---



\## Что дальше



1\. \*\*Закидываешь промт агенту\*\* → получаешь воркер + mock → прогоняешь e2e на ubuntu-торренте (сначала `MOCK\_S3=true`, потом с ключами reg.ru).

2\. \*\*Следующий компонент — backend\*\*, и его контракт уже наполовину зафиксирован этим промтом (эндпоинты `/v1/workers/\*`, `/v1/tasks/\*`), плюс добавятся: Kinopoisk-поиск, очередь задач (`SKIP LOCKED`), lease-expiry job, pre-signed GET для клиентов.

3\. Проверь в личном кабинете reg.ru, можно ли выдать \*\*отдельный ключ с доступом только к бакету `seans`\*\* — если да, компрометация воркера не даст доступа к остальным бакетам.



Когда воркер соберётся и первый файл ляжет в бакет — возвращайся, распишем промт для backend.

