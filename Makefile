.PHONY: sync test dev

sync:                 ## Install dependencies into the uv venv
	uv sync

test:                 ## Run the test suite
	uv run pytest

dev:                  ## Run the dev server (http://localhost:8000)
	uv run uvicorn pagemaster.entrypoints.main:app --reload
