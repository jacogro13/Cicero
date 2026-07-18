from __future__ import annotations

from collections.abc import Awaitable, Callable

from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.events import DocumentUploaded
from cicero.domain.ports.unit_of_work import UnitOfWork


class EnqueueExtraction:
    """Handler for ``DocumentUploaded``: put the document on the job queue so
    extraction runs off the request path (ADR-013).

    It enqueues an *intent* (the document id) only — the queue worker issues the
    ``ExtractDocument`` command at the edge, so no command is synthesised inside a
    handler (ADR-012). The queue is injected as a bare ``enqueue`` callable, so the
    services layer stays clear of the concrete ``entrypoints`` queue.
    """

    def __init__(self, enqueue: Callable[[DocumentId], Awaitable[None]]) -> None:
        self._enqueue = enqueue

    async def __call__(self, event: DocumentUploaded, uow: UnitOfWork) -> None:
        await self._enqueue(event.document_id)
