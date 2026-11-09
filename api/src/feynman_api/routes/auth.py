import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.auth import rate_limit
from feynman_api.auth.breach import BreachChecker
from feynman_api.auth.dependencies import (
    CurrentUser,
    client_ip,
    current_user,
    get_breach_checker,
    require_origin,
)
from feynman_api.auth.passwords import (
    hash_password,
    needs_rehash,
    verify_dummy,
    verify_password,
)
from feynman_api.auth.schemas import DeleteAccountIn, LoginIn, RegisterIn, SessionOut, UserOut
from feynman_api.auth.sessions import (
    SESSION_COOKIE,
    clear_session_cookie,
    create_session,
    delete_session,
    hash_token,
    set_session_cookie,
)
from feynman_api.clock import Clock, get_clock
from feynman_api.config import Settings
from feynman_api.db import get_session
from feynman_api.errors import (
    ErrorResponse,
    email_taken,
    invalid_credentials,
    password_breached,
    rate_limited,
    registration_not_allowed,
)
from feynman_api.models import AuthSession, Document, StudySet, User
from feynman_api.storage import FileStore, get_file_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

Db = Annotated[AsyncSession, Depends(get_session)]
Now = Annotated[Clock, Depends(get_clock)]
MIN_AGE = 13
MAX_AGE_YEARS = 120


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _session_out(user: User, csrf_token: str) -> SessionOut:
    return SessionOut(
        user=UserOut(id=user.id, email=user.email, created_at=user.created_at),
        csrf_token=csrf_token,
    )


@router.post(
    "/register",
    status_code=201,
    response_model=SessionOut,
    dependencies=[Depends(require_origin)],
    responses={
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def register(
    body: RegisterIn,
    request: Request,
    response: Response,
    db: Db,
    clock: Now,
    breach_checker: Annotated[BreachChecker, Depends(get_breach_checker)],
) -> SessionOut:
    settings = _settings(request)
    now = clock()
    await rate_limit.prune(db, now)
    result = await rate_limit.hit(
        db,
        rate_limit.ip_key("register:ip:", client_ip(request)),
        settings.register_ip_limit,
        timedelta(seconds=settings.register_window_seconds),
        now,
    )
    if not result.allowed:
        raise rate_limited(result.retry_after)

    today = now.date()
    if not today.year - MAX_AGE_YEARS <= body.birth_year <= today.year:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "birth_year"),
                    "msg": "Birth year is out of range.",
                    "input": None,
                }
            ]
        )
    age = today.year - body.birth_year - (1 if body.birth_month > today.month else 0)
    if age < MIN_AGE:
        raise registration_not_allowed()

    # body.password is already NFKC-normalised by the schema.
    if await breach_checker.is_breached(body.password):
        raise password_breached()

    user = User(
        email=body.email,
        password_hash=await hash_password(body.password),
        age_verified_at=now,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise email_taken() from None
    token, session = await create_session(db, user.id, now)
    await db.commit()
    set_session_cookie(response, token, settings)
    logger.info("user registered id=%s", user.id)
    return _session_out(user, session.csrf_token)


@router.post(
    "/login",
    response_model=SessionOut,
    dependencies=[Depends(require_origin)],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: Db,
    clock: Now,
) -> SessionOut:
    settings = _settings(request)
    now = clock()
    window = timedelta(seconds=settings.login_window_seconds)
    await rate_limit.prune(db, now)
    ip_result = await rate_limit.hit(
        db,
        rate_limit.ip_key("login:ip:", client_ip(request)),
        settings.login_ip_limit,
        window,
        now,
    )
    if not ip_result.allowed:
        raise rate_limited(ip_result.retry_after)

    email_key = rate_limit.email_key(body.email)
    # Lockout is checked before any password verification.
    email_state = await rate_limit.peek(
        db, email_key, settings.login_email_failure_limit, window, now
    )
    if not email_state.allowed:
        raise rate_limited(email_state.retry_after)

    user = (
        await db.execute(select(User).where(func.lower(User.email) == body.email))
    ).scalar_one_or_none()
    stored_hash = user.password_hash if user is not None else None
    if user is None or stored_hash is None:
        # Count unknown emails too, so lockout behaviour doesn't reveal which emails exist.
        await verify_dummy(body.password)
        await rate_limit.hit(db, email_key, settings.login_email_failure_limit, window, now)
        raise invalid_credentials()
    if not await verify_password(stored_hash, body.password):
        await rate_limit.hit(db, email_key, settings.login_email_failure_limit, window, now)
        raise invalid_credentials()

    await rate_limit.clear(db, email_key)
    if needs_rehash(stored_hash):
        user.password_hash = await hash_password(body.password)
    incoming = request.cookies.get(SESSION_COOKIE)
    if incoming:
        await db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(incoming)))
    token, session = await create_session(db, user.id, now)
    await db.commit()
    set_session_cookie(response, token, settings)
    return _session_out(user, session.csrf_token)


@router.post(
    "/logout",
    status_code=204,
    response_class=Response,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def logout(
    request: Request, db: Db, current: Annotated[CurrentUser, Depends(current_user)]
) -> Response:
    await delete_session(db, current.session.id)
    await db.commit()
    response = Response(status_code=204)
    clear_session_cookie(response, _settings(request))
    return response


@router.get(
    "/session",
    response_model=SessionOut,
    responses={401: {"model": ErrorResponse}},
)
async def get_current_session(
    current: Annotated[CurrentUser, Depends(current_user)],
) -> SessionOut:
    return _session_out(current.user, current.session.csrf_token)


@router.delete(
    "/account",
    status_code=204,
    response_class=Response,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def delete_account(
    body: DeleteAccountIn,
    request: Request,
    db: Db,
    current: Annotated[CurrentUser, Depends(current_user)],
    file_store: Annotated[FileStore, Depends(get_file_store)],
) -> Response:
    user = current.user
    if user.password_hash is None or not await verify_password(user.password_hash, body.password):
        raise invalid_credentials()
    keys = list(
        (
            await db.execute(
                select(Document.storage_key)
                .join(StudySet, Document.study_set_id == StudySet.id)
                .where(StudySet.user_id == user.id)
            )
        ).scalars()
    )
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()
    for key in keys:
        try:
            await file_store.delete(key)
        except Exception as exc:
            logger.warning("failed to delete stored file (%s)", type(exc).__name__)
    response = Response(status_code=204)
    clear_session_cookie(response, _settings(request))
    return response
