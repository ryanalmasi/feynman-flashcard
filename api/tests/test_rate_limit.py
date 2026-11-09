from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from feynman_api.auth.rate_limit import clear, email_key, hit, ip_key, peek, prune
from feynman_api.config import Settings
from feynman_api.models import RateLimitBucket

W = timedelta(minutes=15)
T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)  # aligned to the 15-minute grid


async def test_rate_limit_hit_counts_and_blocks(db_session: AsyncSession) -> None:
    now = T0 + timedelta(minutes=5)
    for _ in range(3):
        assert (await hit(db_session, "k", 3, W, now)).allowed
    r = await hit(db_session, "k", 3, W, now)
    assert not r.allowed
    assert r.retry_after == 600


async def test_retry_after_minimum_one(db_session: AsyncSession) -> None:
    now = T0 + W - timedelta(milliseconds=1)
    r = await hit(db_session, "k", 0, W, now)
    assert not r.allowed and r.retry_after == 1


async def test_peek_reads_only(db_session: AsyncSession) -> None:
    for _ in range(2):
        await hit(db_session, "k", 2, W, T0)
    assert not (await peek(db_session, "k", 2, W, T0)).allowed
    assert (await peek(db_session, "k", 3, W, T0)).allowed
    assert (await peek(db_session, "other", 1, W, T0)).allowed
    count = (await db_session.execute(select(RateLimitBucket.count))).scalars().all()
    assert count == [2]


async def test_rate_limit_new_window_resets(db_session: AsyncSession) -> None:
    await hit(db_session, "k", 1, W, T0)
    assert not (await hit(db_session, "k", 1, W, T0)).allowed
    assert (await hit(db_session, "k", 1, W, T0 + W)).allowed


async def test_rate_limit_clear(db_session: AsyncSession) -> None:
    await hit(db_session, "k", 1, W, T0)
    await hit(db_session, "j", 1, W, T0)
    await clear(db_session, "k")
    assert (await peek(db_session, "k", 1, W, T0)).allowed
    assert not (await peek(db_session, "j", 1, W, T0)).allowed


async def test_prune_deletes_windows_older_than_a_day(db_session: AsyncSession) -> None:
    await hit(db_session, "old", 5, W, T0)
    await hit(db_session, "new", 5, W, T0 + timedelta(days=1, hours=1))
    await prune(db_session, T0 + timedelta(days=1, hours=1))
    keys = set((await db_session.execute(select(RateLimitBucket.key))).scalars())
    assert keys == {"new"}


async def test_rate_limit_hit_survives_rollback(db: AsyncSession, test_settings: Settings) -> None:
    await hit(db, "k", 3, W, T0)
    await db.rollback()
    engine = create_async_engine(test_settings.database_url.get_secret_value())
    try:
        async with AsyncSession(engine) as other:
            counts = (await other.execute(select(RateLimitBucket.count))).scalars().all()
    finally:
        await engine.dispose()
    assert counts == [1]


def test_email_key_hashes_email() -> None:
    assert "a@x.com" not in email_key("A@x.com")
    assert email_key("A@x.com") == email_key("a@x.com")
    assert email_key("a@x.com").startswith("login:email:")
    assert ip_key("login:ip:", "1.2.3.4").startswith("login:ip:")
