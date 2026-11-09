import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from feynman_api.config import Settings
from feynman_api.db import create_sessionmaker
from feynman_api.jobs.queue import claim, enqueue, mark_failed, mark_retry, mark_succeeded
from feynman_api.models.job import Job
from feynman_api.models.user import User

LEASE = timedelta(seconds=300)


@pytest.fixture
async def sessionmaker(
    clean_db: None, test_settings: Settings
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine: AsyncEngine = create_async_engine(test_settings.database_url.get_secret_value())
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest.fixture
async def user_id(sessionmaker: async_sessionmaker[AsyncSession]):  # type: ignore[no-untyped-def]
    async with sessionmaker() as s:
        user = User(email="q@example.com")
        s.add(user)
        await s.commit()
        return user.id


async def _enqueue_committed(sm: async_sessionmaker[AsyncSession], user_id, n: int = 1) -> list:  # type: ignore[no-untyped-def,type-arg]
    ids = []
    async with sm() as s:
        for _ in range(n):
            ids.append((await enqueue(s, kind="extract_pdf", payload={}, user_id=user_id)).id)
        await s.commit()
    return ids


async def _db_now(s: AsyncSession) -> datetime:
    now: datetime = (await s.execute(text("SELECT now()"))).scalar_one()
    return now


async def test_enqueue_is_in_callers_transaction(sessionmaker, user_id) -> None:  # type: ignore[no-untyped-def]
    async with sessionmaker() as s:
        job = await enqueue(s, kind="extract_pdf", payload={"a": 1}, user_id=user_id)
        assert job.id is not None
        assert job.status == "queued"
        await s.rollback()
    async with sessionmaker() as s:
        assert (await s.execute(select(Job))).first() is None


async def test_claim_due_job_sets_running_and_lease(sessionmaker, user_id) -> None:  # type: ignore[no-untyped-def]
    [jid] = await _enqueue_committed(sessionmaker, user_id)
    async with sessionmaker() as s:
        job = await claim(s, LEASE)
        await s.commit()
        assert job is not None
        assert job.id == jid
        assert job.status == "running"
        assert job.attempts == 1
        assert job.locked_until is not None
        delta = job.locked_until - await _db_now(s)
        assert timedelta(seconds=290) < delta <= LEASE


async def test_claim_skips_future_run_after(sessionmaker, user_id) -> None:  # type: ignore[no-untyped-def]
    [jid] = await _enqueue_committed(sessionmaker, user_id)
    async with sessionmaker() as s:
        await s.execute(
            update(Job)
            .where(Job.id == jid)
            .values(run_after=datetime.now(UTC) + timedelta(hours=1))
        )
        await s.commit()
        assert await claim(s, LEASE) is None


async def test_expired_lease_is_reclaimed(sessionmaker, user_id) -> None:  # type: ignore[no-untyped-def]
    [jid] = await _enqueue_committed(sessionmaker, user_id)
    async with sessionmaker() as s:
        first = await claim(s, LEASE)
        await s.commit()
        assert first is not None
        assert first.attempts == 1
    async with sessionmaker() as s:
        # Lease still valid: not claimable.
        assert await claim(s, LEASE) is None
        await s.execute(
            update(Job)
            .where(Job.id == jid)
            .values(locked_until=datetime.now(UTC) - timedelta(seconds=5))
        )
        await s.commit()
        again = await claim(s, LEASE)
        await s.commit()
        assert again is not None
        assert again.id == jid
        assert again.attempts == 2
        assert again.status == "running"


async def test_skip_locked_second_claimer_gets_nothing(sessionmaker, user_id) -> None:  # type: ignore[no-untyped-def]
    [jid] = await _enqueue_committed(sessionmaker, user_id)
    async with sessionmaker() as a, sessionmaker() as b:
        got = await claim(a, LEASE)  # uncommitted: row lock held by A's connection
        assert got is not None
        assert got.id == jid
        # B must not block and must not see the job.
        assert await asyncio.wait_for(claim(b, LEASE), timeout=1) is None
        await b.rollback()
        await a.commit()
    async with sessionmaker() as s:
        row = (await s.execute(select(Job))).scalar_one()
        assert row.attempts == 1


async def test_concurrent_claimers_get_distinct_jobs(sessionmaker, user_id) -> None:  # type: ignore[no-untyped-def]
    ids = await _enqueue_committed(sessionmaker, user_id, 5)
    sessions = [sessionmaker() for _ in range(5)]
    try:
        # Each session claims and holds its (uncommitted) row lock until all have claimed,
        # so every claim really runs while the others' locks are held.
        claimed = await asyncio.wait_for(
            asyncio.gather(*(claim(s, LEASE) for s in sessions)), timeout=5
        )
        got = [j.id for j in claimed if j is not None]
        assert len(got) == 5
        assert set(got) == set(ids)
        for s in sessions:
            await s.commit()
    finally:
        for s in sessions:
            await s.close()
    async with sessionmaker() as s:
        assert await claim(s, LEASE) is None


async def test_mark_fails_after_lease_lost(sessionmaker, user_id) -> None:  # type: ignore[no-untyped-def]
    [jid] = await _enqueue_committed(sessionmaker, user_id)
    async with sessionmaker() as s:
        original = await claim(s, LEASE)
        await s.commit()
        assert original is not None
        await s.execute(
            update(Job)
            .where(Job.id == jid)
            .values(locked_until=datetime.now(UTC) - timedelta(seconds=5))
        )
        await s.commit()
    async with sessionmaker() as other:
        reclaimed = await claim(other, LEASE)
        await other.commit()
        assert reclaimed is not None
        assert reclaimed.attempts == 2
    async with sessionmaker() as s:
        assert await mark_succeeded(s, original, {"ok": True}) is False
        assert await mark_retry(s, original, "X", timedelta(seconds=1)) is False
        assert await mark_failed(s, original, "X") is False
        await s.rollback()
        # The new owner can still finish it.
    async with sessionmaker() as s:
        assert await mark_succeeded(s, reclaimed, {"ok": True}) is True
        await s.commit()


async def test_mark_helpers_set_state_and_truncate_error(sessionmaker, user_id) -> None:  # type: ignore[no-untyped-def]
    await _enqueue_committed(sessionmaker, user_id)
    async with sessionmaker() as s:
        job = await claim(s, LEASE)
        await s.commit()
        assert job is not None
        assert await mark_failed(s, job, "x" * 900) is True
        await s.commit()
    async with sessionmaker() as s:
        row = (await s.execute(select(Job))).scalar_one()
        assert row.status == "failed"
        assert row.last_error is not None
        assert len(row.last_error) == 500
        assert row.locked_until is None
