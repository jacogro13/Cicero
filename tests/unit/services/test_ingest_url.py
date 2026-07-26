"""Ingest a web article by URL → an ARTICLE document, driven through the bus (ADR-027).

No blob is stored at ingest — the URL is the source the worker fetches later; the
document enters the same pipeline as an upload (the `DocumentUploaded` event).
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.document_status import DocumentStatus
from cicero.domain.document.exceptions import InvalidDocumentUrl
from cicero.services.document.ingest_url import IngestUrl
from cicero.services.messagebus import MessageBus

from tests.fakes import make_in_memory_uow_factory

_URL = "https://example.com/blog/clean-architecture"


def _bus(uow_factory) -> MessageBus:
    return MessageBus(
        uow_factory,
        command_handlers={commands.IngestUrl: IngestUrl()},
        event_handlers={},
    )


class TestIngestUrl:
    async def test_creates_an_article_in_uploaded_status(self):
        document = await _bus(make_in_memory_uow_factory()).handle(
            commands.IngestUrl(url=_URL)
        )

        assert document.kind is DocumentKind.ARTICLE
        assert document.status is DocumentStatus.UPLOADED

    async def test_persists_the_document_with_its_source_url(self):
        uow_factory = make_in_memory_uow_factory()

        document = await _bus(uow_factory).handle(commands.IngestUrl(url=_URL))

        async with uow_factory() as uow:
            fetched = await uow.documents.find_by_id(document.id)
        assert fetched == document
        assert fetched.source_url == _URL

    async def test_an_invalid_url_persists_no_document(self):
        store: dict = {}
        bus = _bus(make_in_memory_uow_factory(store))

        with pytest.raises(InvalidDocumentUrl):
            await bus.handle(commands.IngestUrl(url="ftp://example.com/file"))

        assert store == {}
