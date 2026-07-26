"""Programmatic Alembic runner for startup provisioning (ADR-024).

The app runs ``alembic upgrade head`` in-process at startup instead of a create-only
``create_all``. Alembic is located by path (not the cwd-relative ``alembic.ini``), so
this works from the packaged image the same as from a checkout.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _config(database_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def upgrade_to_head(database_url: str) -> None:
    """Migrate the database at ``database_url`` up to the latest revision.

    Synchronous: Alembic's env runs its own async engine via ``asyncio.run``, so
    call this off the event loop (``anyio.to_thread.run_sync``) from async code.
    """
    command.upgrade(_config(database_url), "head")
