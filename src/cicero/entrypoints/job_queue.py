from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from cicero.domain.document.document_id import DocumentId

logger = logging.getLogger(__name__)

JobConsumer = Callable[[DocumentId], Awaitable[None]]


class JobQueue:
    """Process-wide serial queue for slow background jobs (ADR-013).

    Workers drain it at a fixed ``concurrency`` (default 1), bounding how many heavy
    jobs run at once. Created per event loop and held on ``app.state``, never a module
    global. Each entry is a ``DocumentId`` intent the ``consumer`` turns into a command.
    """

    def __init__(self, concurrency: int = 1) -> None:
        self._concurrency = max(1, concurrency)
        self._queue: asyncio.Queue[DocumentId] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []

    async def start(self, consumer: JobConsumer) -> None:
        """Spawn the worker tasks that drain the queue through ``consumer``.
        Idempotent; must run inside a running event loop."""
        if self._workers:
            return
        for n in range(self._concurrency):
            self._workers.append(
                asyncio.create_task(self._worker(n, consumer), name=f"job-worker-{n}")
            )
        logger.info("Job queue started with %d worker(s)", self._concurrency)

    async def enqueue(self, document_id: DocumentId) -> None:
        await self._queue.put(document_id)

    async def join(self) -> None:
        """Block until every enqueued job has finished — for tests and shutdown drain."""
        await self._queue.join()

    async def stop(self) -> None:
        """Cancel the workers and wait for them to unwind. Idempotent."""
        for worker in self._workers:
            worker.cancel()
        for worker in self._workers:
            try:
                await worker
            except asyncio.CancelledError:
                pass
        self._workers = []
        logger.info("Job queue stopped")

    async def _worker(self, n: int, consumer: JobConsumer) -> None:
        while True:
            document_id = await self._queue.get()
            try:
                await consumer(document_id)
            except asyncio.CancelledError:
                # Unwind on shutdown; the finally still balances a concurrent join().
                raise
            except Exception:
                # One bad job must not kill the worker — log and keep draining.
                logger.exception("Job failed id=%s (worker %d)", document_id, n)
            finally:
                self._queue.task_done()
