from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.ports.unit_of_work import UnitOfWork


class IngestUrl:
    """Handler: create an ARTICLE from a URL and persist it (ADR-027).

    Unlike ``UploadDocument`` there is no blob to store first — the link is the
    source, fetched later by the extract stage — so this is a straight persist.
    """

    async def __call__(self, command: commands.IngestUrl, uow: UnitOfWork) -> Document:
        document = Document.create_from_url(command.url)
        async with uow:
            await uow.documents.save(document)
            await uow.commit()
        return document
