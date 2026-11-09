# Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dormant prototype with an approved, tested, secure skeleton (FastAPI API + Vite React web + Postgres in Docker + CI) that the Phase 2 MVP is built on, without adding any product features.

**Architecture:** One repo with `api/` (FastAPI, SQLAlchemy 2 async, Alembic), `web/` (Vite + React + TS SPA calling the API through one generated, typed client), and `infra/` (Postgres 18 in Docker Compose with least-privilege `feynman_migrator` / `feynman_app` roles). A root `Makefile` provides one-command entry points. GitHub Actions runs the same checks as `make check`, plus gitleaks.

**Tech Stack:** Python 3.13, uv, FastAPI, pydantic-settings, SQLAlchemy 2 (asyncpg), Alembic, pytest, ruff, mypy · Node 26 LTS, npm, Vite, React, React Router, TypeScript (strict), openapi-typescript + openapi-fetch, Vitest + React Testing Library, ESLint + Prettier · Postgres 18 · GitHub Actions · pre-commit + gitleaks v8.30.1.

**Spec:** `docs/superpowers/specs/2026-11-08-phase-1-foundation-design.md` (approved 2026-11-09). Decisions: `docs/adr/0001`–`0011`. Machine setup: `docs/setup-prerequisites.md`. **Read all three before Task 0.**

## Global Constraints

- **Repo path:** `~/code/feynman-flashcard` (Linux filesystem). Never work in `/mnt/c/...`.
- **Versions:** Python `>=3.13,<3.14` · Node 26 (`web/.nvmrc` = `26`; `engines.node` = `>=26 <27`) · `postgres:18` · gitleaks `8.30.1`. Other libraries: the latest stable at install time, pinned by `uv.lock` / `package-lock.json` (both committed).
- **Git (ADR 0011):** branch `phase-1-foundation` only. Every commit is `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com commit ...`. One commit per task (plus fix-up commits after review). Push the branch after each task. **Never** push to or merge into `main`, force-push, rewrite pushed commits, create tags, or change global git config. The draft PR is opened in Task 9. **The owner merges.**
- **No `sudo`.** If a prerequisite is missing, stop and tell the owner which step of `docs/setup-prerequisites.md` to run.
- **Secrets:** no `.env` file or real credential is ever staged, committed, or pushed. Only `*.env.example` files with placeholders are committed. Run `gitleaks git --redact -v .` before every push; a finding blocks the push.
- **DB access:** the API connects **only** as `feynman_app`. Alembic connects **only** as `feynman_migrator`. The `postgres` superuser is used only by `infra/postgres/init/01-roles.sh`.
- **Dev URLs use `localhost`, never `127.0.0.1`,** in browser-facing config (API base URL, CORS origins). Cross-port cookies only work same-site in Phase 2 if both sides use `localhost`. Ports: API `8000`, web `5173`, DB `127.0.0.1:5432`.
- **Forbidden prototype patterns:** `create_all()`, `print()` for logging, HTTP 200 on failures, hard-coded URLs or credentials, SQLite in tests, `SQLALCHEMY_ECHO` on by default.
- **Out of scope (spec §3):** auth endpoints, sessions table, any product tables, real LLM SDKs, torch or sentence-transformers, the job queue, UI styling libraries, deployment, Redis.
- **Unplanned architectural choice** (a new dependency not named here, a structural change, anything touching security posture): **stop and ask the owner.** Don't edit ADRs.
- **Commit messages:** Conventional Commits (`feat:`, `chore:`, `test:`, `ci:`, `docs:`). Every message ends with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (adjust to the model actually running).

## Review Focus

1. **Stale DB volume.** The Postgres init script only runs on the *first* volume creation. If the volume predates `infra/.env` (or the passwords changed), the roles are missing or wrong. Expected: `make db` detects that the app role can't log in and prints a message naming `make db-reset` (which deletes local data). Pinned in Task 2.
2. **API started while the DB is down.** Expected: the API still starts, and `/health` returns `503 {"status":"degraded","db":"error"}` within about 2 s with no connection details in the body. It must not crash or hang. Pinned in Task 5.
3. **Browser CORS with credentials.** Expected: requests from `http://localhost:5173` get an exact `Access-Control-Allow-Origin` (not `*`) and `Access-Control-Allow-Credentials: true`. Other origins get no allow-origin header. Pinned in Task 3.
4. **Unhandled exception text leaking to clients.** Expected: a 500 returns the generic error shape, and the exception message appears only in server logs. Pinned in Task 3.
5. **`VITE_API_BASE_URL` missing or empty.** Expected: a clear error naming the variable, instead of silently calling relative URLs against the Vite dev server. Pinned in Task 7.

---

## File Structure (end state)

```
.gitignore  .gitattributes  .gitleaks.toml  .pre-commit-config.yaml  Makefile
README.md  CLAUDE.md  memory.md  LICENSE  docs/  handoff-prompts/  .claude/
.github/workflows/ci.yml
scripts/dev-env.sh                 generates the gitignored .env files with random dev passwords
infra/docker-compose.yml           service `db`
infra/.env.example
infra/postgres/init/01-roles.sh    roles + databases; also runnable standalone (CI)
api/pyproject.toml  api/uv.lock  api/.env.example  api/alembic.ini
api/alembic/env.py  api/alembic/script.py.mako  api/alembic/versions/0001_users.py
api/src/feynman_api/__init__.py
api/src/feynman_api/config.py      Settings, MigrationSettings
api/src/feynman_api/main.py        create_app(settings) factory, lifespan, CORS, logging
api/src/feynman_api/errors.py      ErrorResponse model + exception handlers
api/src/feynman_api/db.py          engine/session factories + FastAPI dependencies
api/src/feynman_api/models/__init__.py  models/base.py  models/user.py
api/src/feynman_api/routes/__init__.py  routes/health.py
api/src/feynman_api/llm/__init__.py  llm/base.py  llm/errors.py  llm/fake.py
api/src/feynman_api/openapi_dump.py  `python -m feynman_api.openapi_dump` prints the OpenAPI JSON
api/tests/conftest.py  test_config.py  test_errors.py  test_cors.py  test_migrations.py
api/tests/test_db_roles.py  test_health.py  llm/test_contract.py
web/package.json  web/package-lock.json  web/.nvmrc  web/.env.example  web/index.html
web/vite.config.ts  web/tsconfig*.json  web/eslint.config.js  web/.prettierrc
web/src/main.tsx  web/src/App.tsx  web/src/pages/StatusPage.tsx  web/src/pages/NotFoundPage.tsx
web/src/api/client.ts  web/src/api/schema.gen.ts (generated, committed)
web/src/assets/images/*.png        moved from the prototype
web/src/**/*.test.ts(x)  web/src/test/setup.ts
```

---

### Task 0: Preflight, branch, and commit the planning docs

**Files:** none created. Commits the planning session's uncommitted work:
- untracked: `docs/adr/`, `docs/superpowers/`, `docs/implementation-plan.md`, `docs/setup-prerequisites.md`, `handoff-prompts/orchestrator/orchestrator-handoff-2.md`, `handoff-prompts/implementer/phase-plan/implementer-phase-1.md`
- modified: `memory.md`, `CLAUDE.md`, `docs/planning-handoff.md`

- [ ] **Step 1:** `cd ~/code/feynman-flashcard`. Run the verification block from `docs/setup-prerequisites.md` §7. Expected: `ALL PREREQUISITES OK`. On any failure, **stop** and report the missing item and the setup step that fixes it.
- [ ] **Step 2:** `git status` shows branch `main`, up to date with `origin/main`, and **exactly** the paths listed above as untracked or modified. Anything else (in particular any `mode change` or any `.env` file) → stop and ask.
- [ ] **Step 3:** `git switch -c phase-1-foundation`
- [ ] **Step 4:** Commit the docs: `git add docs/ handoff-prompts/ memory.md CLAUDE.md && git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com commit -m "docs: add Phase 1 ADRs, design spec, implementation plan, setup guide, session 2 handoff"`
- [ ] **Step 5:** `gitleaks git --redact -v .` → `no leaks found`. Then `git push -u origin phase-1-foundation`.

---

### Task 1: Repo hygiene and secret-leak guardrails

**Files:**
- Delete: `backend/`, `frontend/` (after moving the images), `requirements.txt`, every `.DS_Store`
- Move: `frontend/src/assets/images/*.png` → `web/src/assets/images/`
- Create: `.gitignore`, `.gitattributes`, `.gitleaks.toml`, `.pre-commit-config.yaml`

**Interfaces:** Produces the ignore rules every later task relies on: `.env` and `.env.*` are ignored everywhere except `*.env.example`.

- [ ] **Step 1: Write the guard check.** These must hold after the step 3 files exist:
```bash
for p in .env api/.env infra/.env web/.env web/.env.local api/.env.test x.pem x.key; do git check-ignore -q "$p" || echo "NOT IGNORED: $p"; done
for p in api/.env.example infra/.env.example web/.env.example; do git check-ignore -q "$p" && echo "WRONGLY IGNORED: $p"; done
```
- [ ] **Step 2:** Run it now. Expected: it prints `NOT IGNORED` lines, because no root `.gitignore` exists yet.
- [ ] **Step 3:** Create the files.
  - `.gitignore`:
    - `.env`, `.env.*`, `!*.env.example`, `!.env.example`, `*.pem`, `*.key`
    - Python: `__pycache__/`, `.venv/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `*.egg-info/`
    - Node: `node_modules/`, `web/dist/`, `coverage/`
    - Generated: `web/openapi.json`
    - OS and editor: `.DS_Store`, `Thumbs.db`, `.idea/`, `.vscode/*` with `!.vscode/extensions.json`
  - `.gitattributes`: `* text=auto eol=lf`, plus `*.sh text eol=lf` and `*.png binary`.
  - `.pre-commit-config.yaml` (with top-level `exclude: ^web/src/api/schema\.gen\.ts$`, so fixers never touch the generated file and break the drift check):
    - from `pre-commit/pre-commit-hooks`: `check-added-large-files`, `check-merge-conflict`, `end-of-file-fixer`, `trailing-whitespace`, `detect-private-key`, `check-yaml`
    - from `astral-sh/ruff-pre-commit`: `ruff-check` (with `--fix`) and `ruff-format`, both limited to `^api/`
    - from `gitleaks/gitleaks` rev `v8.30.1`: hook id `gitleaks-system` (uses the binary on PATH)
  - `.gitleaks.toml`: `[extend] useDefault = true`, plus an allowlist for the paths `\.env\.example$` and the CI workflow's throwaway `ci-*` passwords (regex `ci-(postgres|migrator|app)`).
- [ ] **Step 4:** Move the images, then `git rm -r backend frontend requirements.txt` and `git rm` every tracked `.DS_Store`. `git ls-files | grep -E 'DS_Store|__pycache__|flask_session|requirements.txt|^backend/|^frontend/'` → no output. `ls web/src/assets/images` → the 7 PNGs.
- [ ] **Step 5:** Run the step 1 check. Expected: no output.
- [ ] **Step 6: Canary test that gitleaks blocks a secret.** Write a file containing `aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"` and the token `ghp_` followed by 36 alphanumeric chars. `git add` it, run `pre-commit run gitleaks-system`, and expect **Failed**. Then `git rm --cached` the file and delete it. It must never be committed.
- [ ] **Step 7:** `pre-commit install && pre-commit run --all-files`. Expected: all hooks pass (let the fixers reformat, then re-run).
- [ ] **Step 8:** Commit `chore: remove prototype code, add gitignore, gitattributes, pre-commit and gitleaks`. Run gitleaks, then push.

---

### Task 2: Postgres in Docker with least-privilege roles

**Files:**
- Create: `infra/docker-compose.yml`, `infra/.env.example`, `infra/postgres/init/01-roles.sh`, `scripts/dev-env.sh`, `Makefile` (the db and env targets only; extended later)

**Interfaces:**
- Produces:
  - roles `feynman_migrator` and `feynman_app`, and databases `feynman` and `feynman_test`, both owned by `feynman_migrator`
  - env keys: infra `POSTGRES_PASSWORD`, `MIGRATOR_PASSWORD`, `APP_PASSWORD`; api `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `TEST_DATABASE_URL`, `TEST_MIGRATION_DATABASE_URL`, `CORS_ORIGINS`, `LOG_LEVEL`; web `VITE_API_BASE_URL`
  - make targets `env`, `db`, `db-down`, `db-reset`, `db-psql`
- URL formats: `postgresql+asyncpg://feynman_app:<APP_PASSWORD>@127.0.0.1:5432/feynman` and `postgresql+asyncpg://feynman_migrator:<MIGRATOR_PASSWORD>@127.0.0.1:5432/feynman`, with the `_test` variants pointing at db `feynman_test`. The DB URLs use `127.0.0.1` because they're server-side, not browser-facing.

- [ ] **Step 1: `infra/docker-compose.yml`:**
  - service `db`, image `postgres:18`, port `127.0.0.1:5432:5432`
  - env `POSTGRES_PASSWORD`, `MIGRATOR_PASSWORD`, `APP_PASSWORD` interpolated from `infra/.env`
  - mount `./postgres/init` at `/docker-entrypoint-initdb.d:ro`
  - named volume `feynman_pgdata` mounted at `/var/lib/postgresql`, **not** `/var/lib/postgresql/data` (the 18 image keeps `PGDATA` at `/var/lib/postgresql/18/docker`, under that mount)
  - healthcheck `pg_isready -U postgres`
- [ ] **Step 2: `01-roles.sh`.** Bash with `set -euo pipefail`; fail fast via `: "${MIGRATOR_PASSWORD:?}" "${APP_PASSWORD:?}"`. Connect with `psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}"`, which honours `PGHOST`/`PGPASSWORD` so CI can run it standalone. Pass passwords as psql variables (`-v app_pw="$APP_PASSWORD"`, used as `:'app_pw'`), never by string-splicing into SQL. SQL to run:
```sql
CREATE ROLE feynman_migrator LOGIN PASSWORD :'mig_pw';
CREATE ROLE feynman_app LOGIN PASSWORD :'app_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE DATABASE feynman OWNER feynman_migrator;
CREATE DATABASE feynman_test OWNER feynman_migrator;
-- then, connected to EACH of feynman and feynman_test:
REVOKE ALL ON DATABASE <db> FROM PUBLIC;
GRANT CONNECT ON DATABASE <db> TO feynman_app;
ALTER SCHEMA public OWNER TO feynman_migrator;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO feynman_app;
ALTER DEFAULT PRIVILEGES FOR ROLE feynman_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO feynman_app;
ALTER DEFAULT PRIVILEGES FOR ROLE feynman_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO feynman_app;
```
- [ ] **Step 3: `scripts/dev-env.sh` (`make env`).**
  - Creates whichever of `infra/.env`, `api/.env`, `web/.env` is missing, and **never overwrites** an existing file.
  - New passwords: `python3 -c 'import secrets; print(secrets.token_urlsafe(24))'`.
  - If `infra/.env` already exists, `api/.env` is derived from *its* passwords.
  - Values: `CORS_ORIGINS=["http://localhost:5173"]`, `LOG_LEVEL=INFO`, `VITE_API_BASE_URL=http://localhost:8000`.
  - Commit `.env.example` files with the same keys and `change-me` placeholders.
- [ ] **Step 4: Makefile targets.**
  - `env` runs the script.
  - `db` runs `docker compose -f infra/docker-compose.yml up -d --wait`, then an app-role login probe: `docker compose ... exec -T -e PGPASSWORD="$APP_PASSWORD" db psql -h 127.0.0.1 -U feynman_app -d feynman -c 'select 1'`, with `APP_PASSWORD` read from `infra/.env`. If the probe fails it prints exactly: `DB volume was initialised with different credentials or before infra/.env existed. Run 'make db-reset' (DELETES all local DB data).` and exits 1.
  - `db-down` runs `compose down`.
  - `db-reset` runs `compose down -v` then `make db`.
  - `db-psql` opens psql as the migrator.
- [ ] **Step 5: Verify roles by hand** (the automated tests come in Task 4). `make env && make db`, and expect success. As `feynman_app` on `feynman`: `CREATE TABLE t(x int);` → `ERROR: permission denied for schema public`. As `feynman_migrator` on `feynman_test`: `CREATE TABLE t(x int); DROP TABLE t;` → succeeds.
- [ ] **Step 6: Verify the stale-volume message (Review Focus 1).** `make db-down`, then change `APP_PASSWORD` in `infra/.env`, then `make db`. Expected: the exact message above, exit 1. Restore the password and run `make db` → OK.
- [ ] **Step 7:** `git status` must not list any `.env` file. Commit `feat(infra): postgres 18 compose with least-privilege roles and dev env generator`. Run gitleaks, then push.

---

### Task 3: API skeleton: settings, app factory, errors, CORS

**Files:**
- Create: `api/pyproject.toml`, `api/.env.example`, `api/src/feynman_api/{__init__,config,main,errors,openapi_dump}.py`, `api/src/feynman_api/routes/__init__.py`, `api/tests/{conftest,test_config,test_errors,test_cors}.py`

**Interfaces:**
- Produces:
  - `class Settings(BaseSettings)` with fields: `database_url: SecretStr` (required), `cors_origins: list[str] = ["http://localhost:5173"]`, `log_level: Literal["DEBUG","INFO","WARNING","ERROR"] = "INFO"`, `environment: Literal["dev","test","prod"] = "dev"`, `health_db_timeout_seconds: float = 2.0`. It reads env and `api/.env` (`env_file=".env"`, `extra="ignore"`).
  - `class MigrationSettings(BaseSettings)` with field `migration_database_url: SecretStr` (required).
  - `def create_app(settings: Settings | None = None) -> FastAPI`. With no argument it constructs `Settings()`. Launched as `uvicorn --factory feynman_api.main:create_app`. Nothing connects to the DB at import or startup.
  - `errors.py`: `class ErrorBody(BaseModel): code: str; message: str; details: list[dict[str, Any]] | None = None` and `class ErrorResponse(BaseModel): error: ErrorBody`, plus `def register_error_handlers(app: FastAPI) -> None`. Code mapping: 404 → `not_found`, 405 → `method_not_allowed`, 422 → `validation_error` (with `details` carrying `loc`/`msg` per error), any other `HTTPException` → `http_error`, unhandled → 500 `internal_error` with message exactly `Internal server error`. The unhandled exception is logged with its traceback.
  - `openapi_dump.py`: `python -m feynman_api.openapi_dump` prints `create_app(Settings(database_url="postgresql+asyncpg://x:x@127.0.0.1:1/x")).openapi()` as JSON (sorted keys, 2-space indent) to stdout.
- pyproject:
  - `name = "feynman-api"`, `version = "0.1.0"`, `requires-python = ">=3.13,<3.14"`, src layout
  - runtime deps: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
  - dev group: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`
  - ruff `line-length = 100`, `target-version = "py313"`, `select = ["E","F","W","I","B","UP","S","ASYNC","RUF"]`, per-file ignore `S101` in `tests/`
  - mypy `strict = true` with the `pydantic.mypy` plugin
  - pytest `asyncio_mode = "auto"`, `testpaths = ["tests"]`
  - Logging: stdlib `logging.basicConfig` at `settings.log_level`, configured once in `create_app`.

- [ ] **Step 1: Write the failing tests.**
```python
# test_config.py
def test_missing_database_url_fails(monkeypatch): # delenv DATABASE_URL; Settings(_env_file=None) raises ValidationError mentioning "database_url"
def test_secret_not_in_repr(): s = Settings(database_url="postgresql+asyncpg://u:hunter2@h/db", _env_file=None); assert "hunter2" not in repr(s) and "hunter2" not in str(s.model_dump())
# test_errors.py  (client = httpx.AsyncClient(transport=ASGITransport(app=create_app(test_settings))))
async def test_unknown_route_404_shape(): r = GET /nope → 404, r.json() == {"error": {"code": "not_found", "message": ANY, "details": None}}
async def test_unhandled_500_hides_detail(caplog): app gets a test-only route raising RuntimeError("secret-detail-xyz"); use ASGITransport(raise_app_exceptions=False); r.status_code == 500; r.json()["error"] == {"code": "internal_error", "message": "Internal server error", "details": None}; "secret-detail-xyz" not in r.text; "secret-detail-xyz" in caplog.text
async def test_validation_422_shape(): a test-only route with an int query param, called with ?n=abc → 422, error.code == "validation_error", error.details is a non-empty list
# test_cors.py
async def test_cors_allows_web_origin(): OPTIONS /health with Origin http://localhost:5173 + Access-Control-Request-Method GET → headers["access-control-allow-origin"] == "http://localhost:5173", headers["access-control-allow-credentials"] == "true"
async def test_cors_rejects_other_origin(): same with Origin http://evil.example → "access-control-allow-origin" not in headers
```
`conftest.py` provides `test_settings` (built from `TEST_DATABASE_URL`, `environment="test"`) and an `api_client` fixture. If `/health` doesn't exist yet, the CORS preflight tests still exercise the middleware; they must pass both before and after Task 5.
- [ ] **Step 2:** `cd api && uv sync && uv run pytest -q` → FAIL (import errors).
- [ ] **Step 3:** Implement `config.py`, `errors.py`, `main.py`, and `openapi_dump.py` per the Interfaces block.
- [ ] **Step 4:** `uv run pytest -q` → all pass. `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests` → clean. `uv run python -m feynman_api.openapi_dump | head -c 50` → starts with `{`.
- [ ] **Step 5:** Commit `feat(api): settings, app factory, JSON error handlers, CORS`. Run gitleaks, then push.

---

### Task 4: Database layer, Alembic, first migration, role tests

**Files:**
- Create: `api/src/feynman_api/db.py`, `api/src/feynman_api/models/{__init__,base,user}.py`, `api/alembic.ini`, `api/alembic/{env.py,script.py.mako}`, `api/alembic/versions/0001_users.py`, `api/tests/{test_migrations,test_db_roles}.py`
- Modify: `api/tests/conftest.py`, `api/src/feynman_api/main.py` (the lifespan creates and disposes the engine)

**Interfaces:**
- Consumes: `Settings`, `MigrationSettings` (Task 3), and the roles and URLs from Task 2.
- Produces:
  - `def create_engine(settings: Settings) -> AsyncEngine` (`pool_pre_ping=True`, `echo=False`)
  - `def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]`
  - FastAPI dependencies: `async def get_engine(request: Request) -> AsyncEngine`, which reads `request.app.state.engine`, and `async def get_session(request: Request) -> AsyncIterator[AsyncSession]`
  - In `create_app`, the lifespan sets `app.state.engine` and `app.state.sessionmaker`, and calls `await engine.dispose()` on shutdown.
  - `models/base.py`: `class Base(DeclarativeBase)` with `metadata = MetaData(naming_convention={"ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"})`
  - `models/user.py`: `User` and `AuthIdentity`, with the exact columns from spec §7.2:
    - `User.id` / `AuthIdentity.id`: `Uuid`, primary key, default `uuid.uuid4`
    - timestamps: `DateTime(timezone=True)`, `server_default=func.now()`
    - `User.updated_at` also has `onupdate=func.now()`
    - unique functional index `uq_users_email_lower` on `lower(email)`
    - `AuthIdentity.user_id`: FK `ondelete="CASCADE"`
    - `UniqueConstraint("provider", "provider_subject")`
    - a `relationship` from `User.identities` with `cascade="all, delete-orphan"`, `passive_deletes=True`
- Alembic:
  - `env.py` uses the **async** template and takes its URL **only** from `MigrationSettings().migration_database_url`. Tests point it at `feynman_test` by setting `MIGRATION_DATABASE_URL` from `TEST_MIGRATION_DATABASE_URL` before calling `alembic.command.upgrade`.
  - `target_metadata = Base.metadata`.
  - Revision `0001_users` is hand-checked after autogenerate, and its `downgrade()` drops both tables.
- conftest:
  - A session-scoped fixture runs `alembic upgrade head` on `feynman_test` as the migrator.
  - The per-test `db_session` fixture connects as `feynman_app` (`TEST_DATABASE_URL`) inside a transaction that's rolled back at teardown.
  - The DB tests require `make db`. If the DB is unreachable they **fail** with a message telling you to run `make db`. They never skip silently.

- [ ] **Step 1: Write the failing tests.**
```python
# test_migrations.py (as migrator on feynman_test)
def test_upgrade_downgrade_upgrade(): upgrade head → tables {"users","auth_identities"} exist; downgrade base → neither exists; upgrade head → both exist again (leave at head)
def test_no_model_drift(): alembic autogenerate compare (compare_metadata) against head yields []
# test_db_roles.py (as feynman_app)
async def test_app_can_insert_and_select_user(db_session)
async def test_app_cannot_create_table(): new app-role connection; "CREATE TABLE x(i int)" raises sqlalchemy.exc.ProgrammingError whose orig is asyncpg InsufficientPrivilegeError
async def test_app_cannot_alter_or_drop_users(): "ALTER TABLE users ADD COLUMN z int" and "DROP TABLE users" both raise ProgrammingError (insufficient privilege / must be owner)
async def test_app_cannot_create_schema(): "CREATE SCHEMA s" raises ProgrammingError
async def test_email_unique_case_insensitive(db_session): insert "A@x.com" then "a@X.com" → IntegrityError
async def test_password_hash_nullable(db_session): insert User(email=..., password_hash=None) succeeds
async def test_identity_unique_provider_subject(db_session): two AuthIdentity("google","123") → IntegrityError
async def test_identity_cascade_on_user_delete(db_session): delete user via SQL "DELETE FROM users WHERE id=:id" → its identities are gone
```
- [ ] **Step 2:** `make db && cd api && uv run pytest tests/test_migrations.py tests/test_db_roles.py -q` → FAIL.
- [ ] **Step 3:** Implement the models, `db.py`, Alembic, and the migration. Wire the lifespan into `create_app`.
- [ ] **Step 4:** Full `uv run pytest -q` → pass. Ruff and mypy → clean. `MIGRATION_DATABASE_URL=... uv run alembic upgrade head` on the dev DB `feynman` → OK.
- [ ] **Step 5:** Add the Makefile target `migrate` (alembic upgrade head on the dev DB, from `api/.env`). Commit `feat(api): async db layer, alembic, users and auth_identities migration, role tests`. Run gitleaks, then push.

---

### Task 5: `GET /health`

**Files:**
- Create: `api/src/feynman_api/routes/health.py`, `api/tests/test_health.py`
- Modify: `api/src/feynman_api/main.py` (include the router)

**Interfaces:**
- Consumes: `get_engine` (Task 4), and `ErrorResponse` (Task 3) for the documented error responses.
- Produces: `class HealthResponse(BaseModel): status: Literal["ok","degraded"]; db: Literal["ok","error"]; version: str`. The route is `GET /health`, with `response_model=HealthResponse` and `responses={503: {"model": HealthResponse}}`. `version` comes from `importlib.metadata.version("feynman-api")`. The DB probe runs `SELECT 1`, wrapped in `asyncio.wait_for(..., settings.health_db_timeout_seconds)`. Any exception or timeout logs a warning and returns a 503 body. The web client in Task 7 depends on these exact field names.

- [ ] **Step 1: Write the failing tests.**
```python
async def test_health_ok(api_client): 200, json == {"status": "ok", "db": "ok", "version": "0.1.0"}
async def test_health_db_down_returns_503_fast(): app = create_app(test_settings.model_copy(update={"database_url": SecretStr("postgresql+asyncpg://feynman_app:pw@127.0.0.1:1/feynman")})); started within 'async with LifespanManager-or-lifespan context'; t0=monotonic(); r = GET /health; r.status_code == 503; r.json() == {"status": "degraded", "db": "error", "version": "0.1.0"}; monotonic()-t0 < 3.0; "127.0.0.1" not in r.text and "pw" not in r.text
async def test_app_starts_without_db(): constructing and starting the app (lifespan) with an unreachable DB raises nothing
```
For lifespan in tests, use `asgi-lifespan`'s `LifespanManager` (add it to the dev group; it's a test-only dependency and pre-approved) or FastAPI's `TestClient` context. Choose one and use it consistently.
- [ ] **Step 2:** `uv run pytest tests/test_health.py -q` → FAIL.
- [ ] **Step 3:** Implement `routes/health.py` and include the router.
- [ ] **Step 4:** Full suite, ruff, mypy → clean. Manual check: `make api` (`uv run uvicorn --factory feynman_api.main:create_app --reload --host 127.0.0.1 --port 8000`, run in `api/`), then `curl -s localhost:8000/health` → ok JSON. `make db-down`, then curl again → 503 degraded. Then `make db` again.
- [ ] **Step 5:** Add the Makefile target `api`. Commit `feat(api): health endpoint with bounded db probe`. Run gitleaks, then push.

---

### Task 6: LLM and embedding interfaces, fakes, contract tests

**Files:**
- Create: `api/src/feynman_api/llm/{__init__,base,errors,fake}.py`, `api/tests/llm/__init__.py`, `api/tests/llm/test_contract.py`

**Interfaces:**
- Produces: exactly the types, Protocols, and errors in spec §7.4, copied verbatim (`PromptBlock`, `ChatMessage`, `Usage`, `TextDelta`, `StreamDone`, `StructuredResult[T]`, `LLMProvider`, `Embedder`; `LLMError`, `LLMRateLimitError(retry_after: float | None)`, `LLMUnavailableError`, `LLMRefusalError`, `LLMOutputValidationError`). `llm/__init__.py` re-exports them all.
  - `class FakeLLMProvider` takes `__init__(self, *, replies: Sequence[str] = ("Fake reply.",), structured: Sequence[dict[str, Any]] = (), error: LLMError | None = None, chunk_size: int = 4)`.
    - Replies and structured payloads are consumed in order, cycling when exhausted.
    - If `error` is set, both methods raise it (`stream_chat` raises before yielding anything).
    - A structured payload that fails `schema.model_validate` raises `LLMOutputValidationError`.
    - `Usage`: `model_id` = the `model` argument; `input_tokens` = the whitespace word count of all system blocks plus messages; `output_tokens` = the reply's word count; `cached_input_tokens` = the word count of the system blocks up to and including the last `cache=True` block.
    - `stream_chat` yields the reply in `chunk_size`-character `TextDelta`s, then `StreamDone(stop_reason="end")`.
  - `class FakeEmbedder` takes `__init__(self, dimensions: int = 8)` and has `model_id = "fake-embedder-v1"`. Each vector is derived deterministically from `sha256(text)` and L2-normalized.
  - The fakes are **not** imported by any route.

- [ ] **Step 1: Write the failing contract tests.** They're parametrized over a `provider_factory` fixture (params: `[FakeLLMProvider]`) and an `embedder` fixture (params: `[FakeEmbedder]`), so Phase 2 adapters only append a param.
```python
async def test_stream_yields_deltas_then_single_done_last(provider): events = [e async for e in provider.stream_chat(model="m", system=[PromptBlock(text="sys")], messages=[ChatMessage(role="user", content="hi")], max_tokens=50)]; all TextDelta before the last; isinstance(events[-1], StreamDone); exactly one StreamDone
async def test_stream_usage_reports_model(provider): events[-1].usage.model_id == "m"; input_tokens > 0; output_tokens >= 0
async def test_structured_returns_validated_instance(): class Out(BaseModel): answer: str; FakeLLMProvider(structured=[{"answer": "42"}]).generate_structured(model="m", system=[], messages=[...], schema=Out, max_tokens=50) → result.value == Out(answer="42"); result.usage.model_id == "m"
async def test_structured_invalid_payload_raises(): structured=[{"wrong": 1}] → raises LLMOutputValidationError
@pytest.mark.parametrize("err", [LLMRateLimitError(retry_after=1.5), LLMUnavailableError("x"), LLMRefusalError("x"), LLMOutputValidationError("x")])
async def test_errors_propagate_from_both_methods(err): both methods raise exactly type(err); every error is an LLMError
async def test_cached_tokens_counted(): system=[PromptBlock(text="a b c", cache=True), PromptBlock(text="d")] → usage.cached_input_tokens == 3
async def test_embed_shape_and_determinism(embedder): v = await embedder.embed(["a", "b"]); len(v) == 2; all(len(x) == embedder.dimensions for x in v); await embedder.embed(["a"]) == [v[0]]; v[0] != v[1]
async def test_embed_empty(embedder): await embedder.embed([]) == []
```
- [ ] **Step 2:** `uv run pytest tests/llm -q` → FAIL.
- [ ] **Step 3:** Implement `base.py`, `errors.py`, and `fake.py`.
- [ ] **Step 4:** Tests and `mypy --strict` → clean (the Protocol conformance must type-check: add `_: LLMProvider = FakeLLMProvider()` and `_e: Embedder = FakeEmbedder()` assignments in the test module).
- [ ] **Step 5:** Commit `feat(api): LLM provider and embedder interfaces with fakes and contract tests`. Run gitleaks, then push.

---

### Task 7: Web skeleton, typed API client, status page

**Files:**
- Create: everything under `web/` listed in File Structure (the images are already moved).

**Interfaces:**
- Consumes: the `/health` OpenAPI schema (Task 5), via `make gen-types`. The target runs `cd api && uv run python -m feynman_api.openapi_dump > ../web/openapi.json && cd ../web && npx openapi-typescript openapi.json -o src/api/schema.gen.ts`.
- Produces:
  - `web/src/api/client.ts`:
    - `export function getApiBaseUrl(env: { VITE_API_BASE_URL?: string } = import.meta.env): string` throws `Error("VITE_API_BASE_URL is not set")` if the value is missing or blank, and strips trailing `/`.
    - `export const api = createClient<paths>({ baseUrl: getApiBaseUrl(), credentials: "include" })`.
  - Routes: `/` → `StatusPage`, `*` → `NotFoundPage`.
- Scaffold:
  - `npm create vite@latest web -- --template react-ts`, then remove the demo content.
  - Add `react-router`, `openapi-fetch`; dev: `openapi-typescript`, `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `prettier`, `eslint-config-prettier`.
  - npm scripts: `dev`, `build`, `lint`, `format`, `format:check`, `typecheck` (`tsc -b --noEmit` or the equivalent for the scaffold's tsconfig layout), `test` (`vitest run`), `gen:api`.
  - Vitest config: `environment: "jsdom"`, setup file `src/test/setup.ts` (jest-dom), `env: { VITE_API_BASE_URL: "http://api.test" }`.
  - `src/api/schema.gen.ts` is listed in `.prettierignore` and in ESLint `ignores`. Generated output is never reformatted, otherwise the drift check fails.
  - `index.html` `<title>Feynman Flashcard</title>`. `.nvmrc` = `26`. `.env.example` has `VITE_API_BASE_URL=http://localhost:8000`.
- StatusPage UI copy (exact):
  - heading `Feynman Flashcard`
  - while loading: `Checking API…`
  - on 200: `API: ok` and `Database: ok`
  - on 503 with a body: `API: ok` and `Database: error`
  - on network failure: `API unreachable`
  - It shows `version` when one is present. No styling library.
- NotFoundPage: `Page not found` and a link `Back to status` to `/`.

- [ ] **Step 1: Write the failing tests.**
```ts
// client.test.ts
getApiBaseUrl({ VITE_API_BASE_URL: "http://x/" }) === "http://x"
expect(() => getApiBaseUrl({})).toThrow(/VITE_API_BASE_URL/); expect(() => getApiBaseUrl({ VITE_API_BASE_URL: "  " })).toThrow(/VITE_API_BASE_URL/)
// StatusPage.test.tsx  (vi.stubGlobal("fetch", ...))
renders "Checking API…" then "API: ok" + "Database: ok" for 200 {"status":"ok","db":"ok","version":"0.1.0"}; fetch called with URL "http://api.test/health"
503 {"status":"degraded","db":"error","version":"0.1.0"} → "Database: error"
fetch rejects (TypeError) → "API unreachable"
// App.test.tsx
MemoryRouter at "/does-not-exist" → "Page not found"
```
- [ ] **Step 2:** `cd web && npm test` → FAIL.
- [ ] **Step 3:** Run `make gen-types`, then implement `client.ts`, `StatusPage`, `NotFoundPage`, and `App`.
- [ ] **Step 4:** `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build` → all succeed.
- [ ] **Step 5: Manual end-to-end.** `make db`, `make api`, `make web` (`cd web && npm run dev`). Fetch `http://localhost:5173` from WSL with curl to confirm Vite serves. Then **ask the owner** to open `http://localhost:5173` in their Windows browser and confirm it shows `API: ok` / `Database: ok`. Record the answer for the PR body.
- [ ] **Step 6:** Add Makefile targets `web` and `gen-types`. Commit `feat(web): vite react ts skeleton with typed api client and status page`. Run gitleaks, then push.

---

### Task 8: `make check` and GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `Makefile` (add `test`, `lint`, `check`)

**Interfaces:**
- Makefile targets:
  - `lint` = api `ruff check` + `ruff format --check` + `mypy src tests`, and web `lint` + `format:check` + `typecheck`
  - `test` = api `pytest` + web `npm test`
  - `check` = `lint`, then `test`, then web `build`, then a types drift check (`make gen-types && git diff --exit-code web/src/api/schema.gen.ts`)
- Workflow `ci.yml`:
  - `on: pull_request` and `push` to branches `main` and `phase-*`; `permissions: contents: read`; `concurrency` cancels superseded runs per ref.
  - Job **`api`**:
    - service `postgres:18`, env `POSTGRES_PASSWORD: ci-postgres`, port `5432:5432`, health-cmd `pg_isready`
    - step: run `bash infra/postgres/init/01-roles.sh` with `PGHOST=localhost PGUSER=postgres PGPASSWORD=ci-postgres MIGRATOR_PASSWORD=ci-migrator APP_PASSWORD=ci-app`
    - `astral-sh/setup-uv`, then `uv python install 3.13` and `uv sync --locked`
    - ruff check, ruff format --check, mypy
    - `alembic upgrade head && alembic downgrade base && alembic upgrade head` against `feynman`
    - pytest
    - all four DB URLs set as job env with the `ci-*` passwords and `127.0.0.1`
  - Job **`web`**: `actions/setup-node` with `node-version-file: web/.nvmrc` and npm cache; `npm ci`, lint, format:check, typecheck, test, build; then set up uv and run the types drift check (`make gen-types` + `git diff --exit-code`).
  - Job **`secrets`**: checkout with `fetch-depth: 0`; download the gitleaks `8.30.1` linux x64 release tarball; run `gitleaks git --redact -v .`.

- [ ] **Step 1:** Run `make check` locally with the DB up → passes.
- [ ] **Step 2:** Write `ci.yml`, commit `ci: github actions for api, web and secret scanning`, run gitleaks, push.
- [ ] **Step 3: Verify CI.** `gh run watch --exit-status $(gh run list --branch phase-1-foundation --limit 1 --json databaseId -q '.[0].databaseId')` → all three jobs succeed. If any fails, fix it in a follow-up commit and repeat. **Do not claim green without this command's success output.**

---

### Task 9: Docs rewrite, project record, draft PR

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/planning-handoff.md` (§1 table only), `memory.md`

- [ ] **Step 1: `README.md`.**
  - What the project is (2 lines).
  - Prerequisites: a link to `docs/setup-prerequisites.md`.
  - First-time setup: `make env`, `make db`, `make migrate`, `(cd api && uv sync)`, `(cd web && npm ci)`.
  - Daily use: `make db` / `make api` / `make web`, URLs `http://localhost:5173` and `http://localhost:8000/health`.
  - `make check`, and `make db-reset` (with a data-loss warning).
  - Where decisions live (`docs/adr/`).
- [ ] **Step 2: `CLAUDE.md`.**
  - Replace the prototype sections (status banner, tech stack, repo map, data model, HTTP API, user flow, running locally, known issues, conventions) with the new equivalents: current status (Phase 1 complete, pending merge), stack table, repo map, data model (`users`, `auth_identities`), API (`GET /health`, error shape), commands, conventions (the Global Constraints above, in short form), and a one-line pointer: "The Jan-2025 prototype is in git history at `5aba556`."
  - **Keep in substance, unchanged:** Product vision, "Notes for future sessions" (phase order, handoffs and memory.md, hook thresholds, decision process), "Direction agreed so far" (updated to say decisions now live in ADRs), and "Research status".
- [ ] **Step 3: `docs/planning-handoff.md` §1.** The orchestrator already marked the Phase 1 decisions as decided, with ADR links. Only fix anything the implementation changed (e.g. a recorded deviation). LLM provider, voice, embeddings model choice, and pricing stay open.
- [ ] **Step 4: `memory.md`.** Bump "Last updated", and add a **Session log** entry: "Implementation run: Phase 1". List what was built (per task), the test count and CI run URL, the owner's manual checks (browser result from Task 7), deviations from the plan with reasons, and anything incomplete. Update §3 Repository state (branch, pushed, draft PR URL, repo path `~/code/feynman-flashcard`). Next steps: the orchestrator reviews the PR against `docs/implementation-plan.md`, the owner merges, then Phase 2 planning.
- [ ] **Step 5:** Commit `docs: rewrite README and CLAUDE.md for new structure; record phase 1 run`. Run gitleaks, push, and wait for CI to go green again (Task 8 step 3 command).
- [ ] **Step 6: Draft PR.** `gh pr create --draft --base main --head phase-1-foundation --title "Phase 1: architecture foundation" --body-file <tmpfile>`. The body has:
  - a summary;
  - a checklist of the spec §2 exit criteria, each with evidence (command plus result, CI run link);
  - the owner's browser check result;
  - deviations from the plan;
  - "Owner merges after orchestrator review";
  - ending with the line `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

  **Do not merge or mark it ready.** Report the PR URL to the owner and stop.

---

## Phase 2 outline: NOT FOR EXECUTION

> Context for later sessions only. **Do not implement any of this in the Phase 1 run.** A separate Phase 2 plan will be written after the owner merges Phase 1 and makes the decisions listed. Milestones run in order. Each lists *decisions needed first*, then the acceptance criteria.

| # | Milestone | Decisions needed first | Acceptance (summary) |
|---|---|---|---|
| M1 | **Auth**: register/login/logout, Postgres `sessions` table, CSRF, route guards in web | Password rules + breached-password check; rate-limit approach; CSRF mechanism; **age policy / DOB (privacy, §5 #7)**; UI styling approach + component library | Cookie flags verified; session revocation works; brute-force rate-limited; every protected route 401s without a session; web redirects to login |
| M2 | **Study sets + flashcards**: CRUD, flip/review UI | Card schema (front/back + optional `concept_id` per §2.11) | Cards addressed by id; **cross-user access tests return 404** for every endpoint; proper HTTP codes |
| M3 | **PDF upload + job queue** (ADR 0008) | `procrastinate` vs hand-rolled queue; file storage (local disk in dev vs S3-compatible); upload size and page limits | Upload → job → extracted text stored; job status visible in UI; worker restart doesn't lose jobs |
| M4 | **Knowledge Map**: LLM concept extraction, editable by the student | **LLM provider + models (§5 #2)**; provider data-retention settings; first real adapter must pass the Task 6 contract tests | Concepts with importance/key terms/misconceptions/source refs; edit UI; versions stored |
| M5 | **Generated flashcards** from concepts | Card count and style per concept | Generated cards linked to concepts, editable, `origin=generated` |
| M6 | **Text Feynman session**: SSE streaming "curious novice" tutor, scoped concepts, transcript saved | Tutor prompt (doesn't teach), session length limits | Streaming works end to end; turns persisted; the tutor-leak test (tutor never states scoped content) on fixtures |
| M7 | **Scoring v1** (§0 subset of §2): baseline + single-sample judge with quote verification + asymmetric band + divergence flag | **Embedding model (local)**; τ, weights, δ, insufficient-evidence threshold (§5 #6) | Pipeline deterministic on fixtures; fabricated quotes discarded; all payloads + versions stored in `score_runs` |
| M8 | **Feedback**: strengths, gaps, misconceptions with citations | Feedback tone/format | Feedback consistent with stored scores (generated from them) |
| M9 | **Usage logging** from `Usage` on every LLM call | Retention of usage data | Tokens per user per session queryable; no call path skips logging |

**Phase 2 exit criteria (planning doc §0):** a new user completes the whole loop on a real PDF; core flows tested (auth, ownership, scoring on fixed fixtures); runs locally from the README.

**Phase 2 risks:** extraction quality poisoning scores (mitigated by the editable map); tutor leaking answers; LLM cost and latency on long sessions (prompt caching via `PromptBlock.cache`); embedding model size in the API image (torch).
