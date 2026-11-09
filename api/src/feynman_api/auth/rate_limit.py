import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.models import RateLimitBucket

# Transactions: hit, clear and prune COMMIT the caller's session (so counts survive a failing
# request), which also commits any pending work in it. Call them before making pending writes.
# peek only reads.
_RETENTION = timedelta(days=1)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int


def _window(now: datetime, window: timedelta) -> tuple[datetime, int]:
    """Epoch-aligned fixed window: (start, whole seconds from now to its end, >= 1)."""
    size = window.total_seconds()
    start_ts = math.floor(now.timestamp() / size) * size
    start = datetime.fromtimestamp(start_ts, UTC)
    remaining = math.ceil(start_ts + size - now.timestamp())
    return start, max(1, remaining)


async def hit(
    db: AsyncSession, key: str, limit: int, window: timedelta, now: datetime
) -> RateLimitResult:
    """Count one attempt and commit, so the count survives a following 401/403/429."""
    start, retry_after = _window(now, window)
    stmt = (
        insert(RateLimitBucket)
        .values(key=key, window_start=start, count=1)
        .on_conflict_do_update(
            index_elements=["key", "window_start"],
            set_={"count": RateLimitBucket.count + 1},
        )
        .returning(RateLimitBucket.count)
    )
    count = (await db.execute(stmt)).scalar_one()
    await db.commit()
    return RateLimitResult(allowed=count <= limit, retry_after=retry_after)


async def peek(
    db: AsyncSession, key: str, limit: int, window: timedelta, now: datetime
) -> RateLimitResult:
    start, retry_after = _window(now, window)
    count = (
        await db.execute(
            select(RateLimitBucket.count).where(
                RateLimitBucket.key == key, RateLimitBucket.window_start == start
            )
        )
    ).scalar_one_or_none()
    return RateLimitResult(allowed=(count or 0) < limit, retry_after=retry_after)


async def clear(db: AsyncSession, key: str) -> None:
    await db.execute(delete(RateLimitBucket).where(RateLimitBucket.key == key))
    await db.commit()


async def prune(db: AsyncSession, now: datetime) -> None:
    await db.execute(delete(RateLimitBucket).where(RateLimitBucket.window_start < now - _RETENTION))
    await db.commit()


def email_key(email: str) -> str:
    return "login:email:" + hashlib.sha256(email.lower().encode()).hexdigest()


def ip_key(prefix: str, ip: str) -> str:
    return prefix + ip
