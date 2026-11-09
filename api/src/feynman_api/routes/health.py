import asyncio
import logging
from importlib.metadata import version
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from feynman_api.config import Settings
from feynman_api.db import get_engine

logger = logging.getLogger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "error"]
    version: str


async def _probe(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def health(
    request: Request, engine: Annotated[AsyncEngine, Depends(get_engine)]
) -> HealthResponse | JSONResponse:
    settings: Settings = request.app.state.settings
    app_version = version("feynman-api")
    try:
        await asyncio.wait_for(_probe(engine), settings.health_db_timeout_seconds)
    except Exception as exc:
        # Log only the exception type: messages can carry connection details.
        logger.warning("Health check database probe failed (%s)", type(exc).__name__)
        body = HealthResponse(status="degraded", db="error", version=app_version)
        return JSONResponse(status_code=503, content=body.model_dump())
    return HealthResponse(status="ok", db="ok", version=app_version)
