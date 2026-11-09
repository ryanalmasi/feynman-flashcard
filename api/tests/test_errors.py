import logging

import httpx
import pytest
from fastapi import FastAPI


async def test_unknown_route_404_shape(api_client: httpx.AsyncClient) -> None:
    r = await api_client.get("/nope")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found"
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["details"] is None
    assert set(body) == {"error"}


async def test_method_not_allowed_shape(app: FastAPI, api_client: httpx.AsyncClient) -> None:
    @app.get("/only-get")
    async def only_get() -> dict[str, int]:
        return {"ok": 1}

    r = await api_client.post("/only-get")
    assert r.status_code == 405
    assert r.json()["error"]["code"] == "method_not_allowed"


async def test_unhandled_500_hides_detail(
    app: FastAPI, api_client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret-detail-xyz")

    with caplog.at_level(logging.ERROR):
        r = await api_client.get("/boom")
    assert r.status_code == 500
    assert r.json()["error"] == {
        "code": "internal_error",
        "message": "Internal server error",
        "details": None,
    }
    assert "secret-detail-xyz" not in r.text
    assert "secret-detail-xyz" in caplog.text
    assert "Traceback" in caplog.text


async def test_validation_422_shape(app: FastAPI, api_client: httpx.AsyncClient) -> None:
    @app.get("/num")
    async def num(n: int) -> dict[str, int]:
        return {"n": n}

    r = await api_client.get("/num", params={"n": "abc"})
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]
    assert all({"loc", "msg"} <= set(d) for d in error["details"])


async def test_app_error_shape_and_headers(app: FastAPI, api_client: httpx.AsyncClient) -> None:
    from feynman_api.errors import AppError

    @app.get("/limited")
    async def limited() -> None:
        raise AppError(
            429, "rate_limited", "Too many attempts. Try again later.", headers={"Retry-After": "7"}
        )

    r = await api_client.get("/limited")
    assert r.status_code == 429
    assert r.headers["retry-after"] == "7"
    assert r.json() == {
        "error": {
            "code": "rate_limited",
            "message": "Too many attempts. Try again later.",
            "details": None,
        }
    }


def test_error_table_pinned() -> None:
    from feynman_api import errors

    rows = [
        (errors.not_authenticated(), 401, "not_authenticated", "Not signed in."),
        (errors.invalid_credentials(), 401, "invalid_credentials", "Invalid email or password."),
        (
            errors.csrf_failed(),
            403,
            "csrf_failed",
            "Request blocked. Refresh the page and try again.",
        ),
        (
            errors.registration_not_allowed(),
            403,
            "registration_not_allowed",
            "We couldn't create an account with the details provided.",
        ),
        (errors.email_taken(), 409, "email_taken", "An account with this email already exists."),
        (
            errors.password_breached(),
            422,
            "password_breached",
            "This password has appeared in a data breach. Choose a different one.",
        ),
        (errors.rate_limited(30), 429, "rate_limited", "Too many attempts. Try again later."),
        (errors.not_found(), 404, "not_found", "Not found."),
        (errors.file_too_large(), 413, "file_too_large", "This file is larger than 20 MB."),
        (
            errors.unsupported_file_type(),
            415,
            "unsupported_file_type",
            "Only PDF files can be uploaded.",
        ),
    ]
    assert len(rows) == 10
    for err, status, code, message in rows:
        assert (err.status, err.code, err.message) == (status, code, message)
    assert errors.rate_limited(30).headers == {"Retry-After": "30"}
    assert errors.rate_limited(0).headers == {"Retry-After": "1"}


async def test_unknown_route_message_matches_table(api_client: httpx.AsyncClient) -> None:
    r = await api_client.get("/nope")
    assert r.json() == {"error": {"code": "not_found", "message": "Not found.", "details": None}}
