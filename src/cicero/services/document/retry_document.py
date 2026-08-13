from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.ports.unit_of_work import UnitOfWork


class RetryDocument:
    """Handler: send a failed document back to the furthest stage it completed, so the
    pipeline picks it up from there (ADR-030/032). The projections are left in place —
    they are what says how far it got, and the re-run overwrites or skips them rather
    than duplicating (ADR-031). Raises ``DocumentNotFound`` and ``DocumentNotRetryable``."""

    async def __call__(
        self, command: commands.RetryDocument, uow: UnitOfWork
    ) -> Document:
        async with uow:
            document = await uow.documents.find_by_id(command.document_id)
            if document is None:
                raise DocumentNotFound(command.document_id)
            # Chapter rows commit with ``mark_extracted``, after the blobs are written,
            # so having them *is* the record that extraction finished (ADR-032).
            chapters = await uow.chapters.list(command.document_id)
            document.retry(extraction_complete=bool(chapters))
            await uow.documents.save(document)
            await uow.commit()
        return document
