import logging

import httpx
from fastapi import FastAPI

from feynman_api.config import Settings
from feynman_api.main import create_app


def _add_boom(app: FastAPI) -> None:
    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret-xyz")


async def test_500_has_cors_headers_for_allowed_origin(
    app: FastAPI, api_client: httpx.AsyncClient
) -> None:
    _add_boom(app)
    r = await api_client.get("/boom", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "secret-xyz" not in r.text


async def test_500_no_cors_for_other_origin(app: FastAPI, api_client: httpx.AsyncClient) -> None:
    _add_boom(app)
    r = await api_client.get("/boom", headers={"Origin": "http://evil.example"})
    assert r.status_code == 500
    assert "access-control-allow-origin" not in r.headers


async def test_cors_preflight_allows_csrf_header(api_client: httpx.AsyncClient) -> None:
    r = await api_client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-csrf-token",
        },
    )
    assert r.status_code == 200
    assert "x-csrf-token" in r.headers["access-control-allow-headers"].lower()


def test_log_level_applies_even_with_existing_handlers(test_settings: Settings) -> None:
    root = logging.getLogger()
    handler = logging.NullHandler()
    old_level = root.level
    root.addHandler(handler)
    try:
        create_app(test_settings.model_copy(update={"log_level": "DEBUG"}))
        assert root.level == logging.DEBUG
        assert handler in root.handlers
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
