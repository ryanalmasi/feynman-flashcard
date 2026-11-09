from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.config import Settings
from feynman_api.models.job import Job
from feynman_api.storage import FileStore

GENERIC_FAILURE = "Something went wrong while processing this PDF. Try uploading it again."


class PermanentJobError(Exception):
    """Non-retryable failure. `user_message` is a fixed, user-facing string."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass
class WorkerContext:
    settings: Settings
    file_store: FileStore


class JobHandler(Protocol):
    async def run(self, db: AsyncSession, job: Job, ctx: WorkerContext) -> dict[str, Any] | None:
        """Do the work.

        The Job passed in is detached from any session: attribute changes on it are not
        persisted, so handlers must re-select any rows they modify.
        """
        ...

    async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None: ...


HANDLERS: dict[str, JobHandler] = {}


def register(kind: str, handler: JobHandler) -> None:
    HANDLERS[kind] = handler
