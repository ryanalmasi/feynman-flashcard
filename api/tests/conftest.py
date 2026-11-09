import os
from collections.abc import AsyncIterator

import httpx
import pytest
from dotenv import dotenv_values
from fastapi import FastAPI

from feynman_api.config import Settings
from feynman_api.main import create_app


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(".env").get("TEST_DATABASE_URL")
    return url or "postgresql+asyncpg://x:x@127.0.0.1:1/x"


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        database_url=_test_database_url(),
        environment="test",
        _env_file=None,
    )


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
