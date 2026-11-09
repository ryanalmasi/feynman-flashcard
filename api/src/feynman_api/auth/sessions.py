import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.config import Settings
from feynman_api.models import AuthSession

SESSION_COOKIE = "feynman_session"
IDLE = timedelta(days=7)
ABSOLUTE = timedelta(days=30)
TOUCH_INTERVAL = timedelta(minutes=1)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


async def create_session(
    db: AsyncSession, user_id: uuid.UUID, now: datetime
) -> tuple[str, AuthSession]:
    """Create a session; the plain token is returned once and never stored."""
    await db.execute(
        delete(AuthSession).where(AuthSession.user_id == user_id, AuthSession.expires_at <= now)
    )
    token = secrets.token_urlsafe(32)
    session = AuthSession(
        user_id=user_id,
        token_hash=hash_token(token),
        csrf_token=secrets.token_urlsafe(32),
        created_at=now,
        last_seen_at=now,
        expires_at=now + ABSOLUTE,
    )
    db.add(session)
    await db.flush()
    return token, session


async def resolve_session(db: AsyncSession, token: str | None, now: datetime) -> AuthSession | None:
    """Look up a live session. Commits after a touch or a lazy delete."""
    if not token:
        return None
    session = (
        await db.execute(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    ).scalar_one_or_none()
    if session is None:
        return None
    if now >= session.expires_at or now >= session.last_seen_at + IDLE:
        await db.delete(session)
        await db.commit()
        return None
    if now - session.last_seen_at >= TOUCH_INTERVAL:
        session.last_seen_at = now
        await db.commit()
        await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    await db.execute(delete(AuthSession).where(AuthSession.id == session_id))


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(ABSOLUTE.total_seconds()),
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )
