.PHONY: sync lint test integration dev up down migration \
        fe-install fe-dev fe-lint fe-test fe-build

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

migration:            ## Autogenerate a revision from model changes (m="msg"; needs DATABASE_URL)
	uv run alembic revision --autogenerate -m "$(m)"

fe-install:           ## Install the admin SPA's node dependencies (frontend/)
	cd frontend && npm install

fe-dev:               ## Run the admin SPA dev server (proxies /api to the host api on :8000)
	cd frontend && npm run dev

fe-lint:              ## Lint + typecheck the admin SPA
	cd frontend && npm run lint && npm run typecheck

fe-test:              ## Run the admin SPA tests (Vitest)
	cd frontend && npm run test

fe-build:             ## Build the admin SPA production bundle
	cd frontend && npm run build
