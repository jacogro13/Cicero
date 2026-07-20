from __future__ import annotations

from collections.abc import Awaitable, Callable

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.events import DocumentEvent
from cicero.domain.ports.unit_of_work import UnitOfWork


class AdvanceDocument:
    """Handler for any pipeline event: re-enqueue the document id so its next stage
    runs off the request path (ADR-013/014).

    Enqueues an intent only — the edge derives the command from persisted status,
    so no command is synthesised in a handler (ADR-012).
    """

    def __init__(self, enqueue: Callable[[DocumentId], Awaitable[None]]) -> None:
        self._enqueue = enqueue

    async def __call__(self, event: DocumentEvent, uow: UnitOfWork) -> None:
        await self._enqueue(event.document_id)
