"""The serial job queue: bounded background transport (ADR-013).

Workers drain ``DocumentId`` intents through an injected consumer, with at most
``concurrency`` jobs in flight; a failing job is isolated so the worker keeps going.
"""

from __future__ import annotations

import asyncio

from cicero.domain.document.document_id import DocumentId
from cicero.entrypoints.job_queue import JobQueue


async def _record(sink: list, value) -> None:
    sink.append(value)


class TestJobQueue:
    async def test_drains_enqueued_jobs_in_order_with_one_worker(self):
        processed: list[DocumentId] = []
        queue = JobQueue(concurrency=1)
        await queue.start(lambda document_id: _record(processed, document_id))

        ids = [DocumentId.new() for _ in range(5)]
        for document_id in ids:
            await queue.enqueue(document_id)
        await queue.join()
        await queue.stop()

        assert processed == ids

    async def test_concurrency_bounds_how_many_jobs_run_at_once(self):
        in_flight = 0
        peak = 0

        async def job(document_id: DocumentId) -> None:
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.02)  # hold the slot so overlap is observable
            in_flight -= 1

        queue = JobQueue(concurrency=2)
        await queue.start(job)
        for _ in range(6):
            await queue.enqueue(DocumentId.new())
        await queue.join()
        await queue.stop()

        assert peak == 2

    async def test_a_failing_job_does_not_stop_the_worker(self):
        processed: list[DocumentId] = []
        bad, good = DocumentId.new(), DocumentId.new()

        async def job(document_id: DocumentId) -> None:
            if document_id == bad:
                raise RuntimeError("boom")
            processed.append(document_id)

        queue = JobQueue(concurrency=1)
        await queue.start(job)
        await queue.enqueue(bad)
        await queue.enqueue(good)
        await queue.join()
        await queue.stop()

        assert processed == [good]
