import asyncio
import logging
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

from feynman_api.clock import system_clock
from feynman_api.config import Settings
from feynman_api.db import create_sessionmaker
from feynman_api.jobs import worker as worker_module
from feynman_api.jobs.queue import enqueue
from feynman_api.jobs.registry import (
    GENERIC_FAILURE,
    JobHandler,
    LeaseLost,
    PermanentJobError,
    WorkerContext,
    generic_failure_for,
)
from feynman_api.jobs.worker import run_forever, run_once
from feynman_api.llm import FakeLLMProvider
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
    await asyncio.wait_for(task, timeout=0.5)


async def test_failing_on_failed_still_marks_job_failed(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)

    class BadOnFailed(RecordingHandler):
        async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None:
            raise RuntimeError("on_failed broke")

    handler = BadOnFailed(exc=PermanentJobError("Nope."))
    assert await run_once(sm, ctx, {"k": handler}) is True
    job = await _get(sm, jid)
    assert job.status == "failed"
    assert job.last_error == "Nope."
    assert job.locked_until is None
    assert await run_once(sm, ctx, {"k": handler}) is False
    assert handler.runs == 1


async def test_lease_lost_during_run_rolls_back_handler_writes(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)

    class ReclaimedMidRun(RecordingHandler):
        async def run(
            self, db: AsyncSession, job: Job, ctx: WorkerContext
        ) -> dict[str, Any] | None:
            db.add(StudySet(user_id=job.user_id, title="leak"))
            await db.flush()
            async with sm() as other:  # simulate another worker reclaiming the job
                await other.execute(
                    update(Job).where(Job.id == job.id).values(attempts=Job.attempts + 1)
                )
                await other.commit()
            return {"done": True}

    assert await run_once(sm, ctx, {"k": ReclaimedMidRun()}) is True
    async with sm() as s:
        assert (await s.execute(select(StudySet))).first() is None
    job = await _get(sm, jid)
    assert job.status == "running"
    assert job.attempts == 2
    assert job.result is None


async def test_lease_lost_writes_nothing(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)

    class LosesLease(RecordingHandler):
        async def run(
            self, db: AsyncSession, job: Job, ctx: WorkerContext
        ) -> dict[str, Any] | None:
            self.runs += 1
            db.add(StudySet(user_id=job.user_id, title="leak"))
            await db.flush()
            raise LeaseLost()

    handler = LosesLease()
    assert await run_once(sm, ctx, {"k": handler}) is True
    async with sm() as s:
        assert (await s.execute(select(StudySet))).first() is None
    job = await _get(sm, jid)
    assert job.status == "running"
    assert job.attempts == 1
    assert job.last_error is None
    assert job.result is None
    assert handler.runs == 1
    assert handler.failed_messages == []


class KindHandler(RecordingHandler):
    generic_failure = "Kind msg."


async def test_exhausted_retries_use_handler_generic_failure(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)
    handler = KindHandler(exc=RuntimeError("boom"))
    for _ in range(3):
        await _make_due(sm, jid)
        assert await run_once(sm, ctx, {"k": handler}) is True
    job = await _get(sm, jid)
    assert job.status == "failed"
    assert job.last_error == "RuntimeError"
    assert handler.failed_messages == ["Kind msg."]


async def test_reclaimed_exhausted_uses_handler_generic_failure(sm, ctx) -> None:  # type: ignore[no-untyped-def]
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
    handler = KindHandler()
    assert await run_once(sm, ctx, {"k": handler}) is True
    job = await _get(sm, jid)
    assert handler.runs == 0
    assert job.status == "failed"
    assert handler.failed_messages == ["Kind msg."]
    assert job.last_error == "Kind msg."


async def test_worker_context_defaults(test_settings: Settings, file_store: FileStore) -> None:
    c = WorkerContext(settings=test_settings, file_store=file_store)
    assert c.llm is None
    assert c.clock is system_clock
    assert generic_failure_for(RecordingHandler()) == GENERIC_FAILURE
    assert generic_failure_for(KindHandler()) == "Kind msg."


async def test_failure_fallback_runs_when_on_failed_raises(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    jid = await _job(sm)

    class FallbackHandler(RecordingHandler):
        def __init__(self) -> None:
            super().__init__(exc=PermanentJobError("Nope."))
            self.fallback_messages: list[str] = []

        async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None:
            db.add(StudySet(user_id=job.user_id, title="from on_failed"))
            await db.flush()
            raise RuntimeError("on_failed broke")

        async def failure_fallback(self, db: AsyncSession, job: Job, user_message: str) -> None:
            self.fallback_messages.append(user_message)
            db.add(StudySet(user_id=job.user_id, title="from fallback"))

    handler = FallbackHandler()
    assert await run_once(sm, ctx, {"k": handler}) is True
    assert handler.fallback_messages == ["Nope."]
    job = await _get(sm, jid)
    assert job.status == "failed"
    assert job.last_error == "Nope."
    assert job.locked_until is None
    async with sm() as s:
        titles = (await s.execute(select(StudySet.title))).scalars().all()
    assert titles == ["from fallback"]  # on_failed's writes rolled back, fallback's committed


async def test_main_pins_sdk_loggers_and_builds_llm(  # type: ignore[no-untyped-def]
    test_settings: Settings, tmp_path, monkeypatch
) -> None:
    seen: list[WorkerContext] = []

    async def fake_run_forever(sessionmaker, ctx, handlers, stop) -> None:  # type: ignore[no-untyped-def]
        seen.append(ctx)

    monkeypatch.setattr(worker_module, "run_forever", fake_run_forever)
    test_settings.upload_dir = tmp_path / "up"
    names = ("anthropic", "httpx2", "httpcore2")
    saved = {n: logging.getLogger(n).level for n in names}
    try:
        for n in names:
            logging.getLogger(n).setLevel(logging.DEBUG)
        await worker_module._main(test_settings)
        for n in names:
            assert logging.getLogger(n).getEffectiveLevel() >= logging.WARNING, n
    finally:
        for n, level in saved.items():
            logging.getLogger(n).setLevel(level)
    [c] = seen
    assert c.llm is None  # LLM_ENABLED is false in test settings


async def test_main_pins_sdk_loggers_after_provider_build(  # type: ignore[no-untyped-def]
    test_settings: Settings, tmp_path, monkeypatch
) -> None:
    # Simulates the SDK's import-time setup_logging() under ANTHROPIC_LOG=debug, which sets the
    # anthropic and httpx2 loggers to DEBUG while the provider is built. (Tests outside
    # tests/llm/ never import the SDK, so the fake builder does what that import does.)
    names = ("anthropic", "httpx2", "httpcore2")
    monkeypatch.setenv("ANTHROPIC_LOG", "debug")

    def fake_build(settings: Settings) -> FakeLLMProvider:
        for n in names:
            logging.getLogger(n).setLevel(logging.DEBUG)
        return FakeLLMProvider()

    async def fake_run_forever(sessionmaker, ctx, handlers, stop) -> None:  # type: ignore[no-untyped-def]
        assert isinstance(ctx.llm, FakeLLMProvider)
        for n in names:
            assert logging.getLogger(n).getEffectiveLevel() >= logging.WARNING, n

    monkeypatch.setattr(worker_module, "build_llm_provider", fake_build)
    monkeypatch.setattr(worker_module, "run_forever", fake_run_forever)
    test_settings.upload_dir = tmp_path / "up"
    test_settings.llm_enabled = True
    saved = {n: logging.getLogger(n).level for n in names}
    try:
        for n in names:
            logging.getLogger(n).setLevel(logging.NOTSET)
        await worker_module._main(test_settings)
        for n in names:
            assert logging.getLogger(n).getEffectiveLevel() >= logging.WARNING, n
    finally:
        for n, level in saved.items():
            logging.getLogger(n).setLevel(level)


async def test_main_fails_at_startup_without_api_key(  # type: ignore[no-untyped-def]
    test_settings: Settings, tmp_path, monkeypatch
) -> None:
    async def fake_run_forever(sessionmaker, ctx, handlers, stop) -> None:  # type: ignore[no-untyped-def]
        raise AssertionError("must not start")

    monkeypatch.setattr(worker_module, "run_forever", fake_run_forever)
    test_settings.upload_dir = tmp_path / "up"
    test_settings.llm_enabled = True
    test_settings.anthropic_api_key = None
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        await worker_module._main(test_settings)


async def test_llm_job_helpers(sm, ctx) -> None:  # type: ignore[no-untyped-def]
    from feynman_api.jobs.handlers._llm import (
        as_job_error,
        keep_lease,
        require_llm,
        sum_usage,
        usage_dict,
    )
    from feynman_api.jobs.queue import claim
    from feynman_api.jobs.registry import MSG_LLM_DISABLED
    from feynman_api.llm import (
        FakeLLMProvider,
        LLMOutputValidationError,
        LLMRateLimitError,
        LLMRefusalError,
        LLMUnavailableError,
        Usage,
    )

    assert MSG_LLM_DISABLED == "AI features are turned off on this server."
    with pytest.raises(PermanentJobError) as exc_info:
        require_llm(ctx)
    assert exc_info.value.user_message == MSG_LLM_DISABLED
    fake = FakeLLMProvider()
    ctx.llm = fake
    assert require_llm(ctx) is fake

    rl = LLMRateLimitError(retry_after=3)
    un = LLMUnavailableError("down")
    assert as_job_error(rl, "Perm.") is rl
    assert as_job_error(un, "Perm.") is un
    for exc in (LLMRefusalError("no"), LLMOutputValidationError("bad")):
        mapped = as_job_error(exc, "Perm.")
        assert isinstance(mapped, PermanentJobError)
        assert mapped.user_message == "Perm."

    u = Usage(model_id="m", input_tokens=10, output_tokens=5, cached_input_tokens=2)
    d = usage_dict(u)
    assert d == {"model_id": "m", "input_tokens": 10, "output_tokens": 5, "cached_input_tokens": 2}
    assert sum_usage([d, d]) == {"input_tokens": 20, "output_tokens": 10, "cached_input_tokens": 4}
    assert sum_usage([]) == {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0}

    jid = await _job(sm)
    async with sm() as s:
        job = await claim(s, timedelta(seconds=10))
        await s.commit()
    assert job is not None
    async with sm() as s:
        await keep_lease(s, job, ctx)  # renews with llm_job_lease_seconds
        now = (await s.execute(text("SELECT now()"))).scalar_one()
        row = (await s.execute(select(Job).where(Job.id == jid))).scalar_one()
        assert row.locked_until - now > timedelta(seconds=ctx.settings.llm_job_lease_seconds - 10)
    async with sm() as s:
        await s.execute(update(Job).where(Job.id == jid).values(attempts=Job.attempts + 1))
        await s.commit()
    async with sm() as s:
        with pytest.raises(LeaseLost):
            await keep_lease(s, job, ctx)


def _typecheck(h: JobHandler) -> None:  # protocol conformance
    pass


_typecheck(OkHandler())
