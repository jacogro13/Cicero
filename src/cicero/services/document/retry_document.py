from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.document.exceptions import DocumentNotFound
from cicero.domain.ports.unit_of_work import UnitOfWork


class RetryDocument:
    """Handler: return a failed document to ``UPLOADED`` so the pipeline picks it up
    again (ADR-030). The projections are left in place — the re-run overwrites them by
    key. Raises ``DocumentNotFound`` and ``DocumentNotRetryable``."""

    async def __call__(
        self, command: commands.RetryDocument, uow: UnitOfWork
    ) -> Document:
        async with uow:
            document = await uow.documents.find_by_id(command.document_id)
            if document is None:
                raise DocumentNotFound(command.document_id)
            document.retry()
            await uow.documents.save(document)
            await uow.commit()
        return document
