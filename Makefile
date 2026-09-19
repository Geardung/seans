.PHONY: up down migrate test seed logs lint

up:
	docker compose up --build -d

down:
	docker compose down

migrate:
	docker compose exec backend alembic upgrade head

test:
	docker compose exec backend uv run pytest -v

seed:
	docker compose exec backend uv run python scripts/seed.py

logs:
	docker compose logs -f backend

lint:
	uv run ruff check app/ tests/ scripts/
	uv run ruff format --check app/ tests/ scripts/

format:
	uv run ruff check --fix app/ tests/ scripts/
	uv run ruff format app/ tests/ scripts/