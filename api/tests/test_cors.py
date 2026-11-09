import httpx


async def _preflight(client: httpx.AsyncClient, origin: str) -> httpx.Response:
    return await client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


async def test_cors_allows_web_origin(api_client: httpx.AsyncClient) -> None:
    r = await _preflight(api_client, "http://localhost:5173")
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert r.headers["access-control-allow-credentials"] == "true"


async def test_cors_rejects_other_origin(api_client: httpx.AsyncClient) -> None:
    r = await _preflight(api_client, "http://evil.example")
    assert "access-control-allow-origin" not in r.headers
