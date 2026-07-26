"""ADR-024: `alembic upgrade head` builds the schema `orm.metadata` describes.

The migration baseline is the single schema truth alongside the models; this proves
the two agree — and that ADR-021's composite summaries key survives the baseline.
"""

from __future__ import annotations

import anyio
from sqlalchemy import Connection, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from cicero.adapters.persistence.migrations import upgrade_to_head
from cicero.adapters.persistence.orm import metadata


def _reset(conn: Connection) -> None:
    conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    for table in reversed(metadata.sorted_tables):
        conn.execute(text(f'DROP TABLE IF EXISTS "{table.name}" CASCADE'))
    conn.execute(text("DROP TYPE IF EXISTS document_status"))


def _reflect(conn: Connection) -> tuple[set[str], set[str], set[str]]:
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    summaries_pk = inspector.get_pk_constraint("summaries")["constrained_columns"]
    document_columns = {col["name"] for col in inspector.get_columns("documents")}
    return tables, set(summaries_pk), document_columns


async def test_upgrade_head_builds_the_mapped_schema(postgres_url: str) -> None:
    engine = create_async_engine(postgres_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(_reset)

        # Off the event loop, as the app runs it: Alembic's env spins its own loop.
        await anyio.to_thread.run_sync(upgrade_to_head, postgres_url)

        async with engine.connect() as conn:
            tables, summaries_pk, document_columns = await conn.run_sync(_reflect)

        assert set(metadata.tables) <= tables
        # ADR-021's composite key is present from the baseline, not a later ALTER.
        assert summaries_pk == {"document_id", "position"}
        # ADR-026's `kind` (0002) and ADR-027's `source_url` (0003) are ALTER columns,
        # both reached by upgrade head.
        assert {"kind", "source_url"} <= document_columns
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(_reset)
        await engine.dispose()
