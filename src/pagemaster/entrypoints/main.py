from contextlib import asynccontextmanager

from fastapi import FastAPI

from pagemaster.entrypoints.dependencies import dispose_engine, provision_infrastructure
from pagemaster.entrypoints.errors import register_exception_handlers
from pagemaster.entrypoints.routers.documents import router as documents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Provision the schema + bucket the adapters assume, then release the engine
    # on shutdown (ADR-010). Not entered by the fast suite's plain TestClient.
    await provision_infrastructure()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(title="PageMaster", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(documents_router, prefix="/api")
    register_exception_handlers(app)

    return app


app = create_app()
