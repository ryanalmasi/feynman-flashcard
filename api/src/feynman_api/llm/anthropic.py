"""Anthropic (Claude API) adapter behind the LLMProvider Protocol (ADR 0019, design 7.4).

This is the only module that imports the `anthropic` SDK. Vendor exceptions never escape: they
are re-raised as `feynman_api.llm` errors with fixed messages, `from None`, so neither the
vendor's text nor anything from the request (such as the API key) reaches a caller or a log.

Request rules: no `temperature`/`top_p`/`top_k`, no assistant prefill, no tools, no beta headers;
thinking stays at the model default; `output_config.effort` is sent on every call.
"""

import asyncio
import math
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Literal, cast

import anthropic
from anthropic.types import (
    AssistantMessageParam,
    Message,
    MessageParam,
    OutputConfigParam,
    TextBlockParam,
    UserMessageParam,
)
from pydantic import ValidationError

from feynman_api.llm.base import (
    ChatMessage,
    PromptBlock,
    StreamDone,
    StructuredResult,
    T,
    TextDelta,
    Usage,
)
from feynman_api.llm.errors import (
    LLMError,
    LLMOutputValidationError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMUnavailableError,
)

# Structured calls above this many output tokens stream internally (avoids HTTP timeouts).
STREAM_MAX_TOKENS_THRESHOLD = 16_000

_UNAVAILABLE_TYPES = {"overloaded_error", "api_error", "timeout_error"}
_STOP_REASONS: dict[str, Literal["end", "max_tokens"]] = {
    "end_turn": "end",
    "max_tokens": "max_tokens",
}


def _usage(
    model_id: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int | None,
    cache_read_input_tokens: int | None,
) -> Usage:
    """Map Anthropic usage onto our `Usage`.

    - `input_tokens` = `input_tokens + (cache_creation_input_tokens or 0)
      + (cache_read_input_tokens or 0)`: the total input, cached tokens included (as the fake).
    - `cached_input_tokens` = `cache_read_input_tokens or 0`.
    - `output_tokens` = `output_tokens`.
    - `model_id` = the response's `model`.
    """
    return Usage(
        model_id=model_id,
        input_tokens=input_tokens
        + (cache_creation_input_tokens or 0)
        + (cache_read_input_tokens or 0),
        output_tokens=output_tokens,
        cached_input_tokens=cache_read_input_tokens or 0,
    )


def _message_usage(message: Message) -> Usage:
    u = message.usage
    return _usage(
        message.model,
        input_tokens=u.input_tokens,
        output_tokens=u.output_tokens,
        cache_creation_input_tokens=u.cache_creation_input_tokens,
        cache_read_input_tokens=u.cache_read_input_tokens,
    )


def _retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def _status_error(exc: anthropic.APIStatusError) -> LLMError:
    status = exc.status_code
    message = f"anthropic: HTTP {status}"
    # A mid-stream SSE error arrives on a 200 response; its error type classifies it.
    if status == 429 or exc.type == "rate_limit_error":
        return LLMRateLimitError(
            message, retry_after=_retry_after(exc.response.headers.get("retry-after"))
        )
    if status == 408 or status >= 500 or exc.type in _UNAVAILABLE_TYPES:
        return LLMUnavailableError(message)
    return LLMError(message)


@contextmanager
def _vendor_errors() -> Iterator[None]:
    """Re-raise SDK exceptions and our deadline as `feynman_api.llm` errors, `from None`."""
    try:
        yield
    except TimeoutError:
        raise LLMUnavailableError("anthropic: request timed out") from None
    except anthropic.APIStatusError as exc:  # before APIConnectionError (both are APIErrors)
        raise _status_error(exc) from None
    except anthropic.APIConnectionError:  # includes APITimeoutError
        raise LLMUnavailableError("anthropic: connection error") from None
    except anthropic.APIError:
        raise LLMError("anthropic: API error") from None


def _system(blocks: Sequence[PromptBlock]) -> list[TextBlockParam]:
    out: list[TextBlockParam] = []
    for b in blocks:
        block: TextBlockParam = {"type": "text", "text": b.text}
        if b.cache:
            block["cache_control"] = {"type": "ephemeral"}
        out.append(block)
    return out


def _message(m: ChatMessage) -> MessageParam:
    if m.role == "user":
        user: UserMessageParam = {"role": "user", "content": m.content}
        return user
    assistant: AssistantMessageParam = {"role": "assistant", "content": m.content}
    return assistant


def _messages(messages: Sequence[ChatMessage]) -> list[MessageParam]:
    return [_message(m) for m in messages]


class AnthropicProvider:
    def __init__(
        self, client: anthropic.AsyncAnthropic, *, effort: str, request_timeout: float
    ) -> None:
        self.client = client
        self._effort = cast(Literal["low", "medium", "high"], effort)
        self._request_timeout = request_timeout

    def _request(
        self,
        *,
        model: str,
        system: Sequence[PromptBlock],
        messages: Sequence[ChatMessage],
        max_tokens: int,
        output_config: OutputConfigParam,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": _messages(messages),
            "output_config": output_config,
        }
        if system:
            request["system"] = _system(system)
        return request

    async def stream_chat(
        self,
        *,
        model: str,
        system: Sequence[PromptBlock],
        messages: Sequence[ChatMessage],
        max_tokens: int,
    ) -> AsyncIterator[TextDelta | StreamDone]:
        request = self._request(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            output_config={"effort": self._effort},
        )
        # One absolute deadline for the whole call. It wraps only our own awaits, never a
        # `yield`, so time the consumer spends between deltas still counts but its code is
        # never cancelled by us.
        deadline = asyncio.get_running_loop().time() + self._request_timeout
        with _vendor_errors():
            async with asyncio.timeout_at(deadline):
                stream = await self.client.messages.create(**request, stream=True)
        try:
            model_id = model
            input_tokens = output_tokens = 0
            cache_creation: int | None = None
            cache_read: int | None = None
            stop_reason: str | None = None
            while True:
                with _vendor_errors():
                    async with asyncio.timeout_at(deadline):
                        try:
                            event = await anext(stream)
                        except StopAsyncIteration:
                            break
                if event.type == "message_start":
                    model_id = event.message.model
                    u = event.message.usage
                    input_tokens, output_tokens = u.input_tokens, u.output_tokens
                    cache_creation = u.cache_creation_input_tokens
                    cache_read = u.cache_read_input_tokens
                elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                    yield TextDelta(text=event.delta.text)
                elif event.type == "message_delta":
                    stop_reason = event.delta.stop_reason
                    if stop_reason == "refusal":
                        raise LLMRefusalError("anthropic: the model refused") from None
                    d = event.usage
                    output_tokens = d.output_tokens  # cumulative totals: overwrite
                    if d.input_tokens is not None:
                        input_tokens = d.input_tokens
                    if d.cache_creation_input_tokens is not None:
                        cache_creation = d.cache_creation_input_tokens
                    if d.cache_read_input_tokens is not None:
                        cache_read = d.cache_read_input_tokens
        finally:
            await stream.close()
        yield StreamDone(
            usage=_usage(
                model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_input_tokens=cache_creation,
                cache_read_input_tokens=cache_read,
            ),
            stop_reason=_STOP_REASONS.get(stop_reason or "", "other"),
        )

    async def generate_structured(
        self,
        *,
        model: str,
        system: Sequence[PromptBlock],
        messages: Sequence[ChatMessage],
        schema: type[T],
        max_tokens: int,
    ) -> StructuredResult[T]:
        # The same `output_config.format` that `messages.parse(output_format=schema)` sends
        # (the SDK's own `transform_schema`), but we validate the text ourselves so that the
        # stop reason is checked before any parse error (parse() validates first).
        request = self._request(
            model=model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            output_config={
                "effort": self._effort,
                "format": {"type": "json_schema", "schema": anthropic.transform_schema(schema)},
            },
        )
        with _vendor_errors():
            async with asyncio.timeout(self._request_timeout):
                message: Message
                if max_tokens > STREAM_MAX_TOKENS_THRESHOLD:
                    async with self.client.messages.stream(**request) as stream:
                        message = await stream.get_final_message()
                else:
                    message = await self.client.messages.create(**request)

        if message.stop_reason == "refusal":
            raise LLMRefusalError("anthropic: the model refused") from None
        if message.stop_reason == "max_tokens":
            raise LLMOutputValidationError("anthropic: output stopped at max_tokens") from None
        text = "".join(b.text for b in message.content if b.type == "text")
        try:
            value = schema.model_validate_json(text)
        except ValidationError:
            raise LLMOutputValidationError(
                "anthropic: structured output failed validation"
            ) from None
        return StructuredResult[T](value=value, usage=_message_usage(message))


def build_anthropic_provider(
    api_key: str, *, effort: str, request_timeout: float
) -> AnthropicProvider:
    return AnthropicProvider(
        anthropic.AsyncAnthropic(api_key=api_key, max_retries=0, timeout=request_timeout),
        effort=effort,
        request_timeout=request_timeout,
    )
