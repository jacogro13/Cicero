"""Correct a document's kind after the fact — the ``SetDocumentKind`` handler (ADR-026).

kind is browsing-only, so this is a plain persisted mutation: no event, no pipeline
effect. An unknown id raises ``DocumentNotFound``.
"""

import pytest

from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.services.document.set_document_kind import SetDocumentKind
from cicero.services.messagebus import MessageBus

from tests.fakes import make_in_memory_uow_factory


def _bus(uow_factory) -> MessageBus:
    return MessageBus(
        uow_factory,
        command_handlers={commands.SetDocumentKind: SetDocumentKind()},
        event_handlers={},
    )


class TestSetDocumentKind:
    async def test_changes_the_persisted_kind(self):
        uow_factory = make_in_memory_uow_factory()
        document = Document.create("An Article", kind=DocumentKind.ARTICLE)
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.commit()

        await _bus(uow_factory).handle(
            commands.SetDocumentKind(document_id=document.id, kind=DocumentKind.BOOK)
        )

        async with uow_factory() as uow:
            corrected = await uow.documents.find_by_id(document.id)
        assert corrected.kind is DocumentKind.BOOK

    async def test_unknown_id_raises_document_not_found(self):
        with pytest.raises(DocumentNotFound):
            await _bus(make_in_memory_uow_factory()).handle(
                commands.SetDocumentKind(
                    document_id=DocumentId.new(), kind=DocumentKind.BOOK
                )
            )
