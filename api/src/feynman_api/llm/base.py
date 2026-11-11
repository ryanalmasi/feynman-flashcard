from collections.abc import AsyncIterator, Sequence
from typing import Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class PromptBlock(BaseModel):
    text: str
    # cache=True: adapter applies provider prompt caching up to this block;
    # providers without explicit caching ignore it.
    cache: bool = False


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Usage(BaseModel):
    model_id: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0


class TextDelta(BaseModel):
    text: str


class StreamDone(BaseModel):
    usage: Usage
    stop_reason: Literal["end", "max_tokens", "refusal", "other"]


class StructuredResult(BaseModel, Generic[T]):  # noqa: UP046 (spec 7.4 verbatim)
    value: T
    usage: Usage


class LLMProvider(Protocol):
    def stream_chat(
        self,
        *,
        model: str,
        system: Sequence[PromptBlock],
        messages: Sequence[ChatMessage],
        max_tokens: int,
    ) -> AsyncIterator[TextDelta | StreamDone]: ...

    # yields zero or more TextDelta, then exactly one StreamDone, last

    async def generate_structured(
        self,
        *,
        model: str,
        system: Sequence[PromptBlock],
        messages: Sequence[ChatMessage],
        schema: type[T],
        max_tokens: int,
    ) -> StructuredResult[T]: ...


class Embedder(Protocol):
    model_id: str
    dimensions: int

    # async; CPU-bound adapters run in a thread pool
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...
