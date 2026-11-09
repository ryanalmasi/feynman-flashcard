# feynman-flashcard

A study tool built around the Feynman technique: you teach a topic to an AI, get a multi-stage score and feedback, and review flashcards generated from your material.
Today the repo holds the **Phase 1 foundation only** (FastAPI + Postgres + Vite React TS skeleton with a health check); the product features come in Phase 2.

## Prerequisites

Machine setup (WSL, Docker Engine, uv, Node 26, make, gh, gitleaks, pre-commit) is in [`docs/setup-prerequisites.md`](docs/setup-prerequisites.md). Its last step must print `ALL PREREQUISITES OK`.

## First-time setup

From the repo root:

```bash
make env                # generate gitignored .env files with random dev passwords
make db                 # start Postgres 18 in Docker
make migrate            # apply database migrations
(cd api && uv sync)     # install Python dependencies
(cd web && npm ci)      # install JavaScript dependencies
```

## Daily use

```bash
make db     # start the database (if not running)
make api    # API on http://127.0.0.1:8000
make web    # web app on http://localhost:5173
```

- Web app: <http://localhost:5173> (shows "API: ok" and "Database: ok" when everything is wired up)
- API health check: <http://localhost:8000/health>

Use `localhost` (not `127.0.0.1`) for the web app, because the API's CORS origin is `http://localhost:5173`.

## Checks

```bash
make check      # lint, tests, web build, and generated-types drift check
```

`make check` needs the database running (`make db` first): the pytest DB tests fail otherwise.

CI (`.github/workflows/ci.yml`) runs the same checks plus secret scanning. **CI status: pending.** The workflow has not run successfully yet because of a GitHub account billing lock; it needs a re-run once that is resolved.

`make db-reset` stops Postgres and **deletes the local database volume (all local DB data is lost)**, then recreates it. Use it only if the DB was created with different credentials or you want a clean slate.

Other targets: `make test`, `make lint`, `make gen-types`, `make db-down`, `make db-psql`.

## Where decisions live

Architecture decisions are recorded as ADRs in [`docs/adr/`](docs/adr/README.md). The roadmap and open decisions are in [`docs/planning-handoff.md`](docs/planning-handoff.md); the Phase 1 plan is [`docs/implementation-plan.md`](docs/implementation-plan.md). Project state is in [`memory.md`](memory.md) and contributor/agent guidance in [`CLAUDE.md`](CLAUDE.md).

The Jan-2025 prototype is in git history at `5aba556`.

## License

MIT, see [`LICENSE`](LICENSE).
