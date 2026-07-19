from __future__ import annotations

from collections.abc import Awaitable, Callable

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.events import DocumentEvent
from cicero.domain.ports.unit_of_work import UnitOfWork


class AdvanceDocument:
    """Handler for any pipeline event: put the document back on the job queue so its
    next stage runs off the request path (ADR-013/014).

    It enqueues an *intent* (the document id) only, and names no stage — the queue
    consumer at the edge reads the document's persisted status back and derives the
    command from it, so no command is synthesised inside a handler (ADR-012). One
    subscription per stage is therefore the whole cost of extending the pipeline. The
    queue is injected as a bare ``enqueue`` callable, so the services layer stays clear
    of the concrete ``entrypoints`` queue.
    """

    def __init__(self, enqueue: Callable[[DocumentId], Awaitable[None]]) -> None:
        self._enqueue = enqueue

    async def __call__(self, event: DocumentEvent, uow: UnitOfWork) -> None:
        await self._enqueue(event.document_id)
