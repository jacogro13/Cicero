.PHONY: sync lint test integration dev

sync:                 ## Install dependencies into the uv venv
	uv sync

lint:                 ## Check the hexagonal layering (import-linter, ADR-001)
	uv run lint-imports

test:                 ## Run the fast suite (unit + API; no Docker)
	uv run pytest --ignore=tests/integration

integration:          ## Run integration tests against real infra (needs Docker)
	uv run pytest tests/integration

dev:                  ## Run the dev server (http://localhost:8000)
	uv run uvicorn pagemaster.entrypoints.main:app --reload
