# feynman-flashcard

A study tool built around the Feynman technique: you teach a topic to an AI, get a multi-stage score and feedback, and review flashcards generated from your material.
Today the repo holds the Phase 1 foundation, **Phase 2a** (merged: accounts, study sets and flashcards, a review screen, PDF upload with text extraction) and **Phase 2b** (on a draft PR, pending merge: the Knowledge Map and AI-generated flashcards). The tutor, scoring and feedback come in Phase 2c.

### What works

- Register (13+ age screen), log in/out, delete your account.
- Create, edit and delete study sets and flashcards; review a set (flip and shuffle).
- Upload one PDF per set (up to 20 MB, 200 pages, text-based only); its status goes from processing to ready or failed. **The worker (`make worker`) must be running for uploads to finish.**
- **Knowledge Map (2b):** after a PDF is extracted, the worker builds an editable map of its concepts (title, explanation, importance, key terms, misconceptions, source pages). You can edit, add, delete and reorder concepts (drag or keyboard) and rebuild the map. Sets uploaded before 2b get a map via "Build Knowledge Map".
- **Generated flashcards (2b):** on request, for the whole set or one concept, as Q/A or cloze cards. They land in a "Suggested" tray where you accept or reject them; regenerating warns before replacing unedited AI cards. Cloze cards render and review with the blank hidden until flipped.

### AI features (off by default)

The Knowledge Map and card generation call the Anthropic API from the **worker only**. They are off until you opt in: put `LLM_ENABLED=true` and your `ANTHROPIC_API_KEY=...` in `api/.env` (gitignored; never commit a key), then restart `make api` and `make worker`. With `LLM_ENABLED=false` (the default) the rest of the app works and map builds fail with "AI features are turned off on this server." See `api/.env.example` for the model, timeout and per-user limit settings.

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

CI (`.github/workflows/ci.yml`) runs the same checks plus secret scanning. It was green on Phases 1 and 2a; for Phase 2b see the PR. Tests never call the network (a socket guard blocks it); the one live Claude test is opt-in (`RUN_LIVE_LLM=1` plus a key in the environment).

`make db-reset` stops Postgres and **deletes the local database volume (all local DB data is lost)**, then recreates it. Use it only if the DB was created with different credentials or you want a clean slate.

Other targets: `make test`, `make lint`, `make gen-types`, `make db-down`, `make db-psql`.

## Where decisions live

Architecture decisions are recorded as ADRs in [`docs/adr/`](docs/adr/README.md). The roadmap and open decisions are in [`docs/planning-handoff.md`](docs/planning-handoff.md); the Phase 1, 2a and 2b plans are [`docs/implementation-plan.md`](docs/implementation-plan.md), [`docs/implementation-plan-phase-2a.md`](docs/implementation-plan-phase-2a.md) and [`docs/implementation-plan-phase-2b.md`](docs/implementation-plan-phase-2b.md). Project state is in [`memory.md`](memory.md) and contributor/agent guidance in [`CLAUDE.md`](CLAUDE.md).

The Jan-2025 prototype is in git history at `5aba556`.

## License

MIT, see [`LICENSE`](LICENSE).
