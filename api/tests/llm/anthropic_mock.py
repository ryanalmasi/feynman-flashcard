"""A mocked-transport Anthropic client for tests: no network, canned Messages API bodies.

The handler answers like the Messages API: JSON for plain requests, SSE for `"stream": true`.
"""

import json
from collections.abc import Callable, Coroutine, Sequence
from typing import Any

import anthropic
import httpx2

from feynman_api.llm.anthropic import AnthropicProvider
from feynman_api.llm.errors import (
    LLMError,
    LLMOutputValidationError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMUnavailableError,
)

Handler = Callable[[httpx2.Request], Coroutine[Any, Any, httpx2.Response]]

DEFAULT_USAGE: dict[str, int] = {"input_tokens": 10, "output_tokens": 5}


def mock_client(handler: Handler, *, api_key: str = "test-key") -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(
        api_key=api_key,
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )


def error_response(
    status: int, error_type: str, *, headers: dict[str, str] | None = None
) -> httpx2.Response:
    return httpx2.Response(
        status,
        headers=headers,
        json={"type": "error", "error": {"type": error_type, "message": "mock error"}},
    )


def message_response(
    body: dict[str, Any],
    *,
    text: str | None,
    stop_reason: str,
    usage: dict[str, int] | None = None,
) -> httpx2.Response:
    """A Messages API reply for `body`: JSON, or SSE when the request asked to stream."""
    usage = dict(DEFAULT_USAGE if usage is None else usage)
    model = body["model"]
    if not body.get("stream"):
        return httpx2.Response(
            200,
            json={
                "id": "msg_mock",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [] if text is None else [{"type": "text", "text": text}],
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": usage,
            },
        )
    start_usage = {**usage, "output_tokens": 0}
    events: list[tuple[str, dict[str, Any]]] = [
        (
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_mock",
                    "type": "message",
                    "role": "assistant",
                    "model": model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": start_usage,
                },
            },
        )
    ]
    if text is not None:
        events.append(
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            )
        )
        for i in range(0, len(text), 4):
            events.append(
                (
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": text[i : i + 4]},
                    },
                )
            )
        events.append(("content_block_stop", {"type": "content_block_stop", "index": 0}))
    events.append(
        (
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": usage,
            },
        )
    )
    events.append(("message_stop", {"type": "message_stop"}))
    sse = "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=sse.encode())


def is_structured(body: dict[str, Any]) -> bool:
    return bool((body.get("output_config") or {}).get("format"))


def _error_scenario(
    body: dict[str, Any], error: LLMError, usage: dict[str, int] | None
) -> httpx2.Response:
    if isinstance(error, LLMRateLimitError):
        return error_response(429, "rate_limit_error", headers={"retry-after": "1.5"})
    if isinstance(error, LLMUnavailableError):
        return error_response(529, "overloaded_error")
    if isinstance(error, LLMRefusalError):
        return message_response(body, text=None, stop_reason="refusal", usage=usage)
    if isinstance(error, LLMOutputValidationError):
        return message_response(
            body, text='{"answer": "trunc', stop_reason="max_tokens", usage=usage
        )
    return error_response(400, "invalid_request_error")


def make_anthropic_provider(
    *,
    replies: Sequence[str] = ("Fake reply.",),
    structured: Sequence[dict[str, Any] | str] = (),
    error: LLMError | None = None,
    requests: list[dict[str, Any]] | None = None,
    api_key: str = "test-key",
    effort: str = "medium",
    usage: dict[str, int] | None = None,
) -> AnthropicProvider:
    """An AnthropicProvider whose HTTP traffic goes to a scenario-driven mock handler.

    A `str` entry in `structured` is sent verbatim as the reply text (e.g. invalid JSON).
    """
    reply_list = tuple(replies) or ("Fake reply.",)
    structured_list = tuple(structured)
    counters = {"reply": 0, "structured": 0}

    async def handler(request: httpx2.Request) -> httpx2.Response:
        body: dict[str, Any] = json.loads(request.content)
        if requests is not None:
            requests.append(body)
        if error is not None:
            return _error_scenario(body, error, usage)
        if is_structured(body):
            if structured_list:
                payload = structured_list[counters["structured"] % len(structured_list)]
                counters["structured"] += 1
                text = payload if isinstance(payload, str) else json.dumps(payload)
            else:
                text = ""
        else:
            text = reply_list[counters["reply"] % len(reply_list)]
            counters["reply"] += 1
        return message_response(body, text=text, stop_reason="end_turn", usage=usage)

    return AnthropicProvider(
        mock_client(handler, api_key=api_key), effort=effort, request_timeout=30.0
    )
