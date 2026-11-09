import uuid
from typing import Any

import httpx
import pytest
from conftest import ORIGIN
from fastapi import FastAPI
from fastapi.routing import APIRoute

from feynman_api.auth.csrf import UNSAFE_METHODS

pytestmark = pytest.mark.usefixtures("clean_db")
OPEN_ROUTES = {("POST", "/auth/register"), ("POST", "/auth/login")}
EVIL = {"Origin": "http://evil.example"}


def _unsafe_routes(app: FastAPI) -> list[tuple[str, str]]:
    # FastAPI wraps included routers lazily (app.routes holds opaque entries), so the
    # generated OpenAPI paths are the reliable enumeration of every registered route.
    paths = app.openapi()["paths"]
    return sorted(
        (method.upper(), path)
        for path, item in paths.items()
        for method in item
        if method.upper() in UNSAFE_METHODS
    )


def _walk(routes: Any) -> list[APIRoute]:
    found: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
        nested = getattr(route, "original_router", None)
        if nested is not None:
            found.extend(_walk(nested.routes))
    return found


def _fill(path: str) -> str:
    return "/".join(str(uuid.uuid4()) if p.startswith("{") else p for p in path.split("/"))


async def test_every_unsafe_route_enforces_origin_and_csrf(
    app: FastAPI, user_client: httpx.AsyncClient
) -> None:
    routes = _unsafe_routes(app)
    assert routes and ("POST", "/auth/logout") in routes
    hidden = [
        (sorted(r.methods or []), r.path)
        for r in _walk(app.routes)
        if not r.include_in_schema and (r.methods or set()) & UNSAFE_METHODS
    ]
    assert not hidden, f"unsafe routes outside the OpenAPI schema skip the matrix: {hidden}"
    token = (await user_client.get("/auth/session")).json()["csrf_token"]
    for method, path in routes:
        url = _fill(path)
        good = {"X-CSRF-Token": token}
        r = await user_client.request(method, url, json={}, headers=good)
        assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed", (method, path)
        r = await user_client.request(method, url, json={}, headers=good | EVIL)
        assert r.status_code == 403, (method, path)
        assert r.json()["error"]["code"] == "csrf_failed", (method, path, "evil origin")
        if (method, path) in OPEN_ROUTES:
            continue
        r = await user_client.request(method, url, json={}, headers=ORIGIN)
        assert r.status_code == 403, (method, path, "no token")
        assert r.json()["error"]["code"] == "csrf_failed", (method, path, "no token")
        r = await user_client.request(
            method, url, json={}, headers=ORIGIN | {"X-CSRF-Token": "wrong"}
        )
        assert r.status_code == 403, (method, path, "wrong token")
        assert r.json()["error"]["code"] == "csrf_failed", (method, path, "wrong token")
