from cicero.domain.document.document import Document
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory


class ListDocuments:
    """Use case: return every stored document. A read — no commit needed."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> list[Document]:
        async with self._uow_factory() as uow:
            return await uow.documents.find_all()
