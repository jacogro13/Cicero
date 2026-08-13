"""The statement deadline of ADR-033, against a real Postgres.

The deadline is asyncpg's, not SQLAlchemy's, so only a real driver against a real
server can show that a statement which outlives it raises instead of hanging.
"""

import time

import pytest
from sqlalchemy import text

from cicero.adapters.persistence.engine import EnginePolicy, make_engine


class TestStatementDeadline:
    async def test_a_statement_past_the_deadline_raises_rather_than_hangs(
        self, postgres_url: str
    ):
        engine = make_engine(postgres_url, EnginePolicy(command_timeout=0.5))
        started = time.monotonic()

        try:
            with pytest.raises(TimeoutError):
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT pg_sleep(10)"))
        finally:
            await engine.dispose()

        assert time.monotonic() - started < 5.0

    async def test_a_statement_inside_the_deadline_still_returns(
        self, postgres_url: str
    ):
        engine = make_engine(postgres_url, EnginePolicy(command_timeout=5.0))

        try:
            async with engine.connect() as conn:
                assert (await conn.execute(text("SELECT 1"))).scalar() == 1
        finally:
            await engine.dispose()
