from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.auth.breach import BreachChecker
from feynman_api.auth.csrf import UNSAFE_METHODS, csrf_token_valid, origin_allowed
from feynman_api.auth.sessions import SESSION_COOKIE, resolve_session
from feynman_api.clock import Clock, get_clock
from feynman_api.config import Settings
from feynman_api.db import get_session
from feynman_api.errors import csrf_failed, not_authenticated
from feynman_api.models import AuthSession, User

# Transaction note: current_user -> resolve_session COMMITS the request session (after a
# touch or lazy delete). Dependencies and handlers must therefore call auth helpers before
# making pending writes; get_session itself never commits.


@dataclass
class CurrentUser:
    user: User
    session: AuthSession


def get_breach_checker(request: Request) -> BreachChecker:
    return cast(BreachChecker, request.app.state.breach_checker)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def require_origin(request: Request) -> None:
    if not origin_allowed(request, _settings(request)):
        raise csrf_failed()


async def current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> CurrentUser:
    """Authenticate first (401), then CSRF for unsafe methods (403)."""
    session = await resolve_session(db, request.cookies.get(SESSION_COOKIE), clock())
    user = await db.get(User, session.user_id) if session is not None else None
    if session is None or user is None:
        raise not_authenticated()
    if request.method in UNSAFE_METHODS and not (
        origin_allowed(request, _settings(request)) and csrf_token_valid(request, session)
    ):
        raise csrf_failed()
    return CurrentUser(user=user, session=session)
