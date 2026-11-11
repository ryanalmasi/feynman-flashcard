"""Builds the configured LLM provider. Only the worker calls this (the API never builds one).

This module never imports the vendor SDK itself: the adapter is imported lazily, so importing
the factory does not load `anthropic`.
"""

from feynman_api.config import Settings
from feynman_api.llm.base import LLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    if not settings.llm_enabled:
        return None
    key = settings.anthropic_api_key
    if key is None or not key.get_secret_value():
        raise RuntimeError("LLM_ENABLED is true but ANTHROPIC_API_KEY is not set.")
    # Lazy import: loads the SDK only when a provider is actually built.
    from feynman_api.llm.anthropic import build_anthropic_provider

    return build_anthropic_provider(
        key.get_secret_value(),
        effort=settings.llm_effort,
        request_timeout=settings.llm_request_timeout_seconds,
    )
