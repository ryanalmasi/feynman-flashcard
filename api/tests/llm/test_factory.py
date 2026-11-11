import asyncio
import json
import subprocess
import sys
from collections.abc import AsyncIterator

import httpx2
import pytest
from pydantic import BaseModel

from feynman_api.config import Settings
from feynman_api.llm import ChatMessage, LLMUnavailableError
from feynman_api.llm.anthropic import AnthropicProvider
from feynman_api.llm.factory import build_llm_provider
from llm.anthropic_mock import message_response, mock_client

DB = "postgresql+asyncpg://u:p@localhost/db"


class Out(BaseModel):
    answer: str


def _settings(**kw: object) -> Settings:
    return Settings(database_url=DB, _env_file=None, **kw)  # type: ignore[arg-type]


def test_factory_disabled_returns_none() -> None:
    assert build_llm_provider(_settings()) is None
    assert build_llm_provider(_settings(llm_enabled=False, anthropic_api_key="k")) is None


@pytest.mark.parametrize("key", [None, ""])
def test_factory_enabled_without_key_raises(key: str | None) -> None:
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        build_llm_provider(_settings(llm_enabled=True, anthropic_api_key=key))


def test_factory_builds_provider_with_retries_off() -> None:
    provider = build_llm_provider(
        _settings(llm_enabled=True, anthropic_api_key="test-key", llm_effort="low")
    )
    assert isinstance(provider, AnthropicProvider)
    assert provider.client.max_retries == 0


async def test_total_deadline_maps_to_unavailable() -> None:
    async def slow(_req: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(0.2)
        raise AssertionError("the deadline should have fired first")

    p = AnthropicProvider(mock_client(slow), effort="medium", request_timeout=0.05)
    msgs = [ChatMessage(role="user", content="hi")]
    with pytest.raises(LLMUnavailableError) as info:
        await p.generate_structured(model="m", system=[], messages=msgs, schema=Out, max_tokens=50)
    assert info.value.__suppress_context__
    with pytest.raises(LLMUnavailableError):
        await p.generate_structured(
            model="m", system=[], messages=msgs, schema=Out, max_tokens=32_000
        )
    with pytest.raises(LLMUnavailableError):
        async for _e in p.stream_chat(model="m", system=[], messages=msgs, max_tokens=50):
            pass


async def test_total_deadline_covers_a_slow_stream() -> None:
    """Headers arrive, then the body stalls: the deadline still fires (httpx's is per read)."""

    async def stalled(req: httpx2.Request) -> httpx2.Response:
        first = message_response(json.loads(req.content), text="hello", stop_reason="end_turn")
        head = first.content.split(b"\n\n")[0] + b"\n\n"

        async def body() -> AsyncIterator[bytes]:
            yield head
            await asyncio.sleep(0.2)
            yield b""

        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body())

    p = AnthropicProvider(mock_client(stalled), effort="medium", request_timeout=0.05)
    msgs = [ChatMessage(role="user", content="hi")]
    with pytest.raises(LLMUnavailableError):
        async for _e in p.stream_chat(model="m", system=[], messages=msgs, max_tokens=50):
            pass
    with pytest.raises(LLMUnavailableError):
        await p.generate_structured(
            model="m", system=[], messages=msgs, schema=Out, max_tokens=32_000
        )


def test_importing_factory_does_not_load_sdk() -> None:
    code = (
        "import sys, feynman_api.llm.factory, feynman_api.llm; "
        "sys.exit(1 if 'anthropic' in sys.modules else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, check=False)  # noqa: S603
    assert result.returncode == 0, result.stderr.decode()
