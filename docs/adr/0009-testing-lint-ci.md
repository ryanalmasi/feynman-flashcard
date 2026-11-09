# 0009. Testing, lint, format, CI

- **Status:** Accepted (owner, 2026-11-08). Biome was considered instead of ESLint+Prettier and declined: ESLint+Prettier is the default choice with the larger ecosystem.

## Decision
**API (`api/`):** `uv` (lockfile committed, which pins dependencies), `ruff` (lint + format), `mypy --strict`, `pytest` + `pytest-asyncio` + `httpx.AsyncClient`. Tests run against **real Postgres** (the Compose service locally, a service container in CI), never SQLite, because role permissions must be testable.

**Web (`web/`):** npm (`package-lock.json` committed), `tsc --noEmit`, ESLint (flat config) + Prettier, Vitest + React Testing Library. API types are generated from the FastAPI OpenAPI schema with `openapi-typescript` into a committed file. The client is `openapi-fetch`. CI fails if the regenerated types differ from the committed file.

**CI:** GitHub Actions `.github/workflows/ci.yml`, on pull requests and pushes to `main` and `phase-*` branches. Jobs:
- `api`: ruff check, ruff format --check, mypy, Alembic upgrade → downgrade → upgrade, pytest. Runs with a Postgres 18 service.
- `web`: lint, format check, typecheck, test, build, OpenAPI type drift check.
- `secrets`: gitleaks over the pushed commits.

**Local:** `pre-commit` runs ruff, ruff-format, gitleaks, and basic file hygiene hooks. `make lint` / `make test` mirror CI.
