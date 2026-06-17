from fastapi import FastAPI

from pagemaster.entrypoints.routers.documents import router as documents_router


def create_app() -> FastAPI:
    app = FastAPI(title="PageMaster", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(documents_router, prefix="/api")

    return app


app = create_app()
