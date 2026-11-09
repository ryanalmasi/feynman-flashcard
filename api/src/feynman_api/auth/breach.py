import hashlib
import logging
from collections.abc import Collection
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/"


class BreachChecker(Protocol):
    async def is_breached(self, password: str) -> bool: ...


class HibpBreachChecker:
    """Have I Been Pwned range API (k-anonymity). Fails open on any error."""

    def __init__(self, client: httpx.AsyncClient, timeout: float) -> None:
        self._client = client
        self._timeout = timeout

    async def is_breached(self, password: str) -> bool:
        digest = hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()
        prefix, suffix = digest[:5], digest[5:]
        try:
            response = await self._client.get(
                HIBP_RANGE_URL + prefix,
                headers={"Add-Padding": "true", "User-Agent": "feynman-flashcard"},
                timeout=self._timeout,
            )
            if response.status_code != 200:
                logger.warning("HIBP check unavailable (%s); allowing password", "HTTPStatusError")
                return False
        except httpx.HTTPError as exc:
            logger.warning("HIBP check unavailable (%s); allowing password", type(exc).__name__)
            return False
        for line in response.text.splitlines():
            candidate, _, count = line.strip().partition(":")
            if candidate.upper() == suffix and count.strip().isdigit() and int(count) > 0:
                return True
        return False


class StaticBreachChecker:
    def __init__(self, breached: Collection[str] = ()) -> None:
        self._breached = frozenset(breached)

    async def is_breached(self, password: str) -> bool:
        return password in self._breached
