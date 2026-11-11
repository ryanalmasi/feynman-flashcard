# 0007. LLM provider abstraction: own thin interface

- **Status:** Accepted (owner, 2026-11-08). Amended by [0019](0019-llm-provider-anthropic.md) (2026-11-10): `temperature` is removed from both Protocol methods.

## Context
The provider is not chosen yet (P2, and later a bake-off, planning doc §3.1/§2.9). Switching must stay cheap. Prompt caching is what keeps session costs low (§4), so provider-specific features must stay reachable. MVP usage logging needs token counts from every call.

## Options
1. **Own thin interface + per-provider adapters on the official SDKs.** About 100 lines, full control, and caching stays available.
2. LiteLLM. One call shape for 100+ providers, but it is a heavy dependency that changes often and can hide caching controls.
3. An agent framework (Pydantic AI, LangChain). More structure than a single prompted tutor conversation needs.

## Decision
Option 1. Typed `Protocol`s live in `api/src/feynman_api/llm/`:
- `LLMProvider.stream_chat(...)` → async iterator of text deltas, ending with a final event that carries `Usage`.
- `LLMProvider.generate_structured(..., schema: type[BaseModel])` → a validated Pydantic instance plus `Usage`.
- `Usage` = model id, input tokens, output tokens, cached input tokens.
- A separate `Embedder` protocol: `embed(texts) -> list[list[float]]` plus `model_id`, because the baseline uses a local model (0001).

**Phase 1 builds only the interfaces, a deterministic `FakeLLMProvider` / `FakeEmbedder`, and contract tests.** No vendor SDK is installed until the Phase 2 provider decision.

## Consequences
Adding a provider means one adapter file that passes the same contract tests. Every call site receives `Usage`, so usage logging (Phase 2) cannot be skipped by accident.
