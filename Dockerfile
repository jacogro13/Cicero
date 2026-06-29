FROM python:3.12-slim

# uv for dependency management (same toolchain as local dev / CI).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependencies first (cached until pyproject/lock change), then the source.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8000

# The app provisions its schema + bucket on startup (ADR-010), so no entrypoint
# migration step — just run it.
CMD ["uv", "run", "uvicorn", "cicero.entrypoints.main:app", "--host", "0.0.0.0", "--port", "8000"]
