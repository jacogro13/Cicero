"""The engine's stated pool budget (ADR-033).

`create_async_engine` is happy to size its pool from library defaults; these pin the
numbers the app actually runs on. Constructing an engine opens no connection, so this
needs no database.
"""

from cicero.adapters.persistence.engine import DEFAULT_ENGINE, EnginePolicy, make_engine

_URL = "postgresql+asyncpg://user:password@db:5432/cicero"


class TestEnginePoolBudget:
    def test_pool_is_sized_from_the_policy(self):
        policy = EnginePolicy(pool_size=3, max_overflow=7, pool_timeout=11.0)

        pool = make_engine(_URL, policy).pool

        # `size()` is public; the other two read back only through private attributes.
        assert pool.size() == 3
        assert pool._max_overflow == 7
        assert pool._timeout == 11.0

    def test_an_engine_built_without_a_policy_still_states_its_numbers(self):
        pool = make_engine(_URL).pool

        assert pool.size() == DEFAULT_ENGINE.pool_size
        assert pool._max_overflow == DEFAULT_ENGINE.max_overflow
        assert pool._timeout == DEFAULT_ENGINE.pool_timeout
