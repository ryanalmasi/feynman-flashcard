"""Contract tests written against the LLMProvider and Embedder Protocols.

Phase 2 adapters add their factory to the fixture params below.
"""

import inspect
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from feynman_api.llm import (
    ChatMessage,
    Embedder,
    FakeCall,
    FakeEmbedder,
    FakeLLMProvider,
    LLMError,
    LLMOutputValidationError,
    LLMProvider,
    LLMRateLimitError,
    LLMRefusalError,
    LLMUnavailableError,
    PromptBlock,
    StreamDone,
    TextDelta,
)
from llm.anthropic_mock import make_anthropic_provider

ProviderFactory = Callable[..., LLMProvider]

_: LLMProvider = FakeLLMProvider()
_e: Embedder = FakeEmbedder()

MSGS = [ChatMessage(role="user", content="hi")]


class Out(BaseModel):
    answer: str


def _fake_factory(
    *,
    replies: tuple[str, ...] | list[str] = ("Fake reply.",),
    structured: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    error: LLMError | None = None,
) -> LLMProvider:
    return FakeLLMProvider(replies=replies, structured=structured, error=error)


@pytest.fixture(params=[_fake_factory, make_anthropic_provider], ids=["fake", "anthropic"])
def provider_factory(request: pytest.FixtureRequest) -> ProviderFactory:
    factory: ProviderFactory = request.param
    return factory


@pytest.fixture
def provider(provider_factory: ProviderFactory) -> LLMProvider:
    return provider_factory()


@pytest.fixture(params=[FakeEmbedder])
def embedder(request: pytest.FixtureRequest) -> Embedder:
    factory: Callable[[], Embedder] = request.param
    return factory()


async def test_stream_yields_deltas_then_single_done_last(provider: LLMProvider) -> None:
    events = [
        e
        async for e in provider.stream_chat(
            model="m", system=[PromptBlock(text="sys")], messages=MSGS, max_tokens=50
        )
    ]
    assert all(isinstance(e, TextDelta) for e in events[:-1])
    assert isinstance(events[-1], StreamDone)
    assert sum(isinstance(e, StreamDone) for e in events) == 1


async def test_stream_usage_reports_model(provider: LLMProvider) -> None:
    events = [
        e
        async for e in provider.stream_chat(
            model="m", system=[PromptBlock(text="sys")], messages=MSGS, max_tokens=50
        )
    ]
    done = events[-1]
    assert isinstance(done, StreamDone)
    assert done.usage.model_id == "m"
    assert done.usage.input_tokens > 0
    assert done.usage.output_tokens >= 0


async def test_structured_returns_validated_instance(provider_factory: ProviderFactory) -> None:
    result = await provider_factory(structured=[{"answer": "42"}]).generate_structured(
        model="m", system=[], messages=MSGS, schema=Out, max_tokens=50
    )
    assert result.value == Out(answer="42")
    assert result.usage.model_id == "m"


async def test_structured_invalid_payload_raises(provider_factory: ProviderFactory) -> None:
    with pytest.raises(LLMOutputValidationError):
        await provider_factory(structured=[{"wrong": 1}]).generate_structured(
            model="m", system=[], messages=MSGS, schema=Out, max_tokens=50
        )


@pytest.mark.parametrize(
    "err",
    [
        LLMRateLimitError(retry_after=1.5),
        LLMUnavailableError("x"),
        LLMRefusalError("x"),
        LLMOutputValidationError("x"),
    ],
)
async def test_errors_propagate_from_structured(
    provider_factory: ProviderFactory, err: LLMError
) -> None:
    p = provider_factory(error=err)
    with pytest.raises(type(err)):
        await p.generate_structured(model="m", system=[], messages=MSGS, schema=Out, max_tokens=5)


# A chat stream cannot fail output validation, so that error is not exercised here.
@pytest.mark.parametrize(
    "err",
    [LLMRateLimitError(retry_after=1.5), LLMUnavailableError("x"), LLMRefusalError("x")],
)
async def test_errors_propagate_from_stream(
    provider_factory: ProviderFactory, err: LLMError
) -> None:
    p = provider_factory(error=err)
    with pytest.raises(type(err)):
        async for _event in p.stream_chat(model="m", system=[], messages=MSGS, max_tokens=5):
            pytest.fail("stream_chat must raise before yielding")


def test_protocol_has_no_temperature() -> None:
    for name in ("stream_chat", "generate_structured"):
        assert "temperature" not in inspect.signature(getattr(LLMProvider, name)).parameters
        assert "temperature" not in inspect.signature(getattr(FakeLLMProvider, name)).parameters


async def test_fake_records_calls_and_uses_responder() -> None:
    p = FakeLLMProvider(responder=lambda c: {"answer": c.model})
    r1 = await p.generate_structured(
        model="m1", system=[PromptBlock(text="s")], messages=MSGS, schema=Out, max_tokens=7
    )
    r2 = await p.generate_structured(model="m2", system=[], messages=MSGS, schema=Out, max_tokens=8)
    assert (r1.value.answer, r2.value.answer) == ("m1", "m2")
    assert [c.model for c in p.calls] == ["m1", "m2"]
    c = p.calls[0]
    assert c == FakeCall(
        method="structured",
        model="m1",
        system=(PromptBlock(text="s"),),
        messages=tuple(MSGS),
        schema=Out,
        max_tokens=7,
    )


async def test_fake_responder_errors_propagate() -> None:
    def boom(_c: FakeCall) -> dict[str, Any]:
        raise LLMUnavailableError("down")

    p = FakeLLMProvider(responder=boom)
    with pytest.raises(LLMUnavailableError):
        await p.generate_structured(model="m", system=[], messages=MSGS, schema=Out, max_tokens=5)
    assert len(p.calls) == 1


async def test_fake_async_responder_is_awaited() -> None:
    async def respond(_c: FakeCall) -> dict[str, Any]:
        return {"answer": "async"}

    p = FakeLLMProvider(responder=respond)
    r = await p.generate_structured(model="m", system=[], messages=MSGS, schema=Out, max_tokens=5)
    assert r.value.answer == "async"


async def test_fake_records_stream_call_even_on_error() -> None:
    p = FakeLLMProvider(error=LLMUnavailableError("x"))
    with pytest.raises(LLMUnavailableError):
        async for _e in p.stream_chat(model="m", system=[], messages=MSGS, max_tokens=5):
            pass
    assert p.calls[0].method == "stream"
    assert p.calls[0].schema is None


async def test_rate_limit_carries_retry_after() -> None:
    assert LLMRateLimitError(retry_after=1.5).retry_after == 1.5
    assert LLMRateLimitError().retry_after is None


async def test_cached_tokens_counted() -> None:
    p = FakeLLMProvider()
    events = [
        e
        async for e in p.stream_chat(
            model="m",
            system=[PromptBlock(text="a b c", cache=True), PromptBlock(text="d")],
            messages=MSGS,
            max_tokens=50,
        )
    ]
    done = events[-1]
    assert isinstance(done, StreamDone)
    assert done.usage.cached_input_tokens == 3
    assert done.usage.input_tokens == 5


async def test_replies_consumed_in_order_and_cycle() -> None:
    p = FakeLLMProvider(replies=("one", "two"), chunk_size=2)

    async def run() -> str:
        events = [e async for e in p.stream_chat(model="m", system=[], messages=MSGS, max_tokens=5)]
        return "".join(e.text for e in events if isinstance(e, TextDelta))

    assert [await run(), await run(), await run()] == ["one", "two", "one"]


async def test_embed_shape_and_determinism(embedder: Embedder) -> None:
    v = await embedder.embed(["a", "b"])
    assert len(v) == 2
    assert all(len(x) == embedder.dimensions for x in v)
    assert await embedder.embed(["a"]) == [v[0]]
    assert v[0] != v[1]


async def test_embed_vectors_are_normalized() -> None:
    (v,) = await FakeEmbedder(dimensions=16).embed(["hello"])
    assert abs(sum(x * x for x in v) - 1.0) < 1e-9


async def test_embed_empty(embedder: Embedder) -> None:
    assert await embedder.embed([]) == []
