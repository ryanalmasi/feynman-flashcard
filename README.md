# feynman-flashcard

A study tool built around the Feynman technique: you teach a topic to an AI, get a multi-stage score and feedback, and review flashcards generated from your material.
Today the repo holds the Phase 1 foundation plus **Phase 2a** (on a draft PR, pending merge): accounts, study sets and flashcards, a review screen, and PDF upload with text extraction. The tutor, scoring, feedback and generated flashcards come in Phase 2b/2c.

### What works

- Register (13+ age screen), log in/out, delete your account.
- Create, edit and delete study sets and flashcards; review a set (flip and shuffle).
- Upload one PDF per set (up to 20 MB, 200 pages, text-based only); its status goes from processing to ready or failed. **The worker (`make worker`) must be running for uploads to finish.**

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
make worker # background worker (PDF extraction); needed for uploads to finish
make web    # web app on http://localhost:5173
```

`make env` writes `SESSION_COOKIE_SECURE=false` into `api/.env` for plain-http local dev; the code default is secure cookies, so keep it `true` anywhere served over HTTPS.

- Web app: <http://localhost:5173> (redirects to `/sets`, or to `/login` when signed out); the status page is at `/status` and shows "API: ok" and "Database: ok" when everything is wired up
- API health check: <http://localhost:8000/health>

Use `localhost` (not `127.0.0.1`) for the web app, because the API's CORS origin is `http://localhost:5173`.

## Checks

```bash
make check      # lint, tests, web build, and generated-types drift check
```

`make check` needs the database running (`make db` first): the pytest DB tests fail otherwise.

CI (`.github/workflows/ci.yml`) runs the same checks plus secret scanning. It was green on Phase 1; for Phase 2a see the PR.

`make db-reset` stops Postgres and **deletes the local database volume (all local DB data is lost)**, then recreates it. Use it only if the DB was created with different credentials or you want a clean slate.

Other targets: `make test`, `make lint`, `make gen-types`, `make db-down`, `make db-psql`.

## Where decisions live

Architecture decisions are recorded as ADRs in [`docs/adr/`](docs/adr/README.md). The roadmap and open decisions are in [`docs/planning-handoff.md`](docs/planning-handoff.md); the Phase 1 and 2a plans are [`docs/implementation-plan.md`](docs/implementation-plan.md) and [`docs/implementation-plan-phase-2a.md`](docs/implementation-plan-phase-2a.md). Project state is in [`memory.md`](memory.md) and contributor/agent guidance in [`CLAUDE.md`](CLAUDE.md).

The Jan-2025 prototype is in git history at `5aba556`.

## License

MIT, see [`LICENSE`](LICENSE).
