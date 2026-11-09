import time

import httpx
from asgi_lifespan import LifespanManager
from pydantic import SecretStr

from feynman_api.config import Settings
from feynman_api.main import create_app


async def test_health_ok(api_client: httpx.AsyncClient) -> None:
    r = await api_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok", "version": "0.1.0"}


async def test_health_db_down_returns_503_fast(test_settings: Settings) -> None:
    settings = test_settings.model_copy(
        update={
            "database_url": SecretStr("postgresql+asyncpg://feynman_app:pw@127.0.0.1:1/feynman")
        }
    )
    app = create_app(settings)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            t0 = time.monotonic()
            r = await client.get("/health")
            elapsed = time.monotonic() - t0
    assert r.status_code == 503
    assert r.json() == {"status": "degraded", "db": "error", "version": "0.1.0"}
    assert elapsed < 3.0
    assert "127.0.0.1" not in r.text
    assert "pw" not in r.text


async def test_app_starts_without_db(test_settings: Settings) -> None:
    settings = test_settings.model_copy(
        update={
            "database_url": SecretStr("postgresql+asyncpg://feynman_app:pw@127.0.0.1:1/feynman")
        }
    )
    async with LifespanManager(create_app(settings)):
        pass
