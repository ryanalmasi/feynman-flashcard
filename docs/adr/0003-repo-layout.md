# 0003. Repo layout: `api/ web/ infra/ docs/`

- **Status:** Accepted (owner, 2026-11-08)

## Options
1. **One repo with flat top-level folders**, and no monorepo tooling.
2. `apps/api` + `apps/web`. The same idea with one extra level of nesting, which only pays off if more apps are added.
3. Two repos. Doubles the CI and PRs and makes it hard to keep the API and its client in sync.

## Decision
Option 1:
```
api/      FastAPI service (own pyproject.toml, uv.lock, alembic/, tests/)
web/      Vite React app (own package.json, package-lock.json)
infra/    docker-compose.yml, Postgres init scripts
docs/     ADRs, implementation plan, planning doc
Makefile  one-command entry points (db, api, web, test, lint, gen-types)
```

## Consequences
The old `backend/`, `frontend/`, and root `requirements.txt` are removed from the working tree (0010). One CI workflow covers both apps.
