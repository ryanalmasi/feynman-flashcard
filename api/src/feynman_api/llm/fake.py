"""Deterministic fakes for tests. Never imported by any route."""

import hashlib
import math
from collections.abc import AsyncIterator, Sequence
from typing import Any

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
from feynman_api.llm.errors import LLMError, LLMOutputValidationError


def _words(text: str) -> int:
    return len(text.split())


class FakeLLMProvider:
    def __init__(
        self,
        *,
        replies: Sequence[str] = ("Fake reply.",),
        structured: Sequence[dict[str, Any]] = (),
        error: LLMError | None = None,
        chunk_size: int = 4,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        self._replies = tuple(replies) or ("Fake reply.",)
        self._structured = tuple(structured)
        self._error = error
        self._chunk_size = chunk_size
        self._reply_i = 0
        self._structured_i = 0

    def _usage(
        self,
        model: str,
        system: Sequence[PromptBlock],
        messages: Sequence[ChatMessage],
        output: str,
    ) -> Usage:
        last_cached = max((i for i, b in enumerate(system) if b.cache), default=-1)
        return Usage(
            model_id=model,
            input_tokens=sum(_words(b.text) for b in system)
            + sum(_words(m.content) for m in messages),
            output_tokens=_words(output),
            cached_input_tokens=sum(_words(b.text) for b in system[: last_cached + 1]),
        )

    async def stream_chat(
        self,
        *,
        model: str,
        system: Sequence[PromptBlock],
        messages: Sequence[ChatMessage],
        max_tokens: int,
        temperature: float = 0.7,
    ) -> AsyncIterator[TextDelta | StreamDone]:
        if self._error is not None:
            raise self._error
        reply = self._replies[self._reply_i % len(self._replies)]
        self._reply_i += 1
        for i in range(0, len(reply), self._chunk_size):
            yield TextDelta(text=reply[i : i + self._chunk_size])
        yield StreamDone(usage=self._usage(model, system, messages, reply), stop_reason="end")

    async def generate_structured(
        self,
        *,
        model: str,
        system: Sequence[PromptBlock],
        messages: Sequence[ChatMessage],
        schema: type[T],
        max_tokens: int,
        temperature: float = 0.0,
    ) -> StructuredResult[T]:
        if self._error is not None:
            raise self._error
        if not self._structured:
            raise LLMOutputValidationError("FakeLLMProvider has no structured payloads")
        payload = self._structured[self._structured_i % len(self._structured)]
        self._structured_i += 1
        try:
            value = schema.model_validate(payload)
        except ValidationError as exc:
            raise LLMOutputValidationError("structured payload failed schema validation") from exc
        return StructuredResult[T](
            value=value,
            usage=self._usage(model, system, messages, str(payload)),
        )


class FakeEmbedder:
    model_id = "fake-embedder-v1"

    def __init__(self, dimensions: int = 8) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be >= 1")
        self.dimensions = dimensions

    def _vector(self, text: str) -> list[float]:
        raw: list[float] = []
        counter = 0
        while len(raw) < self.dimensions:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            raw.extend((b - 127.5) / 127.5 for b in digest)
            counter += 1
        raw = raw[: self.dimensions]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]
