.PHONY: sync lint test dev

sync:                 ## Install dependencies into the uv venv
	uv sync

lint:                 ## Check the hexagonal layering (import-linter, ADR-001)
	uv run lint-imports

test:                 ## Run the test suite
	uv run pytest

dev:                  ## Run the dev server (http://localhost:8000)
	uv run uvicorn pagemaster.entrypoints.main:app --reload
