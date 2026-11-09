import logging
import secrets
from collections.abc import AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from conftest import ORIGIN, auth_headers, register
from fastapi import FastAPI

from feynman_api.auth.sessions import SESSION_COOKIE

pytestmark = pytest.mark.usefixtures("clean_db")


@pytest.fixture
async def log_app(app: FastAPI) -> AsyncIterator[FastAPI]:
    async with LifespanManager(app):
        yield app


async def test_no_secrets_in_logs(log_app: FastAPI, caplog: pytest.LogCaptureFixture) -> None:
    sentinel = "Zq-" + secrets.token_hex(8) + "-9!"
    caplog.set_level(logging.DEBUG)
    transport = httpx.ASGITransport(app=log_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await register(client, password=sentinel, birth_year=1987, birth_month=7)
        assert r.status_code == 201
        tokens = {r.json()["csrf_token"], client.cookies[SESSION_COOKIE]}
        r = await client.post(
            "/auth/login", json={"email": "a@example.com", "password": sentinel}, headers=ORIGIN
        )
        assert r.status_code == 200
        tokens |= {r.json()["csrf_token"], client.cookies[SESSION_COOKIE]}
        assert (await client.get("/auth/session")).status_code == 200
        headers = await auth_headers(client)
        assert (await client.post("/auth/logout", headers=headers)).status_code == 204
        r = await client.post(
            "/auth/login", json={"email": "a@example.com", "password": sentinel}, headers=ORIGIN
        )
        tokens |= {r.json()["csrf_token"], client.cookies[SESSION_COOKIE]}
        headers = await auth_headers(client)
        r = await client.request(
            "DELETE", "/auth/account", json={"password": sentinel}, headers=headers
        )
        assert r.status_code == 204
    assert "user registered" in caplog.text  # positive control
    assert sentinel not in caplog.text
    assert "birth_" not in caplog.text
    assert "a@example.com" not in caplog.text
    for token in tokens:
        assert token not in caplog.text
