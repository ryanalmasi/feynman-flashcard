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
| [0007](0007-llm-provider-abstraction.md) | LLM provider abstraction: own thin interface | Accepted | 2026-11-08 |
| [0008](0008-background-jobs.md) | Background jobs: Postgres-backed queue + worker | Accepted | 2026-11-08 |
| [0009](0009-testing-lint-ci.md) | Testing, lint, format, CI | Accepted | 2026-11-08 |
| [0010](0010-old-prototype-code.md) | Old prototype: clean restart, keep images | Accepted | 2026-11-08 |
| [0011](0011-git-workflow.md) | Git workflow: phase branches, pushed, draft PR, owner merges | Accepted | 2026-11-08 |
