from starlette.requests import Request

from feynman_api.auth.csrf import csrf_token_valid, origin_allowed
from feynman_api.auth.dependencies import client_ip
from feynman_api.config import Settings
from feynman_api.models import AuthSession

SETTINGS = Settings(database_url="postgresql+asyncpg://x:x@h/d", _env_file=None)


def _req(headers: dict[str, str], client: tuple[str, int] | None = ("1.2.3.4", 1)) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": client,
        }
    )


def test_origin_allowed() -> None:
    assert origin_allowed(_req({"Origin": "http://localhost:5173"}), SETTINGS)
    assert not origin_allowed(_req({}), SETTINGS)
    assert not origin_allowed(_req({"Origin": "null"}), SETTINGS)
    assert not origin_allowed(_req({"Origin": "http://evil.example"}), SETTINGS)


def test_csrf_token_valid() -> None:
    good = "right-token"
    session = AuthSession()
    session.csrf_token = good
    assert csrf_token_valid(_req({"X-CSRF-Token": good}), session)
    assert not csrf_token_valid(_req({"X-CSRF-Token": "wrong"}), session)
    assert not csrf_token_valid(_req({"X-CSRF-Token": ""}), session)
    assert not csrf_token_valid(_req({}), session)


def test_client_ip() -> None:
    assert client_ip(_req({"X-Forwarded-For": "9.9.9.9"})) == "1.2.3.4"
    assert client_ip(_req({}, client=None)) == "unknown"
