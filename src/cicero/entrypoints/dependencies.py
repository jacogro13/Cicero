"""The composition root: settings → adapters → use cases (ADR-005, ADR-010).

Holds the one process-wide engine, builds the real `UnitOfWork` factory and the
`S3DocumentStorage` from settings, and provisions the schema + bucket at startup.
The infra providers (`get_uow_factory`, `get_document_storage`) are the swap point
API tests override with in-memory fakes, so the fast suite needs no infrastructure.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from cicero.adapters.persistence.engine import (
    create_schema,
    make_engine,
    make_session_factory,
)
from cicero.adapters.extraction.pymupdf import PyMuPDFExtractor
from cicero.adapters.persistence.unit_of_work import make_sqlalchemy_uow_factory
from cicero.adapters.storage.s3 import S3DocumentStorage
from cicero.domain.document import commands
from cicero.domain.document.events import DocumentUploaded
from cicero.domain.document.ports.document_extractor import DocumentExtractor
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory
from cicero.entrypoints.settings import Settings, get_settings
from cicero.services.document.delete_document import DeleteDocument
from cicero.services.document.extract_document import ExtractDocument
from cicero.services.document.list_documents import ListDocuments
from cicero.services.document.upload_document import UploadDocument
from cicero.services.messagebus import MessageBus

# One engine + session factory per process, created lazily and disposed on shutdown.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = make_engine(get_settings().database_url)
        _session_factory = make_session_factory(_engine)
    return _session_factory


async def dispose_engine() -> None:
    """Release the engine's connection pool at shutdown; reset for a clean restart."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = _session_factory = None


def _make_storage(settings: Settings) -> S3DocumentStorage:
    return S3DocumentStorage(
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
        bucket=settings.s3_bucket,
        region_name=settings.s3_region,
    )


async def provision_infrastructure() -> None:
    """Create the DB schema and ensure the bucket — idempotent startup (ADR-010)."""
    _get_session_factory()  # build the engine
    assert _engine is not None
    await create_schema(_engine)
    await _make_storage(get_settings()).ensure_bucket()


def get_uow_factory() -> UnitOfWorkFactory:
    return make_sqlalchemy_uow_factory(_get_session_factory())


def get_document_storage(
    settings: Settings = Depends(get_settings),
) -> DocumentStorage:
    return _make_storage(settings)


def get_document_extractor() -> DocumentExtractor:
    return PyMuPDFExtractor()


def bootstrap(
    uow_factory: UnitOfWorkFactory,
    storage: DocumentStorage,
    extractor: DocumentExtractor,
) -> MessageBus:
    """Wire deps into the handlers and build the command/event maps (ADR-011, ADR-012).

    Commands come from the routes (the edge); extraction is an internal reaction —
    the ``DocumentUploaded`` event handler — so upload *causes* it with no coupling.
    """
    return MessageBus(
        uow_factory,
        command_handlers={
            commands.UploadDocument: UploadDocument(storage),
            commands.ListDocuments: ListDocuments(),
            commands.DeleteDocument: DeleteDocument(storage),
        },
        event_handlers={DocumentUploaded: [ExtractDocument(storage, extractor)]},
    )


def get_message_bus(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    storage: DocumentStorage = Depends(get_document_storage),
    extractor: DocumentExtractor = Depends(get_document_extractor),
) -> MessageBus:
    return bootstrap(uow_factory, storage, extractor)
