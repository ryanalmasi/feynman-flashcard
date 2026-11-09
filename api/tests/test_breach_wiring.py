import httpx
from asgi_lifespan import LifespanManager

from feynman_api.auth.breach import HibpBreachChecker, StaticBreachChecker
from feynman_api.config import Settings
from feynman_api.main import create_app


async def test_injected_checker_stored(app) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(app.state.breach_checker, StaticBreachChecker)
    assert await app.state.breach_checker.is_breached("breached-password-123")


async def test_default_disabled_is_static(migrated_db: None, test_settings: Settings) -> None:
    app = create_app(test_settings)
    async with LifespanManager(app):
        assert isinstance(app.state.breach_checker, StaticBreachChecker)


async def test_default_enabled_is_hibp_and_client_closed(
    migrated_db: None, test_settings: Settings
) -> None:
    s = test_settings.model_copy(update={"hibp_enabled": True})
    app = create_app(s)
    async with LifespanManager(app):
        checker = app.state.breach_checker
        assert isinstance(checker, HibpBreachChecker)
        client: httpx.AsyncClient = checker._client
    assert client.is_closed


async def test_get_breach_checker_dependency(app) -> None:  # type: ignore[no-untyped-def]
    from starlette.requests import Request

    from feynman_api.auth.deps import get_breach_checker

    request = Request({"type": "http", "app": app, "headers": []})
    assert get_breach_checker(request) is app.state.breach_checker
