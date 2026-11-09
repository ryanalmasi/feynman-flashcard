from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Request

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now(UTC)


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock
