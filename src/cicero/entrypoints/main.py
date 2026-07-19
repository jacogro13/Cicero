from contextlib import asynccontextmanager

from fastapi import FastAPI

from cicero.entrypoints.dependencies import (
    build_message_bus,
    dispose_engine,
    get_uow_factory,
    make_extraction_consumer,
    provision_infrastructure,
)
from cicero.entrypoints.errors import register_exception_handlers
from cicero.entrypoints.job_queue import JobQueue
from cicero.entrypoints.job_recovery import reconcile_processing_documents
from cicero.entrypoints.routers.documents import router as documents_router
from cicero.entrypoints.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Provision the schema + bucket the adapters assume (ADR-010), then build the
    # process-wide bus and job queue (ADR-013): the worker drains extraction off the
    # request path, and any document left PROCESSING by a restart is re-enqueued.
    # Not entered by the fast suite's plain TestClient.
    await provision_infrastructure()
    queue = JobQueue(concurrency=get_settings().job_queue_concurrency)
    bus = build_message_bus(queue)
    app.state.bus = bus
    await queue.start(make_extraction_consumer(bus))
    await reconcile_processing_documents(queue, get_uow_factory())
    yield
    await queue.stop()
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
