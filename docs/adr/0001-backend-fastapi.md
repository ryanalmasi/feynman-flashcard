# 0001. Backend: Python + FastAPI

- **Status:** Accepted (owner, 2026-11-08)

## Context
The backend must stream tutor chat, run a deterministic scoring baseline (embeddings), extract text from PDFs, and request structured LLM output. The prototype's Flask app is being replaced (see 0010).

## Options
1. **FastAPI (Python).** Async, native SSE streaming, Pydantic models that double as LLM JSON schemas, and the Python PDF and embedding ecosystem (PyMuPDF, sentence-transformers). The downside is two languages (Python + TS).
2. **Full-stack TypeScript (Next.js / Hono).** One language and shared types. Embeddings would have to be a hosted API, so the "objective" baseline would depend on a vendor model. PDF tooling is weaker.

## Decision
**FastAPI on Python 3.13**, with dependencies managed by `uv`. To limit the two-language cost, the frontend's API types are generated from FastAPI's OpenAPI schema (see 0009).

## Consequences
- Embeddings for the baseline (planning doc §3.3, P1 #4) will use a **local sentence-transformers model**. The exact model is picked in Phase 2; `bert-base-nli-mean-tokens` is not reused. It sits behind the `Embedder` interface (0007).
- Heavy ML dependencies (torch) are **not** installed in Phase 1.
