from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.clock import Clock, system_clock
from feynman_api.config import Settings
from feynman_api.llm.base import LLMProvider
from feynman_api.models.job import Job
from feynman_api.storage import FileStore

GENERIC_FAILURE = "Something went wrong while processing this PDF. Try uploading it again."
MSG_LLM_DISABLED = "AI features are turned off on this server."


class PermanentJobError(Exception):
    """Non-retryable failure. `user_message` is a fixed, user-facing string."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class LeaseLost(Exception):
    """Another worker reclaimed the job. The worker rolls back and records nothing."""


@dataclass
class WorkerContext:
    settings: Settings
    file_store: FileStore
    llm: LLMProvider | None = None
    clock: Clock = system_clock


class JobHandler(Protocol):
    async def run(self, db: AsyncSession, job: Job, ctx: WorkerContext) -> dict[str, Any] | None:
        """Do the work.

        The Job passed in is detached from any session: attribute changes on it are not
        persisted, so handlers must re-select any rows they modify.
        """
        ...

    async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None: ...

    # Optional, found with getattr (not part of the Protocol):
    #   generic_failure: str  -- the kind's "retries exhausted / unknown error" message
    #   async def failure_fallback(self, db, job, user_message) -> None
    #     -- a single guarded UPDATE that sets the owning row failed; used when on_failed raises


def generic_failure_for(handler: object) -> str:
    message: str = getattr(handler, "generic_failure", GENERIC_FAILURE)
    return message


HANDLERS: dict[str, JobHandler] = {}


def register(kind: str, handler: JobHandler) -> None:
    HANDLERS[kind] = handler
