"""The composition root: settings → adapters → use cases (ADR-005, ADR-010, ADR-013).

Owns the process-wide engine and builds the adapters from settings. The bus is
assembled once in the lifespan; tests swap it at the `get_message_bus` seam.
"""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from cicero.adapters.extraction.pymupdf import PyMuPDFExtractor
from cicero.adapters.persistence.engine import (
    create_schema,
    make_engine,
    make_session_factory,
)
from cicero.adapters.persistence.unit_of_work import make_sqlalchemy_uow_factory
from cicero.adapters.storage.s3 import S3DocumentStorage
from cicero.adapters.summarization.mock import MockSummarizer
from cicero.adapters.summarization.openai import OpenAISummarizer
from cicero.domain.document import commands
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.events import DocumentUploaded, ExtractionCompleted
from cicero.domain.document.ports.document_extractor import DocumentExtractor
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.document.ports.document_summarizer import DocumentSummarizer
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory
from cicero.entrypoints.job_queue import JobQueue
from cicero.entrypoints.settings import Settings, get_settings
from cicero.services.document.advance_document import AdvanceDocument
from cicero.services.document.delete_document import DeleteDocument
from cicero.services.document.extract_document import ExtractDocument
from cicero.services.document.summarise_document import SummariseDocument
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


def get_document_extractor() -> DocumentExtractor:
    return PyMuPDFExtractor()


def get_document_summarizer() -> DocumentSummarizer:
    return make_summarizer(get_settings())


def make_summarizer(settings: Settings) -> DocumentSummarizer:
    """Select the summarizer from config: an OpenAI-compatible endpoint when
    ``LLM_BASE_URL`` is set, else the zero-config mock (ADR-016, ADR-018)."""
    if settings.llm_base_url:
        return OpenAISummarizer(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
        )
    return MockSummarizer()


def bootstrap(
    uow_factory: UnitOfWorkFactory,
    storage: DocumentStorage,
    extractor: DocumentExtractor,
    summarizer: DocumentSummarizer,
    queue: JobQueue,
) -> MessageBus:
    """Wire deps into the handlers and build the command/event maps (ADR-011→016).

    Commands come from the edge; each slow stage's completion event re-enqueues the
    document via ``AdvanceDocument``, so upload causes extraction causes summarization.
    """
    return MessageBus(
        uow_factory,
        command_handlers={
            commands.UploadDocument: UploadDocument(storage),
            commands.DeleteDocument: DeleteDocument(storage),
            commands.ExtractDocument: ExtractDocument(storage, extractor),
            commands.SummariseDocument: SummariseDocument(storage, summarizer),
        },
        event_handlers={
            DocumentUploaded: [AdvanceDocument(queue.enqueue)],
            ExtractionCompleted: [AdvanceDocument(queue.enqueue)],
        },
    )


def build_message_bus(queue: JobQueue) -> MessageBus:
    """Assemble the bus from the real adapters — called once in the lifespan."""
    settings = get_settings()
    return bootstrap(
        get_uow_factory(),
        _make_storage(settings),
        get_document_extractor(),
        get_document_summarizer(),
        queue,
    )


def get_message_bus(request: Request) -> MessageBus:
    """Return the process-wide bus built in the lifespan (ADR-013). Tests override
    this with a fake-wired bus (``bootstrap`` over fakes)."""
    return request.app.state.bus
