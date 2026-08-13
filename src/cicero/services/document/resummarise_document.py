from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.ports.unit_of_work import UnitOfWork


class ResummariseDocument:
    """Handler: discard a summarised document's summaries and send it back to
    ``EXTRACTED``, so the pipeline summarises it afresh (ADR-032). Discarding is the
    substance, not the reset — a surviving summary is one the re-run would skip
    (ADR-031). Raises ``DocumentNotFound`` and ``DocumentNotRetryable``."""

    async def __call__(
        self, command: commands.ResummariseDocument, uow: UnitOfWork
    ) -> Document:
        async with uow:
            document = await uow.documents.find_by_id(command.document_id)
            if document is None:
                raise DocumentNotFound(command.document_id)
            # Guard first: a refused request must not cost a book's summaries.
            document.resummarise()
            await uow.summaries.delete(command.document_id)
            await uow.documents.save(document)
            # One transaction, so no reader sees SUMMARISED with nothing to read.
            await uow.commit()
        return document
