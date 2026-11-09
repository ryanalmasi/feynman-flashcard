import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from feynman_api.config import Settings
from feynman_api.db import create_engine, create_sessionmaker
from feynman_api.errors import ServerErrorJSONMiddleware, register_error_handlers
from feynman_api.routes.health import router as health_router
from feynman_api.storage import FileStore, LocalFileStore


def create_app(settings: Settings | None = None, *, file_store: FileStore | None = None) -> FastAPI:
    settings = settings or Settings()
    default_store = file_store is None
    store: FileStore = file_store or LocalFileStore(settings.upload_dir)
    logging.basicConfig(level=settings.log_level)
    logging.getLogger().setLevel(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if default_store:
            settings.upload_dir.mkdir(parents=True, exist_ok=True)
        engine = create_engine(settings)
        app.state.engine = engine
        app.state.sessionmaker = create_sessionmaker(engine)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Feynman Flashcard API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.file_store = store
    # Last added is outermost: CORS wraps the 500 middleware so 500s carry CORS headers.
    app.add_middleware(ServerErrorJSONMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        expose_headers=["Retry-After"],
    )
    register_error_handlers(app)
    app.include_router(health_router)
    return app
