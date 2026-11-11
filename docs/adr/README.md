# Architecture Decision Records

One file per decision: `NNNN-short-title.md`. Each records the context, the options considered, the decision, and its consequences. ADRs are **approved by the owner** before any code depends on them. To change a decision, write a new ADR that supersedes the old one; don't edit history.

| # | Title | Status | Date |
|---|---|---|---|
| [0001](0001-backend-fastapi.md) | Backend: Python + FastAPI | Accepted | 2026-11-08 |
| [0002](0002-frontend-vite-react-ts.md) | Frontend: Vite + React + TypeScript SPA | Accepted | 2026-11-08 |
| [0003](0003-repo-layout.md) | Repo layout: `api/ web/ infra/ docs/` | Accepted | 2026-11-08 |
| [0004](0004-database-migrations-roles.md) | Postgres 18, SQLAlchemy 2 async + Alembic, least-privilege roles | Accepted | 2026-11-08 |
| [0005](0005-auth.md) | Auth: own server-side sessions; email+password in MVP, Google next | Accepted | 2026-11-08 |
| [0006](0006-config-secrets.md) | Config and secrets | Accepted | 2026-11-08 |
| [0007](0007-llm-provider-abstraction.md) | LLM provider abstraction: own thin interface | Accepted (amended by 0019) | 2026-11-08 |
| [0008](0008-background-jobs.md) | Background jobs: Postgres-backed queue + worker | Accepted | 2026-11-08 |
| [0009](0009-testing-lint-ci.md) | Testing, lint, format, CI | Accepted | 2026-11-08 |
| [0010](0010-old-prototype-code.md) | Old prototype: clean restart, keep images | Accepted | 2026-11-08 |
| [0011](0011-git-workflow.md) | Git workflow: phase branches, pushed, draft PR, owner merges | Accepted | 2026-11-08 |
| [0012](0012-mvp-scope-and-phase-2-split.md) | MVP scope confirmed; Phase 2 split into 2a/2b/2c | Accepted | 2026-11-09 |
| [0013](0013-age-policy.md) | Age policy: 13+ neutral age screen, no birth date stored | Accepted | 2026-11-09 |
| [0014](0014-ui-styling.md) | UI styling: Tailwind CSS + shadcn/ui, swappable theme tokens | Accepted | 2026-11-09 |
| [0015](0015-job-queue-own-table.md) | Job queue: own `jobs` table and worker (implements 0008) | Accepted | 2026-11-09 |
| [0016](0016-file-storage.md) | File storage: local disk behind `FileStore`; 20 MB / 200 pages, text PDFs only | Accepted | 2026-11-09 |
| [0017](0017-auth-security-details.md) | Auth security details: 12-char min, HIBP, Postgres rate limits, CSRF token, hashed sessions | Accepted | 2026-11-09 |
| [0018](0018-study-content-model-and-pdf-library.md) | Study content model (one PDF per set) and pypdfium2 for PDF text | Accepted | 2026-11-09 |
| [0019](0019-llm-provider-anthropic.md) | LLM provider: Anthropic; Sonnet 5.5 for the map, Haiku 5.5 for cards; `temperature` removed | Accepted | 2026-11-10 |
| [0020](0020-knowledge-map.md) | Knowledge Map: schema, editing + reorder, chunked extraction with resume, limits, cost guard | Accepted | 2026-11-10 |
| [0021](0021-generated-flashcards.md) | Generated flashcards: on request, by importance, Q/A + cloze, draft tray, safe regeneration | Accepted | 2026-11-10 |
