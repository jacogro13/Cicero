from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cicero.adapters.persistence.repository import PostgresDocumentRepository
from cicero.adapters.persistence.summary_read_model import PostgresSummaryReadModel
from cicero.domain.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory


class SqlAlchemyUnitOfWork(UnitOfWork):
    """``UnitOfWork`` over a SQLAlchemy ``AsyncSession`` (ADR-006).

    One ``async with`` block is one session/transaction spanning the document
    repository and the summaries read model. Commit is explicit; any other exit
    rolls back (ADR-003).
    """

    documents: PostgresDocumentRepository
    summaries: PostgresSummaryReadModel

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.documents = PostgresDocumentRepository(self._session)
        self.summaries = PostgresSummaryReadModel(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Detach loaded instances with their state so a returned Document stays
        # usable after the block; then roll back by default — writes not explicitly
        # committed are discarded (clean exit or error), and rollback would
        # otherwise expire those instances, breaking access once detached.
        self._session.expunge_all()
        await self.rollback()
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


def make_sqlalchemy_uow_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> UnitOfWorkFactory:
    """Return a zero-arg factory yielding fresh UoWs over one session factory."""

    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    return factory
