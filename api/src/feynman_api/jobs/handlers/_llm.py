"""Helpers shared by the LLM job handlers."""

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.jobs.queue import renew_lease
from feynman_api.jobs.registry import (
    MSG_LLM_DISABLED,
    LeaseLost,
    PermanentJobError,
    WorkerContext,
)
from feynman_api.llm import LLMError, LLMProvider, LLMRateLimitError, LLMUnavailableError, Usage
from feynman_api.models.job import Job

_USAGE_TOTALS = ("input_tokens", "output_tokens", "cached_input_tokens")


def require_llm(ctx: WorkerContext) -> LLMProvider:
    if ctx.llm is None:
        raise PermanentJobError(MSG_LLM_DISABLED)
    return ctx.llm


async def keep_lease(db: AsyncSession, job: Job, ctx: WorkerContext) -> None:
    """Renew the lease (committing pending writes). Raises LeaseLost if it was lost.

    Never call this after the final writes begin.
    """
    lease = timedelta(seconds=ctx.settings.llm_job_lease_seconds)
    if not await renew_lease(db, job, lease):
        raise LeaseLost()


def as_job_error(exc: LLMError, permanent_message: str) -> Exception:
    """Rate limits and outages stay transient (the queue retries); anything else is permanent."""
    if isinstance(exc, (LLMRateLimitError, LLMUnavailableError)):
        return exc
    return PermanentJobError(permanent_message)


def usage_dict(u: Usage) -> dict[str, Any]:
    return u.model_dump()


def sum_usage(calls: Sequence[dict[str, Any]]) -> dict[str, int]:
    return {name: sum(int(call.get(name, 0)) for call in calls) for name in _USAGE_TOTALS}
