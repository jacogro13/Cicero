from cicero.domain.document import commands
from cicero.domain.document.document import Document
from cicero.domain.ports.unit_of_work import UnitOfWork


class ListDocuments:
    """Handler: return every stored document. A read — no deps, no commit (ADR-012)."""

    async def __call__(
        self, command: commands.ListDocuments, uow: UnitOfWork
    ) -> list[Document]:
        async with uow:
            return await uow.documents.find_all()
