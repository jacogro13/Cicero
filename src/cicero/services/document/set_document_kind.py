from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.ports.unit_of_work import UnitOfWork


class SetDocumentKind:
    """Handler: correct a document's browsing classification — no pipeline stage
    reads ``kind``, so this raises no event (ADR-026). Raises ``DocumentNotFound``."""

    async def __call__(
        self, command: commands.SetDocumentKind, uow: UnitOfWork
    ) -> Document:
        async with uow:
            document = await uow.documents.find_by_id(command.document_id)
            if document is None:
                raise DocumentNotFound(command.document_id)
            document.set_kind(command.kind)
            await uow.documents.save(document)
            await uow.commit()
        return document
