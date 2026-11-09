# Phase 1 Foundation: Design

> **Status:** Approved by the owner (2026-11-09)
> **Decided in:** orchestrator session 2. The decisions are recorded as ADRs 0001–0011 in `docs/adr/`.
> **Next:** once approved, it is turned into `docs/implementation-plan.md` (detailed Phase 1 tasks and a Phase 2 outline), which a Sonnet implementer session runs with subagent-driven development. This orchestrator session then reviews the result against the plan.

## 1. Intent and why

Replace the dormant Jan-2025 prototype (Flask + MySQL + Redis + Create React App, about 1,300 lines with known structural bugs) with a clean, approved foundation that the Phase 2 MVP can be built on: *upload material → study flashcards → teach it to the AI → score + feedback*. Phase 1 adds **no product features**. Its value is that every later feature lands on decided, tested, secure plumbing, and nothing has to be torn out later.

The owner works in a specific way: every architecture choice is explained and approved first, the work is reviewed against a written plan, and the owner merges. The design is therefore deliberately explicit, leaving the implementer nothing architectural to decide.

## 2. Goals

1. A new project skeleton in the approved layout (ADR 0003): `api/` (FastAPI), `web/` (Vite React TS), `infra/` (Compose + DB init), `docs/`, and a root `Makefile`.
2. Postgres 18 in Docker Compose, with **least-privilege roles** (ADR 0004).
3. The **first Alembic migration**: `users` + `auth_identities`.
4. `GET /health` that reports API and DB status.
5. The web app calls the API **through one configured client** with generated types, and shows the health status.
6. **LLM and embedding interfaces** with fakes and contract tests (ADR 0007). No vendor SDKs.
7. Tests, lint, format, and type checks run **locally and in GitHub Actions**, plus **secret scanning** (ADRs 0006, 0009).
8. Repo hygiene: the old code is removed, there is a root `.gitignore`, and dependencies are pinned through lockfiles.
9. `README.md` and `CLAUDE.md` are rewritten to describe the new structure.

**Exit criteria (from planning doc §0):** one command each to start the DB, the API, and the web app. Health check green. CI green on the pushed branch. ADRs approved. No prototype code or bugs carried over.

## 3. Non-goals (Phase 2 or later; do not build)

- Auth endpoints, the sessions table, CSRF, or password hashing code (Phase 2, ADR 0005).
- Study sets, flashcards, PDFs, the Knowledge Map, the tutor, scoring, or usage-logging tables.
- A real LLM provider adapter or vendor SDK. Torch or sentence-transformers.
- The job queue or worker (ADR 0008, built in the Phase 2 PDF milestone).
- A UI styling system or component library, porting the landing page, or any real UI beyond a status page.
- Deployment, hosting, Redis, voice, billing.

## 4. Anti-goals (would count as failure even if "it works")

- **Any secret or `.env` file committed or pushed.**
- The API connecting to Postgres as a superuser or as the schema owner.
- The implementer making an unrecorded architectural choice. If something isn't covered here or in an ADR and it would change structure, the implementer **stops and asks the owner**.
- Hard-coded URLs or credentials anywhere in code.
- `create_all()`, `print()` debugging, failure responses with HTTP 200, or any other prototype pattern.
- Tests that hit a fake DB (SQLite) instead of real Postgres.
- Claiming CI is green without a pushed run that shows it.

## 5. Constraints

- **Environment:** Windows + WSL2, Ubuntu 24.04 (systemd on). **Docker Engine runs inside WSL** (not Docker Desktop), and the repo lives in the Linux filesystem at `~/code/feynman-flashcard` (moved off `/mnt/c` for file-watching and I/O speed). Both are owner decisions from 2026-11-09. Line endings: add a `.gitattributes` with `* text=auto eol=lf`.
- **Versions:** Python 3.13 (via uv), Node 26 LTS (via nvm, pinned in `web/.nvmrc`), Postgres 18 (`postgres:18` image). CI uses the same versions.
- **Owner's git rules (ADR 0011):** branch `phase-1-foundation` from `main`; one commit per plan task, made with `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com`; push only that branch, after gitleaks passes; open a draft PR at the end; never push to or merge into `main`, never force-push, no tags. The owner merges.
- **Planning docs reach the branch with the first commit** *(orchestrator's call)*: `docs/adr/`, this spec, and `docs/implementation-plan.md` are left uncommitted on `main` by the planning session. The implementer's **first task** creates `phase-1-foundation` and commits them there, so `main` stays untouched and the draft PR contains the decisions alongside the code.
- **Machine prerequisites:** everything in `docs/setup-prerequisites.md` must be done before the run. The implementer's first task runs that doc's verification block and **stops** with a clear message if any check fails. It never runs `sudo`. GitHub push protection is **not** required (deferred by the owner, ADR 0006). The repo is public.

## 6. Approaches considered (summary; full reasoning in the ADRs)

| Decision | Chosen | Rejected and why |
|---|---|---|
| Backend (0001) | FastAPI, Python 3.13 | Full-stack TS: hosted-only embeddings weaken the objective baseline; weaker PDF tooling |
| Frontend (0002) | Vite + React + TS SPA | Next.js: a second server for SSR the app doesn't need |
| Layout (0003) | `api/ web/ infra/ docs/` | `apps/*` nesting (no payoff yet); two repos (sync and CI overhead) |
| DB (0004) | SQLAlchemy 2 async + Alembic, migrator/app roles | SQLModel (lags); raw SQL (no safety net) |
| Auth (0005) | Own Postgres sessions; password in MVP, Google next | JWT (revocation, XSS); managed (lock-in) |
| Config (0006) | pydantic-settings, `.env.example`, 3-layer leak defence | none viable |
| LLM layer (0007) | Own thin Protocol + fakes | LiteLLM (heavy, hides caching); agent frameworks (overkill) |
| Jobs (0008) | Postgres queue + worker, built in Phase 2 | Redis queues (adds Redis back); in-process (no durability) |
| Tooling (0009) | uv/ruff/mypy/pytest; npm/ESLint/Prettier/Vitest; GH Actions | Biome (smaller ecosystem) |
| Old code (0010) | Clean restart, keep images | Porting the UI now (bugs, off critical path) |
| Git (0011) | Pushed phase branch, draft PR, owner merges | Local-only (CI can't be proven) |

**Sign-in method comparison** (the basis for ADR 0005):

| Method | Simplicity for students | Security | Cost to us |
|---|---|---|---|
| Continue with Google | Best: one click | Very high; no password stored | OAuth app setup; some school accounts block it; needs a fallback |
| Email + password | Familiar | Good if done right | Nothing external; testable offline |
| Magic link | Easy, but needs the inbox each time | High | Needs an email service from day one |
| Passkeys | Easy once set up; unfamiliar | Highest | Most complex |

## 7. The design as decided

### 7.1 Target tree after Phase 1
```
.gitignore  .gitattributes  .pre-commit-config.yaml  Makefile  README.md  CLAUDE.md  memory.md  LICENSE
.github/workflows/ci.yml
api/
  pyproject.toml  uv.lock  .env.example  alembic.ini
  alembic/           env.py (uses MIGRATION_DATABASE_URL), versions/0001_users.py
  src/feynman_api/
    main.py          create_app() factory; CORS from settings; JSON error handlers
    config.py        Settings (pydantic-settings)
    db.py            async engine/sessionmaker from DATABASE_URL; get_db dependency
    models/          base.py (DeclarativeBase, naming convention), user.py
    routes/health.py
    llm/             base.py (Protocols + Usage + event types), fake.py
  tests/             conftest.py, test_health.py, test_db_roles.py, test_migrations.py, test_llm_contract.py, test_config.py
web/
  package.json  package-lock.json  vite.config.ts  tsconfig*.json  eslint.config.js  .prettierrc  .env.example  index.html
  src/
    main.tsx  App.tsx            routes: "/" status page, "*" not-found
    api/client.ts                openapi-fetch client; baseUrl = import.meta.env.VITE_API_BASE_URL; credentials: "include"
    api/schema.gen.ts            generated by openapi-typescript (committed)
    pages/StatusPage.tsx         calls GET /health; shows API/DB status, loading and error states
    assets/images/*.png          moved from the prototype
  src/**/*.test.tsx
infra/
  docker-compose.yml             postgres:18, 127.0.0.1:5432, named volume, healthcheck
  .env.example                   POSTGRES_PASSWORD, MIGRATOR_PASSWORD, APP_PASSWORD
  postgres/init/01-roles.sh      creates roles + dbs feynman and feynman_test from env vars
docs/  adr/  superpowers/specs/  implementation-plan.md  planning-handoff.md
handoff-prompts/  .claude/       (unchanged)
```
Removed: `backend/`, `frontend/`, `requirements.txt`, all `.DS_Store`.

### 7.2 Database
- `01-roles.sh` (it runs only on the first volume init) creates `feynman_migrator` (LOGIN, owns the databases `feynman` and `feynman_test` and their `public` schema) and `feynman_app` (LOGIN, `CONNECT` + schema `USAGE`, and default privileges granting `SELECT, INSERT, UPDATE, DELETE` on tables and `USAGE, SELECT` on sequences, both set for objects created by the migrator). `REVOKE ALL ON SCHEMA public FROM PUBLIC`. Passwords come from env vars and are never literal.
- Migration `0001`:
  - `users(id uuid pk, email text not null, password_hash text null, email_verified_at timestamptz null, created_at timestamptz not null default now(), updated_at timestamptz not null default now())`, with a **unique index on `lower(email)`** (no citext extension).
  - `auth_identities(id uuid pk, user_id uuid not null fk→users on delete cascade, provider text not null, provider_subject text not null, created_at timestamptz not null default now(), unique(provider, provider_subject))`.
- SQLAlchemy models mirror these. A constraint naming convention is set on the metadata so Alembic autogenerate gives stable names.
- Tests run against `feynman_test`: the session-scoped fixture runs `alembic upgrade head` as the migrator, and the tests connect as `feynman_app`.

### 7.3 API
- `create_app()` factory. Settings are injected, and nothing heavy happens at import time.
- `GET /health` → `200 {"status":"ok","db":"ok","version":"<pkg version>"}` after a `SELECT 1`. If the DB is unreachable it returns `503 {"status":"degraded","db":"error",...}` without leaking connection details.
- Errors use one JSON shape, `{"error":{"code":"...","message":"..."}}`, with correct HTTP status codes (validation 422, unknown route 404, unhandled 500 with a generic message).
- Logging uses the stdlib `logging`, configured once. No `print`. No SQL echo by default.
- CORS: allowed origins from `CORS_ORIGINS` (dev: `http://localhost:5173`), `allow_credentials=True`.

### 7.4 LLM interfaces (ADR 0007)
`llm/base.py` defines the types and Protocols below. These signatures are fixed. *(The orchestrator's call, made after the builder check and flagged for the owner.)*

```python
class PromptBlock(BaseModel):     text: str; cache: bool = False   # cache=True: adapter applies provider prompt caching up to this block; providers without explicit caching ignore it
class ChatMessage(BaseModel):     role: Literal["user", "assistant"]; content: str
class Usage(BaseModel):           model_id: str; input_tokens: int; output_tokens: int; cached_input_tokens: int = 0
class TextDelta(BaseModel):       text: str
class StreamDone(BaseModel):      usage: Usage; stop_reason: Literal["end", "max_tokens", "refusal", "other"]
class StructuredResult(BaseModel, Generic[T]): value: T; usage: Usage

class LLMProvider(Protocol):
    def stream_chat(self, *, model: str, system: Sequence[PromptBlock], messages: Sequence[ChatMessage],
                    max_tokens: int, temperature: float = 0.7) -> AsyncIterator[TextDelta | StreamDone]: ...
        # yields zero or more TextDelta, then exactly one StreamDone, last
    async def generate_structured(self, *, model: str, system: Sequence[PromptBlock], messages: Sequence[ChatMessage],
                    schema: type[T], max_tokens: int, temperature: float = 0.0) -> StructuredResult[T]: ...

class Embedder(Protocol):
    model_id: str
    dimensions: int
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...   # async; CPU-bound adapters run in a thread pool
```
- `model` is required on every call. Phase 2 config maps roles (tutor, judge, extractor) to model ids. There is no untyped per-provider options bag.
- **Errors** (in `llm/errors.py`): `LLMError` (base), `LLMRateLimitError(retry_after: float | None)`, `LLMUnavailableError` (timeouts, 5xx), `LLMRefusalError`, `LLMOutputValidationError` (structured output failed schema validation after the adapter's own retry). Adapters map vendor exceptions onto these; callers never see vendor exception types.
- The fakes can be configured to raise each error, so the contract tests cover error paths too. `llm/fake.py` provides deterministic fakes: scripted replies and a schema-valid structured result, plus fixed-dimension deterministic embeddings. The contract tests are written **against the Protocol**, so every future adapter can reuse them. The fakes are not wired into any route.

### 7.5 Web
- The status page shows a "Feynman Flashcard" title, the API/DB status, and loading and error states. That's all.
- `npm run gen:api` regenerates `schema.gen.ts` from the running API's `/openapi.json` (or from a dumped file produced by a `make` target, so CI doesn't need a live server).
- `index.html` title is "Feynman Flashcard".

### 7.6 One-command entry points (root `Makefile`)
`make db` (compose up -d + wait healthy), `make db-down`, `make migrate`, `make api` (uvicorn, reload), `make web` (vite dev), `make test`, `make lint`, `make gen-types`, `make check` (everything CI runs).

### 7.7 CI and leak defences
As in ADRs 0006 and 0009: three jobs (`api`, `web`, `secrets`). The workflow uses `permissions: contents: read`. CI DB passwords are throwaway values defined in the workflow, which is acceptable because they are CI-only and the container is ephemeral. gitleaks must be configured so it doesn't flag those or `.env.example` placeholders.

### 7.8 Docs
- `README.md`: prerequisites, first-time setup (copy the `.env.example` files, `make db`, `make migrate`), daily commands, and how to run the checks.
- `CLAUDE.md`: rewritten for the new structure. Keep the owner's rules, the phase order, the handoff procedure, and the hook notes **verbatim in substance**. Replace the prototype map, API, data model, and known-issues sections with the new ones, plus a one-line pointer to the prototype in git history.
- `docs/planning-handoff.md` §1: decisions table updated to point at the ADRs.
- `memory.md`: a Session log entry for the implementation run (what was built, test and CI status, anything incomplete).

## 8. Left to the builder (the implementer may decide these)
Exact file splits inside `api/src/feynman_api/` and `web/src/` beyond §7.1; test fixture mechanics; ESLint rule set beyond the recommended configs with TypeScript; pre-commit hook versions; Makefile internals; README wording. Anything not listed here that would change structure, dependencies, or security posture goes back to the owner.
