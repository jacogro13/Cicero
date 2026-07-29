from contextlib import asynccontextmanager

from fastapi import FastAPI

from cicero.entrypoints.dependencies import (
    build_message_bus,
    dispose_engine,
    get_uow_factory,
    provision_infrastructure,
)
from cicero.entrypoints.enrichment_pipeline import make_enrichment_consumer
from cicero.entrypoints.errors import register_exception_handlers
from cicero.entrypoints.job_queue import JobQueue
from cicero.entrypoints.job_recovery import (
    reconcile_pending_enrichment,
    reconcile_unfinished_documents,
)
from cicero.entrypoints.pipeline import make_pipeline_consumer
from cicero.entrypoints.routers.documents import router as documents_router
from cicero.entrypoints.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Provision schema + bucket (ADR-010), build the process-wide bus and its two job
    # queues — the readability spine and the enrichment branch, each on its own
    # concurrency budget (ADR-013, ADR-028) — then re-enqueue whatever a restart left
    # unfinished on either axis (ADR-014). Not entered by the fast suite's plain TestClient.
    await provision_infrastructure()
    uow_factory = get_uow_factory()
    settings = get_settings()
    queue = JobQueue(concurrency=settings.job_queue_concurrency)
    enrich_queue = JobQueue(concurrency=settings.enrichment_queue_concurrency)
    bus = build_message_bus(queue, enrich_queue)
    app.state.bus = bus
    await queue.start(make_pipeline_consumer(bus, uow_factory))
    await enrich_queue.start(make_enrichment_consumer(bus, uow_factory))
    await reconcile_unfinished_documents(queue, uow_factory)
    await reconcile_pending_enrichment(enrich_queue, uow_factory)
    yield
    await queue.stop()
    await enrich_queue.stop()
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(title="Cicero", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(documents_router, prefix="/api")
    register_exception_handlers(app)

    return app


app = create_app()
