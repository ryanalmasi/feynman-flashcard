"""Contract tests written against the LLMProvider and Embedder Protocols.

Phase 2 adapters add their factory to the fixture params below.
"""

from collections.abc import Callable

import pytest
from pydantic import BaseModel

from feynman_api.llm import (
    ChatMessage,
    Embedder,
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

_: LLMProvider = FakeLLMProvider()
_e: Embedder = FakeEmbedder()

MSGS = [ChatMessage(role="user", content="hi")]


class Out(BaseModel):
    answer: str


@pytest.fixture(params=[FakeLLMProvider])
def provider_factory(request: pytest.FixtureRequest) -> Callable[..., LLMProvider]:
    factory: Callable[..., LLMProvider] = request.param
    return factory


@pytest.fixture
def provider(provider_factory: Callable[..., LLMProvider]) -> LLMProvider:
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


async def test_structured_returns_validated_instance() -> None:
    result = await FakeLLMProvider(structured=[{"answer": "42"}]).generate_structured(
        model="m", system=[], messages=MSGS, schema=Out, max_tokens=50
    )
    assert result.value == Out(answer="42")
    assert result.usage.model_id == "m"


async def test_structured_invalid_payload_raises() -> None:
    with pytest.raises(LLMOutputValidationError):
        await FakeLLMProvider(structured=[{"wrong": 1}]).generate_structured(
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
async def test_errors_propagate_from_both_methods(err: LLMError) -> None:
    assert isinstance(err, LLMError)
    p = FakeLLMProvider(error=err)
    with pytest.raises(type(err)):
        async for _event in p.stream_chat(model="m", system=[], messages=MSGS, max_tokens=5):
            pytest.fail("stream_chat must raise before yielding")
    with pytest.raises(type(err)):
        await p.generate_structured(model="m", system=[], messages=MSGS, schema=Out, max_tokens=5)


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
