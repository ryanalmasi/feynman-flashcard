import hmac

from fastapi import Request

from feynman_api.config import Settings
from feynman_api.models import AuthSession

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def origin_allowed(request: Request, settings: Settings) -> bool:
    """A missing Origin header is not allowed."""
    origin = request.headers.get("origin")
    return origin is not None and origin in settings.cors_origins


def csrf_token_valid(request: Request, session: AuthSession) -> bool:
    supplied = request.headers.get("x-csrf-token")
    if not supplied:
        return False
    return hmac.compare_digest(supplied.encode(), session.csrf_token.encode())
