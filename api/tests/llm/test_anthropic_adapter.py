"""AnthropicProvider behaviour, pinned from the request bodies the SDK sends to a mock transport."""

import json
import re
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import BaseModel

from feynman_api.llm import (
    ChatMessage,
    LLMError,
    LLMOutputValidationError,
    LLMProvider,
    LLMRateLimitError,
    LLMRefusalError,
    LLMUnavailableError,
    PromptBlock,
    StreamDone,
    TextDelta,
    Usage,
)
from feynman_api.llm.anthropic import AnthropicProvider
from llm.anthropic_mock import (
    error_response,
    make_anthropic_provider,
    message_response,
    mock_client,
)

MSGS = [ChatMessage(role="user", content="hi")]
SRC = Path(__file__).resolve().parents[2] / "src" / "feynman_api"

_: LLMProvider = make_anthropic_provider()


class Out(BaseModel):
    answer: str


async def _chat(p: AnthropicProvider, **kw: Any) -> list[TextDelta | StreamDone]:
    args: dict[str, Any] = {"model": "m", "system": [], "messages": MSGS, "max_tokens": 50} | kw
    return [e async for e in p.stream_chat(**args)]


async def _structured(p: AnthropicProvider, **kw: Any) -> Any:
    args: dict[str, Any] = {
        "model": "m",
        "system": [],
        "messages": MSGS,
        "schema": Out,
        "max_tokens": 50,
    } | kw
    return await p.generate_structured(**args)


async def test_request_body_has_no_sampling_params() -> None:
    reqs: list[dict[str, Any]] = []
    p = make_anthropic_provider(structured=[{"answer": "x"}], requests=reqs)
    await _chat(p)
    await _structured(p)
    await _structured(p, max_tokens=32_000)
    assert len(reqs) == 3
    for body in reqs:
        assert not ({"temperature", "top_p", "top_k"} & body.keys())


async def test_cache_control_on_cached_block_only() -> None:
    reqs: list[dict[str, Any]] = []
    p = make_anthropic_provider(structured=[{"answer": "x"}], requests=reqs)
    system = [PromptBlock(text="a", cache=True), PromptBlock(text="b")]
    await _chat(p, system=system)
    await _structured(p, system=system)
    for body in reqs:
        assert body["system"][0] == {
            "type": "text",
            "text": "a",
            "cache_control": {"type": "ephemeral"},
        }
        assert body["system"][1] == {"type": "text", "text": "b"}
        assert "cache_control" not in body["system"][1]


async def test_model_and_effort_sent() -> None:
    reqs: list[dict[str, Any]] = []
    p = make_anthropic_provider(structured=[{"answer": "x"}], requests=reqs, effort="low")
    await _chat(p, model="claude-haiku-5-5")
    await _structured(p, model="claude-haiku-5-5")
    for body in reqs:
        assert body["model"] == "claude-haiku-5-5"
        assert body["output_config"]["effort"] == "low"
        assert "thinking" not in body
    assert reqs[1]["output_config"]["format"]["type"] == "json_schema"


async def test_large_max_tokens_streams() -> None:
    reqs: list[dict[str, Any]] = []
    p = make_anthropic_provider(structured=[{"answer": "x"}], requests=reqs)
    big = await _structured(p, max_tokens=32_000)
    small = await _structured(p, max_tokens=8_000)
    assert reqs[0]["stream"] is True
    assert reqs[1].get("stream") in (None, False)
    assert big.value == small.value == Out(answer="x")


async def test_usage_mapping_includes_cache_tokens() -> None:
    usage = {
        "input_tokens": 10,
        "cache_creation_input_tokens": 5,
        "cache_read_input_tokens": 20,
        "output_tokens": 7,
    }
    # The reply names a different model than the request: model_id must come from the reply.
    served = "claude-sonnet-5-5-20261101"
    p = make_anthropic_provider(structured=[{"answer": "x"}], usage=usage, response_model=served)
    expected = Usage(model_id=served, input_tokens=35, cached_input_tokens=20, output_tokens=7)
    for max_tokens in (50, 32_000):
        r = await _structured(p, model="claude-sonnet-5-5", max_tokens=max_tokens)
        assert r.usage == expected
    events = await _chat(p, model="claude-sonnet-5-5")
    done = events[-1]
    assert isinstance(done, StreamDone)
    assert done.usage == expected


async def test_stream_text_and_stop_reason() -> None:
    p = make_anthropic_provider(replies=["Hello there, friend."])
    events = await _chat(p)
    assert "".join(e.text for e in events if isinstance(e, TextDelta)) == "Hello there, friend."
    done = events[-1]
    assert isinstance(done, StreamDone)
    assert done.stop_reason == "end"


@pytest.mark.parametrize(
    ("reason", "expected"),
    [("end_turn", "end"), ("max_tokens", "max_tokens"), ("stop_sequence", "other")],
)
async def test_stream_stop_reason_mapping(reason: str, expected: str) -> None:
    async def handler(req: httpx2.Request) -> httpx2.Response:
        return message_response(json.loads(req.content), text="hi", stop_reason=reason)

    p = AnthropicProvider(mock_client(handler), effort="medium", request_timeout=30.0)
    done = (await _chat(p))[-1]
    assert isinstance(done, StreamDone)
    assert done.stop_reason == expected


def _status_handler(status: int, error_type: str) -> Any:
    async def handler(_req: httpx2.Request) -> httpx2.Response:
        return error_response(status, error_type)

    return handler


# Each case: a handler (or a provider scenario) and the error the adapter must raise.
ERROR_CASES: list[tuple[str, dict[str, Any], type[LLMError]]] = [
    ("429", {"error": LLMRateLimitError()}, LLMRateLimitError),
    ("529", {"error": LLMUnavailableError()}, LLMUnavailableError),
    ("500", {"status": (500, "api_error")}, LLMUnavailableError),
    ("408", {"status": (408, "timeout_error")}, LLMUnavailableError),
    ("400", {"status": (400, "invalid_request_error")}, LLMError),
    ("401", {"status": (401, "authentication_error")}, LLMError),
    ("refusal", {"error": LLMRefusalError()}, LLMRefusalError),
    ("max_tokens", {"error": LLMOutputValidationError()}, LLMOutputValidationError),
    ("invalid_json", {"structured": ["not json {"]}, LLMOutputValidationError),
    ("schema_mismatch", {"structured": [{"wrong": 1}]}, LLMOutputValidationError),
]


def _provider_for(case: dict[str, Any], api_key: str = "test-key") -> AnthropicProvider:
    if "status" in case:
        return AnthropicProvider(
            mock_client(_status_handler(*case["status"]), api_key=api_key),
            effort="medium",
            request_timeout=30.0,
        )
    return make_anthropic_provider(api_key=api_key, **case)


@pytest.mark.parametrize(
    ("case", "expected"), [(c, e) for _, c, e in ERROR_CASES], ids=[i for i, _, _ in ERROR_CASES]
)
@pytest.mark.parametrize("max_tokens", [50, 32_000], ids=["plain", "streamed"])
async def test_error_mapping(
    case: dict[str, Any], expected: type[LLMError], max_tokens: int
) -> None:
    with pytest.raises(LLMError) as info:
        await _structured(_provider_for(case), max_tokens=max_tokens)
    assert type(info.value) is expected
    if expected is LLMRateLimitError:
        assert isinstance(info.value, LLMRateLimitError)
        assert info.value.retry_after == 1.5


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        (c, e)
        for _, c, e in ERROR_CASES
        if "structured" not in c and e is not LLMOutputValidationError
    ],
)
async def test_stream_error_mapping(case: dict[str, Any], expected: type[LLMError]) -> None:
    with pytest.raises(LLMError) as info:
        await _chat(_provider_for(case))
    assert type(info.value) is expected


async def test_retry_after_missing_or_bad_is_none() -> None:
    for headers in ({}, {"retry-after": "soon"}):

        async def handler(_req: httpx2.Request, h: dict[str, str] = headers) -> httpx2.Response:
            return error_response(429, "rate_limit_error", headers=h)

        p = AnthropicProvider(mock_client(handler), effort="medium", request_timeout=30.0)
        with pytest.raises(LLMRateLimitError) as info:
            await _structured(p)
        assert info.value.retry_after is None


async def test_connection_error_is_unavailable() -> None:
    async def handler(req: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom", request=req)

    p = AnthropicProvider(mock_client(handler), effort="medium", request_timeout=30.0)
    with pytest.raises(LLMUnavailableError):
        await _structured(p)
    with pytest.raises(LLMUnavailableError):
        await _chat(p)


async def test_api_key_never_in_error() -> None:
    key = "sk-ant-SECRET-123"
    for _, case, expected in ERROR_CASES:
        for call in ("structured", "chat"):
            if call == "chat" and ("structured" in case or expected is LLMOutputValidationError):
                continue
            p = _provider_for(case, api_key=key)
            with pytest.raises(LLMError) as info:
                if call == "chat":
                    await _chat(p)
                else:
                    await _structured(p)
            exc = info.value
            assert "SECRET-123" not in str(exc)
            assert "SECRET-123" not in repr(exc)
            assert exc.__cause__ is None
            assert exc.__suppress_context__


async def test_no_prefill_no_tools() -> None:
    reqs: list[dict[str, Any]] = []
    p = make_anthropic_provider(structured=[{"answer": "x"}], requests=reqs)
    msgs = [
        ChatMessage(role="user", content="q1"),
        ChatMessage(role="assistant", content="a1"),
        ChatMessage(role="user", content="q2"),
    ]
    await _chat(p, messages=msgs)
    await _structured(p, messages=msgs)
    for body in reqs:
        assert body["messages"] == [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
        ]
        assert body["messages"][-1]["role"] == "user"
        assert "tools" not in body
        assert "tool_choice" not in body


def test_only_adapter_imports_sdk() -> None:
    pattern = re.compile(r"^\s*(import|from)\s+anthropic\b", re.MULTILINE)
    offenders = [
        str(p.relative_to(SRC))
        for p in SRC.rglob("*.py")
        if p != SRC / "llm" / "anthropic.py" and pattern.search(p.read_text())
    ]
    assert offenders == []
    assert pattern.search((SRC / "llm" / "anthropic.py").read_text())
