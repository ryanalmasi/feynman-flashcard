import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

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
from feynman_api.jobs.queue import enqueue
from feynman_api.jobs.registry import GENERIC_FAILURE, JobHandler, PermanentJobError, WorkerContext
from feynman_api.jobs.worker import run_forever, run_once
from feynman_api.models.job import Job
from feynman_api.models.study_set import StudySet
from feynman_api.models.user import User
from feynman_api.storage import FileStore


class OkHandler:
    async def run(self, db: AsyncSession, job: Job, ctx: WorkerContext) -> dict[str, Any] | None:
        return {"done": True}

    async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None:
        raise AssertionError("not expected")


class RecordingHandler:
    def __init__(self, fail_times: int | None = None, exc: Exception | None = None) -> None:
        self.fail_times = fail_times  # None = always fail when exc given
        self.exc = exc
        self.runs = 0
        self.failed_messages: list[str] = []

    async def run(self, db: AsyncSession, job: Job, ctx: WorkerContext) -> dict[str, Any] | None:
        self.runs += 1
        if self.exc is not None and (self.fail_times is None or self.runs <= self.fail_times):
            raise self.exc
        return {"runs": self.runs}

    async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None:
        self.failed_messages.append(user_message)


def flaky(fail_times: int) -> RecordingHandler:
    return RecordingHandler(fail_times=fail_times, exc=RuntimeError("boom"))


def always_raise() -> RecordingHandler:
    return RecordingHandler(exc=RuntimeError("boom"))


def permanent() -> RecordingHandler:
    return RecordingHandler(exc=PermanentJobError("Nope."))


@pytest.fixture
async def sm(
    clean_db: None, test_settings: Settings
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine: AsyncEngine = create_async_engine(test_settings.database_url.get_secret_value())
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest.fixture
def ctx(test_settings: Settings, file_store: FileStore) -> WorkerContext:
    return WorkerContext(settings=test_settings, file_store=file_store)


async def _user(sm: async_sessionmaker[AsyncSession]) -> UUID:
    async with sm() as s:
        user = User(email="w@example.com")
        s.add(user)
        await s.commit()
        return user.id


async def _job(sm: async_sessionmaker[AsyncSession], kind: str = "k") -> UUID:
    uid = await _user(sm)
    async with sm() as s:
        job = await enqueue(s, kind=kind, payload={}, user_id=uid)
        await s.commit()
        return job.id


async def _get(sm: async_sessionmaker[AsyncSession], jid: UUID) -> Job:
    async with sm() as s:
        return (await s.execute(select(Job).where(Job.id == jid))).scalar_one()


async def _make_due(sm: async_sessionmaker[AsyncSession], jid: UUID) -> None:
    async with sm() as s:
        await s.execute(
            update(Job)
            .where(Job.id == jid)
            .values(run_after=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()


async def test_success_stores_result(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)
    assert await run_once(sm, ctx, {"k": OkHandler()}) is True
    job = await _get(sm, jid)
    assert job.status == "succeeded"
    assert job.result == {"done": True}
    assert job.locked_until is None
    assert await run_once(sm, ctx, {"k": OkHandler()}) is False


async def test_unknown_kind_fails(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm, kind="nope")
    assert await run_once(sm, ctx, {}) is True
    job = await _get(sm, jid)
    assert job.status == "failed"
    assert job.last_error == "unknown job kind"


async def test_transient_error_retries_with_backoff(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)
    handler = flaky(1)
    assert await run_once(sm, ctx, {"k": handler}) is True
    job = await _get(sm, jid)
    assert job.status == "queued"
    assert job.attempts == 1
    assert job.last_error == "RuntimeError"
    assert job.locked_until is None
    async with sm() as s:
        now = (await s.execute(text("SELECT now()"))).scalar_one()
    assert timedelta(seconds=15) < job.run_after - now < timedelta(seconds=21)
    # Not due yet.
    assert await run_once(sm, ctx, {"k": handler}) is False
    await _make_due(sm, jid)
    assert await run_once(sm, ctx, {"k": handler}) is True
    assert (await _get(sm, jid)).status == "succeeded"


async def test_transient_exhaustion_fails_and_calls_on_failed(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)
    handler = always_raise()
    for _ in range(3):
        await _make_due(sm, jid)
        assert await run_once(sm, ctx, {"k": handler}) is True
    job = await _get(sm, jid)
    assert job.status == "failed"
    assert job.attempts == 3
    assert job.last_error == "RuntimeError"
    assert handler.runs == 3
    assert handler.failed_messages == [GENERIC_FAILURE]


async def test_permanent_error_fails_immediately(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)
    handler = permanent()
    assert await run_once(sm, ctx, {"k": handler}) is True
    job = await _get(sm, jid)
    assert job.status == "failed"
    assert job.attempts == 1
    assert job.last_error == "Nope."
    assert handler.failed_messages == ["Nope."]


async def test_reclaimed_exhausted_job_fails(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)
    async with sm() as s:
        await s.execute(
            update(Job)
            .where(Job.id == jid)
            .values(
                status="running",
                attempts=3,
                max_attempts=3,
                locked_until=datetime.now(UTC) - timedelta(seconds=5),
            )
        )
        await s.commit()
    handler = RecordingHandler()
    assert await run_once(sm, ctx, {"k": handler}) is True
    job = await _get(sm, jid)
    assert handler.runs == 0  # never ran
    assert job.status == "failed"
    assert job.attempts == 4
    assert handler.failed_messages == [GENERIC_FAILURE]
    assert job.last_error == GENERIC_FAILURE


async def test_handler_writes_roll_back_on_error(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)

    class WritingHandler(RecordingHandler):
        async def run(
            self, db: AsyncSession, job: Job, ctx: WorkerContext
        ) -> dict[str, Any] | None:
            db.add(StudySet(user_id=job.user_id, title="leak"))
            await db.flush()
            raise RuntimeError("boom")

    await run_once(sm, ctx, {"k": WritingHandler()})
    async with sm() as s:
        assert (await s.execute(select(StudySet))).first() is None
    assert (await _get(sm, jid)).status == "queued"


async def test_last_error_never_contains_exception_text(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)
    handler = RecordingHandler(exc=RuntimeError("secret-path /etc/x"))
    for _ in range(3):
        await _make_due(sm, jid)
        await run_once(sm, ctx, {"k": handler})
        job = await _get(sm, jid)
        assert job.last_error == "RuntimeError"
    assert (await _get(sm, jid)).status == "failed"


async def test_run_forever_stops_on_event(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    ctx.settings.job_poll_interval_seconds = 0.05
    stop = asyncio.Event()
    task = asyncio.create_task(run_forever(sm, ctx, {}, stop))
    await asyncio.sleep(0.15)
    assert not task.done()
    stop.set()
    await asyncio.wait_for(task, timeout=0.1)


def _typecheck(h: JobHandler) -> None:  # protocol conformance
    pass


_typecheck(OkHandler())
