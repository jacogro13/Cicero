"""The UoW's contract before a transaction is opened.

The bus drains ``collect_new_events()`` after every message, including one whose
handler never opened a block — an enqueue-only subscriber, say. The repositories
only exist inside a transaction, so the drain has to survive their absence.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cicero.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWork


class TestUnitOfWorkBeforeEntering:
    def test_collect_new_events_on_a_never_entered_uow_yields_nothing(self):
        uow = SqlAlchemyUnitOfWork(async_sessionmaker(class_=AsyncSession))

        assert list(uow.collect_new_events()) == []
