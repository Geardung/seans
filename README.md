# Seans Backend

Self-hosted медиа-система: поиск фильмов (Кинопоиск), поиск торрентов,
автоматическое скачивание воркерами в S3, просмотр через presigned URL,
синхронный просмотр (watch-party) через WebSocket.

## Быстрый старт

```bash
cp .env.example .env
# Заполнить секреты в .env

make up       # поднять db + backend + adminer
make migrate  # применить миграции
make seed     # демо-данные
```

- API: http://localhost:8000
- Healthcheck: http://localhost:8000/healthz
- Adminer: http://localhost:8081

## Команды

| Команда | Описание |
|---------|----------|
| `make up` | Собрать и запустить все сервисы |
| `make down` | Остановить все сервисы |
| `make migrate` | Применить миграции Alembic |
| `make test` | Запустить тесты |
| `make seed` | Загрузить демо-данные |
| `make logs` | Логи backend |
| `make lint` | Проверка ruff |
| `make format` | Форматирование ruff |

## Стек

- Python 3.12, FastAPI, Pydantic v2
- SQLAlchemy 2.0 async (asyncpg), Alembic
- PostgreSQL 16 (docker)
- S3 (Reg.ru) через boto3
- JWT авторизация
- Очередь задач в PostgreSQL (FOR UPDATE SKIP LOCKED)

## Milestones

- **M1** — скелет репо + docker-compose + healthcheck
- **M2** — схема БД + миграции + seed
- **M3** — авторизация (JWT)
- **M4** — S3-сервис + presigned URL
- **M5** — поиск Кинопоиск + кеш
- **M6** — поиск торрентов (mock + Jackett)
- **M7** — задачи + протокол воркеров + квоты + библиотека
- **M8** — WS-комнаты + история + оценки