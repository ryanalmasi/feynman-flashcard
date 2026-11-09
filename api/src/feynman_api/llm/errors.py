class LLMError(Exception):
    """Base class. Adapters map vendor exceptions onto these; callers never see vendor types."""


class LLMRateLimitError(LLMError):
    def __init__(self, message: str = "rate limited", *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMUnavailableError(LLMError):
    """Timeouts, 5xx."""


class LLMRefusalError(LLMError):
    pass


class LLMOutputValidationError(LLMError):
    """Structured output failed schema validation after the adapter's own retry."""
