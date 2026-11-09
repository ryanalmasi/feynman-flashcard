import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from feynman_api.auth.sessions import (
    ABSOLUTE,
    IDLE,
    SESSION_COOKIE,
    clear_session_cookie,
    create_session,
    delete_session,
    hash_token,
    resolve_session,
    set_session_cookie,
)
from feynman_api.config import Settings
from feynman_api.models import AuthSession, User

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


async def _user(db: AsyncSession, email: str = "s@example.com") -> User:
    user = User(email=email)
    db.add(user)
    await db.flush()
    return user


async def test_session_token_stored_only_hashed(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token, s = await create_session(db_session, user.id, T0)
    assert s.token_hash == hashlib.sha256(token.encode()).digest()
    assert s.token_hash == hash_token(token)
    row = (
        await db_session.execute(text("select * from auth_sessions where id = :i"), {"i": s.id})
    ).one()
    assert all(token not in str(v) for v in row)
    assert s.created_at == s.last_seen_at == T0
    assert s.expires_at == T0 + ABSOLUTE
    assert s.csrf_token and s.csrf_token != token


async def test_resolve_valid_and_unknown(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token, s = await create_session(db_session, user.id, T0)
    got = await resolve_session(db_session, token, T0)
    assert got is not None and got.id == s.id
    assert await resolve_session(db_session, "nope", T0) is None
    assert await resolve_session(db_session, None, T0) is None


async def test_idle_expiry(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token, s = await create_session(db_session, user.id, T0)
    t1 = T0 + IDLE - timedelta(seconds=1)
    got = await resolve_session(db_session, token, t1)
    assert got is not None and got.last_seen_at == t1
    assert await resolve_session(db_session, token, t1 + IDLE) is None
    rows = (await db_session.execute(select(AuthSession).where(AuthSession.id == s.id))).all()
    assert rows == []


async def test_absolute_expiry(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token, _ = await create_session(db_session, user.id, T0)
    for days in (6, 12, 18, 24, 30 - 1):
        assert await resolve_session(db_session, token, T0 + timedelta(days=days)) is not None
    assert await resolve_session(db_session, token, T0 + ABSOLUTE) is None


async def test_last_seen_throttled(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token, _ = await create_session(db_session, user.id, T0)
    got = await resolve_session(db_session, token, T0 + timedelta(seconds=30))
    assert got is not None and got.last_seen_at == T0
    got = await resolve_session(db_session, token, T0 + timedelta(seconds=61))
    assert got is not None and got.last_seen_at == T0 + timedelta(seconds=61)


async def test_touch_persists_across_sessions(db: AsyncSession, test_settings: Settings) -> None:
    user = await _user(db)
    token, s = await create_session(db, user.id, T0)
    await db.commit()
    t = T0 + timedelta(minutes=2)
    await resolve_session(db, token, t)
    engine = create_async_engine(test_settings.database_url.get_secret_value())
    try:
        async with AsyncSession(engine) as other:
            seen = (
                await other.execute(select(AuthSession.last_seen_at).where(AuthSession.id == s.id))
            ).scalar_one()
    finally:
        await engine.dispose()
    assert seen == t


async def test_lazy_delete_persists(db: AsyncSession, test_settings: Settings) -> None:
    user = await _user(db)
    token, s = await create_session(db, user.id, T0)
    await db.commit()
    assert await resolve_session(db, token, T0 + ABSOLUTE) is None
    engine = create_async_engine(test_settings.database_url.get_secret_value())
    try:
        async with AsyncSession(engine) as other:
            rows = (await other.execute(select(AuthSession).where(AuthSession.id == s.id))).all()
    finally:
        await engine.dispose()
    assert rows == []


async def test_create_session_prunes_users_expired_sessions(db_session: AsyncSession) -> None:
    a = await _user(db_session, "a@example.com")
    b = await _user(db_session, "b@example.com")
    _, old_a = await create_session(db_session, a.id, T0)
    _, old_b = await create_session(db_session, b.id, T0)
    later = T0 + ABSOLUTE + timedelta(seconds=1)
    _, new_a = await create_session(db_session, a.id, later)
    ids = set((await db_session.execute(select(AuthSession.id))).scalars())
    assert old_a.id not in ids
    assert old_b.id in ids  # other users' rows untouched
    assert new_a.id in ids


async def test_delete_session(db_session: AsyncSession) -> None:
    user = await _user(db_session)
    token, s = await create_session(db_session, user.id, T0)
    await delete_session(db_session, s.id)
    assert await resolve_session(db_session, token, T0) is None


def test_cookie_flags() -> None:
    settings = Settings(database_url="postgresql+asyncpg://x:x@h/d", _env_file=None)
    assert settings.session_cookie_secure is True
    resp = Response()
    set_session_cookie(resp, "tok", settings)
    header = resp.headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE}=tok" in header
    for flag in ("httponly", "samesite=lax", "path=/", "max-age=2592000", "secure"):
        assert flag in header
    off = settings.model_copy(update={"session_cookie_secure": False})
    resp2 = Response()
    set_session_cookie(resp2, "tok", off)
    assert "secure" not in resp2.headers["set-cookie"].lower()
    resp3 = Response()
    clear_session_cookie(resp3, settings)
    assert "max-age=0" in resp3.headers["set-cookie"].lower()
