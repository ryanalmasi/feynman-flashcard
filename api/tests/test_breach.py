import hashlib
import logging

import httpx
import pytest

from feynman_api.auth.breach import HibpBreachChecker, StaticBreachChecker

PW = "pw-under-test"
DIGEST = hashlib.sha1(PW.encode(), usedforsecurity=False).hexdigest().upper()
PREFIX, SUFFIX = DIGEST[:5], DIGEST[5:]


def checker(transport: httpx.MockTransport) -> HibpBreachChecker:
    return HibpBreachChecker(httpx.AsyncClient(transport=transport), timeout=2.0)


def respond(body: str, status: int = 200) -> HibpBreachChecker:
    return checker(httpx.MockTransport(lambda r: httpx.Response(status, text=body)))


async def test_hibp_sends_only_prefix_and_padding() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="")

    assert not await checker(httpx.MockTransport(handler)).is_breached(PW)
    (request,) = seen
    assert request.url.path == f"/range/{PREFIX}"
    assert request.url.host == "api.pwnedpasswords.com"
    assert request.headers["Add-Padding"] == "true"
    assert request.headers["User-Agent"] == "feynman-flashcard"
    assert SUFFIX not in str(request.url)
    assert DIGEST not in str(request.url)


async def test_hibp_match_with_count_is_breached() -> None:
    body = f"0000000000000000000000000000000000A:1\r\n{SUFFIX}:42\r\n"
    assert await respond(body).is_breached(PW)


async def test_hibp_padding_line_with_zero_count_not_breached() -> None:
    assert not await respond(f"{SUFFIX}:0\r\n").is_breached(PW)


async def test_hibp_timeout_fails_open(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with caplog.at_level(logging.WARNING):
        assert not await checker(httpx.MockTransport(handler)).is_breached(PW)
    assert "HIBP check unavailable" in caplog.text
    assert "ReadTimeout" in caplog.text
    assert PW not in caplog.text


async def test_hibp_500_fails_open(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert not await respond(f"{SUFFIX}:42", status=500).is_breached(PW)
    assert "HIBP check unavailable" in caplog.text


async def test_static_checker() -> None:
    s = StaticBreachChecker({"bad"})
    assert await s.is_breached("bad")
    assert not await s.is_breached("good")
