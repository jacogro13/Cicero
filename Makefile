.PHONY: sync lint test integration dev up down

sync:                 ## Install dependencies into the uv venv
	uv sync

lint:                 ## Check the hexagonal layering (import-linter, ADR-001)
	uv run lint-imports

test:                 ## Run the fast suite (unit + API; no Docker)
	uv run pytest --ignore=tests/integration

integration:          ## Run integration tests against real infra (needs Docker)
	uv run pytest tests/integration

up:                   ## Run the whole stack (api + Postgres + MinIO) in Docker
	docker compose up --build

down:                 ## Stop the stack and remove its volumes
	docker compose down -v

dev:                  ## Run the app on the host (needs Postgres + MinIO; see .env.example)
	uv run uvicorn cicero.entrypoints.main:app --reload
