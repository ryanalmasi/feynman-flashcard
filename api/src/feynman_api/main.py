import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from feynman_api.auth.breach import BreachChecker, HibpBreachChecker, StaticBreachChecker
from feynman_api.clock import Clock, system_clock
from feynman_api.config import Settings
from feynman_api.db import create_engine, create_sessionmaker
from feynman_api.errors import ServerErrorJSONMiddleware, register_error_handlers
from feynman_api.routes.auth import router as auth_router
from feynman_api.routes.flashcards import router as flashcards_router
from feynman_api.routes.health import router as health_router
from feynman_api.routes.study_sets import router as study_sets_router
from feynman_api.storage import FileStore, LocalFileStore


def create_app(
    settings: Settings | None = None,
    *,
    file_store: FileStore | None = None,
    breach_checker: BreachChecker | None = None,
    clock: Clock | None = None,
) -> FastAPI:
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
        hibp_client: httpx.AsyncClient | None = None
        if breach_checker is None:
            if settings.hibp_enabled:
                hibp_client = httpx.AsyncClient()
                app.state.breach_checker = HibpBreachChecker(
                    hibp_client, settings.hibp_timeout_seconds
                )
            else:
                app.state.breach_checker = StaticBreachChecker()
        try:
            yield
        finally:
            if hibp_client is not None:
                await hibp_client.aclose()
            await engine.dispose()

    app = FastAPI(title="Feynman Flashcard API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.file_store = store
    app.state.clock = clock or system_clock
    if breach_checker is not None:
        app.state.breach_checker = breach_checker
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
    app.include_router(auth_router)
    app.include_router(study_sets_router)
    app.include_router(flashcards_router)
    return app
