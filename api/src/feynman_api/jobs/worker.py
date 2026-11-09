import asyncio
import contextlib
import logging
import signal
from collections.abc import Mapping
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from feynman_api.config import Settings
from feynman_api.db import create_engine, create_sessionmaker
from feynman_api.jobs.queue import claim, mark_failed, mark_retry, mark_succeeded
from feynman_api.jobs.registry import (
    GENERIC_FAILURE,
    JobHandler,
    PermanentJobError,
    WorkerContext,
)
from feynman_api.models.job import Job
from feynman_api.storage import LocalFileStore

logger = logging.getLogger(__name__)


async def _fail(
    sessionmaker: async_sessionmaker[AsyncSession],
    job: Job,
    error: str,
    handler: JobHandler | None,
    user_message: str,
) -> None:
    if handler is not None:
        try:
            async with sessionmaker() as db:
                if not await mark_failed(db, job, error):
                    logger.warning("job %s: lease lost before failure could be recorded", job.id)
                    await db.rollback()
                    return
                await handler.on_failed(db, job, user_message)
                await db.commit()
                return
        except Exception as exc:
            # Never loop forever on a broken on_failed: record the failure alone below.
            logger.error(
                "job %s: on_failed raised %s; marking failed without it",
                job.id,
                type(exc).__name__,
                exc_info=True,
            )
    async with sessionmaker() as db:
        if await mark_failed(db, job, error):
            await db.commit()
        else:
            logger.warning("job %s: lease lost before failure could be recorded", job.id)
            await db.rollback()


async def run_once(
    sessionmaker: async_sessionmaker[AsyncSession],
    ctx: WorkerContext,
    handlers: Mapping[str, JobHandler],
) -> bool:
    """Claim and process at most one job. Returns True if a job was processed."""
    lease = timedelta(seconds=ctx.settings.job_lease_seconds)
    async with sessionmaker() as db:
        job = await claim(db, lease)
        await db.commit()
    if job is None:
        return False

    handler = handlers.get(job.kind)
    if handler is None:
        logger.error("job %s: unknown kind %r", job.id, job.kind)
        await _fail(sessionmaker, job, "unknown job kind", None, GENERIC_FAILURE)
        return True

    if job.attempts > job.max_attempts:
        # A reclaimed job whose lease expired on its last try: do not run it again.
        logger.error("job %s: attempts exhausted after lease expiry", job.id)
        await _fail(sessionmaker, job, GENERIC_FAILURE, handler, GENERIC_FAILURE)
        return True

    try:
        async with sessionmaker() as db:
            result = await handler.run(db, job, ctx)
            if await mark_succeeded(db, job, result):
                await db.commit()
            else:
                await db.rollback()
                logger.warning("job %s: lease lost, discarding result", job.id)
    except PermanentJobError as e:
        logger.warning("job %s: permanent failure", job.id)
        await _fail(sessionmaker, job, e.user_message, handler, e.user_message)
    except Exception as exc:
        logger.exception("job %s: handler raised", job.id)
        name = type(exc).__name__
        if job.attempts < job.max_attempts:
            backoff = timedelta(seconds=ctx.settings.job_backoff_base_seconds * 2**job.attempts)
            async with sessionmaker() as db:
                if await mark_retry(db, job, name, backoff):
                    await db.commit()
                else:
                    await db.rollback()
                    logger.warning("job %s: lease lost before retry was recorded", job.id)
        else:
            await _fail(sessionmaker, job, name, handler, GENERIC_FAILURE)
    return True


async def run_forever(
    sessionmaker: async_sessionmaker[AsyncSession],
    ctx: WorkerContext,
    handlers: Mapping[str, JobHandler],
    stop: asyncio.Event,
) -> None:
    interval = ctx.settings.job_poll_interval_seconds
    while not stop.is_set():
        try:
            processed = await run_once(sessionmaker, ctx, handlers)
        except Exception:
            logger.exception("worker loop error")
            processed = False
        if processed:
            continue
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval)


async def _main(settings: Settings) -> None:
    from feynman_api.jobs import handlers as _handlers  # noqa: F401  (registers handlers)
    from feynman_api.jobs.registry import HANDLERS

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings)
    sessionmaker = create_sessionmaker(engine)
    ctx = WorkerContext(settings=settings, file_store=LocalFileStore(settings.upload_dir))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    logger.info("worker started; polling every %ss", settings.job_poll_interval_seconds)
    try:
        await run_forever(sessionmaker, ctx, HANDLERS, stop)
    finally:
        await engine.dispose()
        logger.info("worker stopped")


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    logging.getLogger().setLevel(settings.log_level)
    asyncio.run(_main(settings))
