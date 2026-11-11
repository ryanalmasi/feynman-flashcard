"""Opt-in live call to the Claude API. Never runs in CI.

Run manually with RUN_LIVE_LLM=1 and ANTHROPIC_API_KEY set in the environment.
"""

import os

import pytest
from pydantic import BaseModel

from feynman_api.llm import ChatMessage, PromptBlock
from feynman_api.llm.anthropic import build_anthropic_provider


class Capital(BaseModel):
    city: str


@pytest.mark.allow_network
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM") != "1" or not os.environ.get("ANTHROPIC_API_KEY"),
    reason="live LLM test is opt-in",
)
async def test_live_structured_haiku() -> None:
    provider = build_anthropic_provider(
        os.environ["ANTHROPIC_API_KEY"], effort="low", request_timeout=60.0
    )
    result = await provider.generate_structured(
        model="claude-haiku-5-5",
        system=[PromptBlock(text="Answer with the city name only.")],
        messages=[ChatMessage(role="user", content="What is the capital of France?")],
        schema=Capital,
        max_tokens=1024,
    )
    assert isinstance(result.value, Capital)
    assert result.value.city
    assert result.usage.input_tokens > 0
