from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.ports.unit_of_work import UnitOfWork


class IngestUrl:
    """Handler: create a document from a URL and persist it — no blob to store
    first, so unlike ``UploadDocument`` this is a straight persist (ADR-027)."""

    async def __call__(self, command: commands.IngestUrl, uow: UnitOfWork) -> Document:
        document = Document.create_from_url(command.url, command.kind or DocumentKind.ARTICLE)
        async with uow:
            await uow.documents.save(document)
            await uow.commit()
        return document
