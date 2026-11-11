# 0019. LLM provider: Anthropic (Claude), one model per job; `temperature` removed from the Protocol

- **Status:** Accepted (owner, 2026-11-10). Amends ADR 0007 (the `temperature` parameter only).

## Context
Phase 2b (ADR 0012) needs one real LLM provider behind the ADR 0007 Protocols, for Knowledge Map extraction and flashcard generation (and, later, the 2c tutor and judge). Students may be 13–17 (ADR 0013), so provider data handling matters as much as price. The prices in `docs/planning-handoff.md` §3.1 were unverified. Everything below was re-checked on the providers' own pages on 2026-11-10.

**Prices (USD per 1M tokens: input / cache hit / output):**
- **Anthropic:**
  - `claude-haiku-5-5`: $0.10 / $0.01 / $0.50 for prompts up to 100k tokens; $0.50 / $0.05 / $2.50 above that.
  - `claude-sonnet-5-5`: $2 / $0.10 / $10.
  - `claude-opus-5-5`: $4 / $0.20 / $20.
  - Batch is half price.
- **OpenAI:** `gpt-6-luna` $0.10 / $0.01 / $0.50; `gpt-5-nano` $0.05 / $0.005 / $0.40; `gpt-6.1-terra` $1 / $0.05 / $5; `gpt-6.1-sol` $2 / $0.10 / $10.
- **Google:** `gemini-3.1-flash-lite` $0.25 / $1.50 (input / output); `gemini-3.8-flash` $0.75 / $3.75, doubling on 2027-01-01.

**Data handling:**
- **Anthropic:** API prompts and outputs are not retained by default, except for the "Covered Models" (Fable/Mythos), which require 30-day retention. API data is never used for training without express permission. Zero data retention (ZDR) is available through sales. Structured outputs are ZDR-eligible; only the JSON schema is cached, for up to 24 h.
- **OpenAI:** API data is not used for training by default. Abuse-monitoring logs are kept for up to 30 days. ZDR needs OpenAI's prior approval.
- **Google:** free-tier content is used to improve Google's products, so the free tier is unusable with student data. Paid-tier content is not used.

**Capabilities:** Claude structured outputs are GA on Haiku/Sonnet/Opus 5.5. The Python SDK's `messages.parse()` takes a Pydantic model. Schema limits: no recursive schemas, no `minLength`/`maxLength`/`minimum`/`maximum` on the wire; the SDK moves those constraints into descriptions and validates the response. Prompt caching needs a prefix of at least ~512 tokens on these models; shorter prefixes silently don't cache. Rate limits on the entry tier are 4,000 RPM and 2M input tokens per minute per model.

**API change:** API version `2026-10-21` removed `temperature`, `top_p` and `top_k`. A request that sends any of them gets a 400 on every model. The ADR 0007 Protocol has a `temperature` argument on both `stream_chat` and `generate_structured`.

## Options
**Provider:**
1. **Anthropic.**
2. OpenAI: comparable cheap-tier price; 30-day abuse logs by default.
3. Google Gemini (paid tier): higher cheap-tier prices; a scheduled price rise.

**Models:**
1. **Sonnet 5.5 for the Knowledge Map, Haiku 5.5 for cards.**
2. Haiku for both.
3. Sonnet for both.

**`temperature`:**
1. **Remove it from the Protocol.**
2. Keep it and have the adapter ignore it.

## Decision
- **Provider: Anthropic (Claude API, first-party),** through the official `anthropic` Python SDK. It is a new API dependency, used only in the adapter module.
  - The adapter (`llm/anthropic.py`, or the name the 2b plan chooses) implements `LLMProvider` and must pass `api/tests/llm/test_contract.py`.
  - Structured output uses the SDK's structured-output support; the 2b design states the exact call.
  - `PromptBlock.cache=True` maps to `cache_control`.
  - `Usage` is filled from the response's `usage`, including cache reads.
  - The key comes from env (`ANTHROPIC_API_KEY`); there is no key in git.
- **Models are settings, one per job:**
  - Knowledge Map extraction: `claude-sonnet-5-5`.
  - Flashcard generation: `claude-haiku-5-5`.
  - Changing a model is a configuration change. The 2c tutor and judge models are decided in 2c.
- **Tests and CI never call the real provider.** Unit and job tests use `FakeLLMProvider`. An optional live smoke test runs only when a key is present (skipped otherwise, never in CI).
- **ADR 0007 amended:** `temperature` is removed from `LLMProvider.stream_chat` and `LLMProvider.generate_structured`. The fakes and contract tests change to match. Depth and cost are controlled per call by the adapter through Claude's `effort` setting, which is not part of the Protocol. The 2b design picks the levels.
- **Minors (ADR 0013):** Anthropic's guidelines for organisations serving minors apply:
  - users are told they are interacting with an AI system
  - compliance is stated publicly
  - age-appropriate safeguards are in place
  The 2b UI labels generated content as AI-generated. The public statement belongs with the deployment and landing work (Phase 3+). The tutor's safeguards are a 2c design item.
- No ZDR contract for the MVP: the default already does not retain prompts or outputs. Covered Models (Fable/Mythos), which require 30-day retention, are not used.

## Consequences
- One new dependency (`anthropic`).
- The owner needs an Anthropic Console account and API key for the manual end-to-end check only. Development and tests run on fakes.
- The Phase 3 provider bake-off (§2.9) can still add an OpenAI adapter behind the same Protocol.
- Haiku 5.5's higher price for prompts over 100k tokens is a reason to chunk long documents (2b design).
