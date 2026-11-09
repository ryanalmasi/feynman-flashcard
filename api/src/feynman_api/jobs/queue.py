from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.models.job import Job

ERROR_MAX_LEN = 500

# Job claiming deliberately uses the database clock (now()), not the injected clock:
# leases must be comparable across worker processes.
_CLAIM_SQL = text(
    """
    UPDATE jobs
    SET status = 'running',
        attempts = attempts + 1,
        locked_until = now() + CAST(:lease AS interval),
        updated_at = now()
    WHERE id = (
        SELECT id FROM jobs
        WHERE (status = 'queued' AND run_after <= now())
           OR (status = 'running' AND locked_until < now())
        ORDER BY run_after, created_at
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING *
    """
)


async def enqueue(db: AsyncSession, *, kind: str, payload: dict[str, Any], user_id: UUID) -> Job:
    """Add a job in the caller's transaction. Never commits."""
    job = Job(kind=kind, payload=payload, user_id=user_id)
    db.add(job)
    await db.flush()
    return job


async def claim(db: AsyncSession, lease: timedelta) -> Job | None:
    """Claim one due or lease-expired job. The caller commits."""
    result = await db.execute(
        select(Job).from_statement(_CLAIM_SQL.bindparams(lease=lease)),
        execution_options={"populate_existing": True},
    )
    return result.scalars().first()


async def _mark(db: AsyncSession, job: Job, **values: Any) -> bool:
    result = await db.execute(
        update(Job)
        .where(Job.id == job.id, Job.status == "running", Job.attempts == job.attempts)
        .values(updated_at=func.now(), **values)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1  # type: ignore[attr-defined,no-any-return]


async def mark_succeeded(db: AsyncSession, job: Job, result: dict[str, Any] | None) -> bool:
    return await _mark(db, job, status="succeeded", result=result, locked_until=None)


async def mark_retry(db: AsyncSession, job: Job, error: str, delay: timedelta) -> bool:
    return await _mark(
        db,
        job,
        status="queued",
        run_after=func.now() + delay,
        locked_until=None,
        last_error=error[:ERROR_MAX_LEN],
    )


async def mark_failed(db: AsyncSession, job: Job, error: str) -> bool:
    return await _mark(
        db, job, status="failed", locked_until=None, last_error=error[:ERROR_MAX_LEN]
    )
