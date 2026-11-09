# Phase 2a Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Real accounts, a user's own study sets and flashcards, and PDF upload processed by a durable background worker into stored page text, behind a styled, auth-guarded web app. No LLM.

**Architecture:** The FastAPI app gains `auth/`, `jobs/`, `storage.py` and four routers. Every owned resource is reached through a query scoped to the current user, and anything else gets 404. Sessions, rate limits and jobs live in Postgres. A separate worker process (`python -m feynman_api.worker`) claims jobs with `FOR UPDATE SKIP LOCKED` and parses PDFs with pypdfium2. The API never parses PDFs. The SPA uses Tailwind 4 + shadcn/ui with all tokens in `web/src/index.css`, and reaches the API only through the generated openapi-fetch client. A client middleware adds the CSRF header.

**Tech Stack:** As Phase 1, plus: argon2-cffi, pypdfium2, python-multipart, httpx (runtime), email-validator · Tailwind CSS 4, @tailwindcss/vite, shadcn/ui (Radix), tw-animate-css, sonner, lucide-react, class-variance-authority, clsx, tailwind-merge.

**Spec:** `docs/superpowers/specs/2026-11-09-phase-2a-foundations-design.md` (approved 2026-11-09). It is cited below as "design §N". Decisions: `docs/adr/0012`–`0018`, building on `0001`–`0011`. **Read the design and ADRs 0013–0018 before Task 0.** Where this plan and the design disagree, stop and ask.

**Marked choices:** items tagged *(orch.)* are orchestrator's calls made while writing this plan. They are approved as part of the plan; the implementer follows them as written.

## Global Constraints

- **Everything in `docs/implementation-plan.md` Global Constraints still holds**:
  - repo path, version floors, no `sudo`, secrets rules
  - DB roles: the API and the worker connect only as `feynman_app`; Alembic only as `feynman_migrator`
  - `localhost` dev URLs
  - the forbidden prototype patterns
  - Conventional Commits with the `Co-Authored-By` trailer
- **Git (ADR 0011, 0012):**
  - Branch **`phase-2a-foundations`**, created from `main` in Task 0.
  - Every commit uses `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com commit ...`. One commit per task, plus review fix-up commits.
  - Before each push, run `make check` and then `gitleaks git --redact -v .`.
  - Never push to or merge into `main`, force-push, rewrite pushed commits, tag, or change global git config.
  - A draft PR is opened in Task 15. **The owner merges.**
- **Approved new dependencies (design §5); nothing else:**
  - API runtime: `argon2-cffi`, `pypdfium2`, `python-multipart`, `email-validator`; `httpx` moves from the dev group to runtime.
  - Web: `tailwindcss`, `@tailwindcss/vite`, `tw-animate-css`, the Radix packages the shadcn CLI installs (individual `@radix-ui/*` or the `radix-ui` umbrella), `sonner`, `lucide-react`, `class-variance-authority`, `clsx`, `tailwind-merge`, and `shadcn` (dev).
  - **Not approved:** `next-themes`, `react-hook-form`, `zod`, any font package, Playwright or any E2E tool, Redis, `aiofiles`, `freezegun`/`time-machine`.
  - If the shadcn CLI adds something outside this list, remove it. If a component can't work without it, **stop and ask**.
- **Error shape everywhere:** `{"error":{"code","message","details"}}`. New codes and their exact messages are in Task 5's Interfaces block. Messages are fixed strings and never include exception text, SQL, paths, emails or tokens.
- **Status precedence on protected routes:** 401 `not_authenticated` → 403 `csrf_failed` → 404 `not_found` → 422 `validation_error` (where FastAPI allows; body validation can run first, which is accepted). A non-UUID path id gets 422, which is accepted.
- **Transactions:** `get_session` never commits. Every route commits its own writes explicitly. The auth helpers that must persist even when the request then fails commit themselves (`rate_limit.hit`/`clear`, and `resolve_session` after a touch or lazy delete; see Task 5). Every sessionmaker (API, worker, tests) uses `expire_on_commit=False`, as `create_sessionmaker` already does.
- **Time:** session expiry and rate-limit decisions use the injected clock (`app.state.clock`, Task 5), never DB `now()` or `datetime.now()` called directly. Job claiming uses DB `now()`.
- **Types drift:** any task that changes a route or response model runs `make gen-types` and commits `web/src/api/schema.gen.ts` in the same commit.
- **Tests:**
  - Real Postgres. No network: HIBP is always a fake or an `httpx.MockTransport`.
  - Tests that commit data use the `clean_db` fixture (Task 2).
  - The web tests stub `fetch` the way Phase 1 does.
  - No test sleeps longer than 1 s.
- **UI:** screens use semantic token classes only (ADR 0014). Light mode only. UI copy is quoted in the tasks; copy not quoted is the builder's (short and plain).
- **CI:** prove CI green with `gh run watch --exit-status <id>`, and never claim green without that output. If runs fail with **zero steps executed** (for example "account is locked due to a billing issue"), it's an account problem: **stop and tell the owner**. Don't retry in a loop.
- **Known environment traps (from Phase 1):**
  - pre-commit stashes unstaged files, so **stage config changes before testing hooks**.
  - Inside the Postgres container, `127.0.0.1` is trust-auth, so password probes use `-h db`.
  - Pin any new GitHub Action by commit SHA (`gh api repos/<o>/<r>/commits/<tag> -q .sha`).
  - The owner's manual browser checks run in the **Windows** browser against `http://localhost:5173` served from WSL.
- **Out of scope (design §3):**
  - anything with an LLM or embeddings
  - email sending or verification, password reset or change, OAuth, MFA
  - OCR, multi-PDF sets, S3, deployment
  - spaced repetition, card reordering, Markdown in cards
  - landing page, branding, dark mode, E2E tooling
  - **anything 2b/2c**
- **Unplanned architectural choice** (a dependency not listed above, a structural change, anything touching security posture): **stop and ask the owner.** Don't edit ADRs or the design.

## Review Focus

Each item is pinned by a named test in the task that owns it. The reviewer checks that the test exists, asserts what is stated here, and fails when the behaviour is broken.

1. **Ownership 404 matrix covers every endpoint.** User B gets 404 `not_found` on every read, update and delete of user A's set, card and document, and the response is identical to a random UUID's. A meta-test fails if any route with a path id is missing from the matrix. Pinned in Task 7 (`test_ownership_matrix`, `test_ownership_matrix_covers_every_id_route`), extended in Task 9.
2. **Cookie flags and hashed session tokens.** The `Set-Cookie` header has `HttpOnly`, `SameSite=lax`, `Path=/`, `Max-Age=2592000`, and `Secure` exactly when `session_cookie_secure` is true. The DB holds `sha256(token)` and never the token. Pinned in Task 6 (`test_register_sets_session_cookie_flags`, `test_secure_flag_follows_setting`) and Task 5 (`test_session_token_stored_only_hashed`).
3. **CSRF and Origin enforcement on every unsafe route.** A test enumerates every POST/PUT/PATCH/DELETE route on the app. Each one returns 403 `csrf_failed` with a bad or missing `Origin`; each authenticated one also does with a missing or wrong `X-CSRF-Token`. Pinned in Task 6 (`test_every_unsafe_route_enforces_origin_and_csrf`). Task 9 re-runs it with `/documents` included.
4. **No password, birth data or tokens in logs.** A full register → login → session → logout → delete flow under `caplog` at DEBUG. None of these appear in the logs: the password, `birth_month`/`birth_year`, the cookie token, the CSRF token. Pinned in Task 6 (`test_no_secrets_in_logs`).
5. **An oversized upload leaves no temp or stored file.** Three cases, each with 413 `file_too_large`, no `documents`/`study_sets`/`jobs` row, an empty `UPLOAD_DIR`, and an empty temp dir:
   - a declared `Content-Length` over the cap
   - a chunked body over the cap
   - a body exactly 1 byte over 20 MiB inside the multipart allowance
   Pinned in Task 9 (`test_upload_too_large_*`).
6. **A worker lease is reclaimed and two claimers never get the same job.** Pinned in Task 8:
   - an expired `running` job is claimed again
   - a job claimed in an open transaction is skipped by a second claimer
   - concurrent claimers over N jobs get N distinct jobs
   - an expired job already at `max_attempts` is failed, not run
   Tests: `test_expired_lease_is_reclaimed`, `test_skip_locked_second_claimer_gets_nothing`, `test_concurrent_claimers_get_distinct_jobs`, `test_reclaimed_exhausted_job_fails`.
7. **Raw palette colours appear nowhere in screens.** A Vitest test scans `src/pages`, `src/components` (excluding `src/components/ui`), `src/auth` and `src/App.tsx`. It fails on Tailwind palette classes (`bg-indigo-600`, `text-gray-500/50`, …), hex colours, `rgb(`/`hsl(`/`oklch(` and inline `style` colours. Pinned in Task 11 (`tokens.test.ts`).
8. **Only 401 `not_authenticated` triggers logout.** Pinned in Task 11 (`client.test.ts`) and Task 12:
   - a 401 `not_authenticated` from any call except `GET /auth/session` clears auth and navigates to `/login?next=…`
   - a 401 `invalid_credentials` (wrong password on login or account deletion) shows a form error and keeps the user signed in
   - a 401 from `GET /auth/session` just means signed out, with no redirect loop on `/register`

---

## File Structure (end state; new or changed only)

```
.gitignore                                   + api/var/
Makefile                                     + worker
scripts/dev-env.sh                           warning + new api/.env keys
.github/workflows/ci.yml                     (unchanged unless a real CI failure needs a fix)
api/pyproject.toml / uv.lock / .env.example  deps + new settings
api/alembic/versions/0002_auth_sessions_rate_limits.py  0003_study_content.py  0004_jobs.py
api/src/feynman_api/
  config.py            new settings (Tasks 3–10)
  main.py              create_app(settings, *, clock, breach_checker, file_store); middleware order
  errors.py            AppError + handler; ServerErrorJSONMiddleware (CORS-safe 500s)
  clock.py             Clock type, system_clock
  storage.py           FileStore protocol, LocalFileStore, InvalidStorageKey
  upload_limit.py      BodySizeLimitMiddleware (pure ASGI)
  worker.py            `python -m feynman_api.worker` entry point
  auth/__init__.py  passwords.py  breach.py  sessions.py  rate_limit.py  csrf.py  dependencies.py  schemas.py
  models/__init__.py  user.py(+age_verified_at)  auth_session.py  rate_limit.py  study_set.py  flashcard.py  document.py  job.py
  routes/auth.py  study_sets.py  flashcards.py  documents.py  (health.py unchanged)
  jobs/__init__.py  queue.py  worker.py  registry.py  handlers/__init__.py  handlers/extract_pdf.py
api/tests/
  conftest.py          + clean_db, make_user/login helpers, fake breach checker, frozen clock, tmp file store
  test_leftovers.py  test_models.py  test_storage.py  test_passwords.py  test_breach.py
  test_sessions.py  test_rate_limit.py  test_auth_routes.py  test_csrf_matrix.py  test_auth_logs.py
  test_study_sets.py  test_flashcards.py  test_ownership.py
  test_upload.py  test_documents.py  test_queue.py  test_worker.py  test_extract_pdf.py
  fixtures/make_fixtures.py (stdlib only)  fixtures/README.md
  fixtures/text.pdf  fixtures/image_only.pdf  fixtures/too_many_pages.pdf  fixtures/corrupt.pdf
web/
  package.json / package-lock.json  components.json  vite.config.ts (+ tailwind, @ alias)  tsconfig*.json (+ paths)
  src/index.css        Tailwind import + @theme tokens (the ONLY place colours/radius/fonts are defined)
  src/lib/utils.ts     cn()
  src/components/ui/*  shadcn components
  src/components/AppShell.tsx  RequireAuth.tsx  DocumentStatus.tsx  UploadPdfButton.tsx  ConfirmDialog.tsx …
  src/auth/AuthProvider.tsx  useAuth.ts  safeNext.ts
  src/api/client.ts    + CSRF middleware, 401 handler
  src/pages/LoginPage RegisterPage SetsPage SetDetailPage ReviewPage AccountPage StatusPage NotFoundPage (+ tests)
  src/test/tokens.test.ts
README.md  CLAUDE.md  memory.md  docs/planning-handoff.md (§1/§5)
```

Task order follows the handoff, with three changes:
- **`FileStore` moves up to Task 3**, because account deletion (Task 6) removes stored files.
- **The job queue (Task 8) comes before upload (Task 9)**, because upload enqueues a job.
- **The account page joins the auth pages (Task 12)**, because it is mostly the delete-account flow.

---

### Task 0: Preflight, branch, and commit the planning docs

**Files:** none created. Commits orchestrator session 3/4's uncommitted work:
- modified: `CLAUDE.md`, `memory.md`, `docs/planning-handoff.md`, `docs/adr/README.md`
- untracked: `docs/adr/0012-mvp-scope-and-phase-2-split.md`, `docs/adr/0013-age-policy.md`, `docs/adr/0014-ui-styling.md`, `docs/adr/0015-job-queue-own-table.md`, `docs/adr/0016-file-storage.md`, `docs/adr/0017-auth-security-details.md`, `docs/adr/0018-study-content-model-and-pdf-library.md`, `docs/superpowers/specs/2026-11-09-phase-2a-foundations-design.md`, `docs/implementation-plan-phase-2a.md`, `handoff-prompts/orchestrator/orchestrator-handoff-3.md`, `handoff-prompts/implementer/phase-plan/implementer-phase-2a.md`

- [ ] **Step 1:** `cd ~/code/feynman-flashcard`. Run the verification block in `docs/setup-prerequisites.md` §7 → `ALL PREREQUISITES OK`. Otherwise **stop** and report.
- [ ] **Step 2:** `git switch main && git pull --ff-only`. `git status --porcelain` must list **exactly** the paths above:
  - ` M` for the four modified files
  - `??` for the untracked ones, where a directory may show as e.g. `?? docs/adr/0012-…`
  Anything else (in particular any `.env` or `mode change`) → stop and ask. `git log --oneline -1` → `3185eb1 Phase 1: architecture foundation (#1)` or a later commit the owner made (if later, ask before continuing).
- [ ] **Step 3:** `git switch -c phase-2a-foundations`.
- [ ] **Step 4:** `git add CLAUDE.md memory.md docs/planning-handoff.md docs/adr/ docs/superpowers/specs/2026-11-09-phase-2a-foundations-design.md docs/implementation-plan-phase-2a.md handoff-prompts/orchestrator/orchestrator-handoff-3.md handoff-prompts/implementer/phase-plan/implementer-phase-2a.md`. Then `git status --porcelain` → nothing unstaged or untracked. Commit `docs: add Phase 2 ADRs 0012-0018, 2a design, 2a plan, session 3 handoff`.
- [ ] **Step 5:** `make db && make migrate && make check` → passes. Record the actual counts (expected after the Phase 1 fix-ups: 40 pytest, 8 vitest; `CLAUDE.md`'s 36/7 is stale). `gitleaks git --redact -v .` → no leaks. `git push -u origin phase-2a-foundations`.

---

### Task 1: Phase 1 leftovers (design §7.9)

**Files:**
- Modify: `api/src/feynman_api/main.py`, `api/src/feynman_api/errors.py`, `api/tests/test_migrations.py`, `scripts/dev-env.sh`
- Create: `api/tests/test_leftovers.py`

**Interfaces:**
- Produces: `class ServerErrorJSONMiddleware` in `errors.py`, a **pure ASGI** middleware (`__init__(self, app: ASGIApp)`, `async __call__(scope, receive, send)`).
  - On an exception before the response has started, it logs exactly as `unhandled_handler` does today (method, path, traceback) and sends the standard 500 body `{"error":{"code":"internal_error","message":"Internal server error","details":null}}`.
  - If the response already started, it re-raises.
- Produces: the middleware order in `create_app`. Starlette runs the *last added* middleware outermost, so after Task 9 the order from outside in is:
  1. `CORSMiddleware`
  2. `ServerErrorJSONMiddleware`
  3. `BodySizeLimitMiddleware` (added in Task 9)
  4. the routes
  Add `ServerErrorJSONMiddleware` first, then CORS.
- CORS: `allow_headers=["Content-Type", "X-CSRF-Token"]`; `expose_headers=["Retry-After"]`.
- Logging: keep `logging.basicConfig(level=settings.log_level)` and add `logging.getLogger().setLevel(settings.log_level)`, so the configured level always applies *(orch.)*. This deviates from design §7.9's literal `force=True` but meets its intent: `force=True` removes every root handler, including pytest's `caplog` handler whenever an app is built inside a test, which would make the log tests pass vacuously.

- [ ] **Step 1: Write the failing tests** in `test_leftovers.py`:
```python
async def test_500_has_cors_headers_for_allowed_origin(app, api_client):  # route raising RuntimeError("secret-xyz")
    r = await api_client.get("/boom", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "secret-xyz" not in r.text
async def test_500_no_cors_for_other_origin(app, api_client):  # Origin http://evil.example → no access-control-allow-origin
async def test_cors_preflight_allows_csrf_header(api_client):  # OPTIONS /health, Access-Control-Request-Headers: x-csrf-token → 200, "x-csrf-token" in allow-headers (case-insensitive)
def test_log_level_applies_even_with_existing_handlers():  # add a handler to root, create_app(Settings(log_level="DEBUG", ...)) → logging.getLogger().level == logging.DEBUG, and the added handler is still attached
```
  Keep the existing `test_unhandled_500_hides_detail` green (traceback still logged).
- [ ] **Step 2:** `cd api && uv run pytest tests/test_leftovers.py -q` → the CORS-on-500 and allow-headers tests FAIL.
- [ ] **Step 3:** Implement the middleware, the CORS changes and the logging change. Remove `unhandled_handler`: `@app.exception_handler(Exception)` is served by Starlette's outermost `ServerErrorMiddleware`, so the new middleware makes it dead code. `test_errors.py` stays green.
- [ ] **Step 4: `test_migrations.py` hardening.**
  - `test_upgrade_downgrade_upgrade` wraps the downgrade in `try/finally: command.upgrade(cfg, "head")`, so the DB is always left at head.
  - The table-set assertions compare against `set(Base.metadata.tables)` instead of a literal, so later migrations need no test edit.
  - Add `test_users_email_lower_index_is_unique`: the inspector's `get_indexes("users")` contains `uq_users_email_lower` with `unique` true.
- [ ] **Step 5: `scripts/dev-env.sh`.**
  - When it **creates** `infra/.env` while `api/.env` already exists, print to stderr: `WARNING: created infra/.env but api/.env already exists; its passwords will not match. Delete api/.env and run make env again.`
  - New API keys from later tasks: when **creating** `api/.env`, write `SESSION_COOKIE_SECURE=false`. When `api/.env` **exists** but lacks a `SESSION_COOKIE_SECURE=` line, **append** that line and print `added SESSION_COOKIE_SECURE=false to api/.env`. Never change existing lines *(orch.)*.
  - Verify by hand in a scratch copy: create `api/.env` only, run the script → warning. Run it again → no duplicate line.
- [ ] **Step 6:** `make check` → passes. Commit `fix: CORS headers on 500s, CSRF header in CORS, logging force, migration test hardening, dev-env warning`. gitleaks, push.

---

### Task 2: Migrations, models, and DB test fixtures

**Files:**
- Create: `api/alembic/versions/0002_auth_sessions_rate_limits.py`, `0003_study_content.py`, `0004_jobs.py`; `api/src/feynman_api/models/{auth_session,rate_limit,study_set,flashcard,document,job}.py`; `api/tests/test_models.py`
- Modify: `models/user.py`, `models/__init__.py`, `api/tests/conftest.py`

**Interfaces:**
- Produces the tables in design §7.2, **exactly**. All ids `Uuid` with `default=uuid.uuid4`. Timestamps `DateTime(timezone=True)`, `server_default=func.now()`, and `updated_at` also `onupdate=func.now()`. FKs `ondelete="CASCADE"`.
  - `User.age_verified_at: Mapped[datetime | None]`.
  - `AuthSession` (`auth_sessions`): `id`, `user_id` FK, `token_hash: bytes` (`LargeBinary`, unique, not null), `csrf_token: str` not null, `created_at`, `last_seen_at`, `expires_at` (all not null; set from Python, see Task 5). Index on `user_id`.
  - `RateLimitBucket` (`rate_limit_buckets`): `key: str`, `window_start: datetime`, `count: int` not null; composite PK `(key, window_start)`.
  - `StudySet` (`study_sets`): `id`, `user_id` FK, `title`, `description` nullable, `created_at`, `updated_at`. CHECKs: `ck_study_sets_title_length`: `char_length(title) BETWEEN 1 AND 120`; `ck_study_sets_description_length`: `description IS NULL OR char_length(description) <= 1000`. Index `(user_id, created_at)`.
  - `Flashcard` (`flashcards`): `id`, `study_set_id` FK, `front`, `back`, `origin` (default `'manual'`, server default too), `created_at`, `updated_at`. CHECKs: `front_length` 1–500, `back_length` 1–2000, `origin IN ('manual','generated')`. Index `(study_set_id, created_at)`.
  - `Document` (`documents`): `id`, `study_set_id` FK **unique**, `storage_key` unique, `original_filename`, `size_bytes` (int), `page_count` nullable, `status` (CHECK `IN ('processing','ready','failed')`), `error_message` nullable, `created_at`, `updated_at`. CHECK `ck_documents_original_filename_length`: `char_length(original_filename) BETWEEN 1 AND 255`.
  - `DocumentPage` (`document_pages`): `document_id` FK, `page_number` int, `text` not null; PK `(document_id, page_number)`.
  - `Job` (`jobs`): `id`, `user_id` FK, `kind`, `payload` (`JSONB`, not null), `status` (CHECK `IN ('queued','running','succeeded','failed')`, default `'queued'`), `attempts` (default 0), `max_attempts` (default 3), `run_after` (server default `now()`), `locked_until` nullable, `last_error` nullable, `result` (`JSONB`) nullable, `created_at`, `updated_at`. Index `ix_jobs_status_run_after` on `(status, run_after)`.
  - Relationships where useful (`StudySet.flashcards`, `StudySet.document` as `uselist=False`), all with `passive_deletes=True`. DB cascades do the deleting.
- Migrations: `0002` adds `users.age_verified_at`, `auth_sessions`, `rate_limit_buckets`. `0003` adds study sets, cards, documents and pages. `0004` adds jobs. Each `downgrade()` reverses its own `upgrade()`. No grants needed (default privileges cover new tables). **Do not** re-grant on `alembic_version`.
- conftest additions (all later tasks use them):
  - `clean_db` (function scope, depends on `migrated_db`): at **setup and teardown**, connect as the **migrator** (`migration_url`) and `TRUNCATE users, jobs, rate_limit_buckets RESTART IDENTITY CASCADE`. This is test-only use of the migrator, because the app role has no TRUNCATE.
  - `db` (function scope, depends on `clean_db`): a plain `feynman_app` `AsyncSession` on its own engine. It is **not** rolled back; tests use it to insert setup rows and to assert committed state written by the app or the worker.
  - `app` now depends on `migrated_db`.

- [ ] **Step 1: Write the failing tests** in `test_models.py` (using `db_session`, which rolls back):
```python
async def test_all_tables_exist(app_connection)  # inspector tables ⊇ {"auth_sessions","rate_limit_buckets","study_sets","flashcards","documents","document_pages","jobs"}
@pytest.mark.parametrize("title", ["", "x" * 121])
async def test_study_set_title_check(db_session, title)  # raw INSERT with that title → IntegrityError (CheckViolation)
async def test_study_set_description_check(db_session)   # 1001 chars → IntegrityError; 1000 OK
@pytest.mark.parametrize("front,back", [("", "b"), ("x"*501, "b"), ("f", ""), ("f", "x"*2001)])
async def test_flashcard_length_checks(db_session, front, back)
async def test_flashcard_origin_check(db_session)        # origin="ai" → IntegrityError; default is "manual"
async def test_one_document_per_set(db_session)          # second document for the same set → IntegrityError
async def test_document_status_check(db_session)         # status="done" → IntegrityError
async def test_job_status_check_and_defaults(db_session) # defaults: status queued, attempts 0, max_attempts 3, run_after set
async def test_user_delete_cascades_everything(db_session)  # user with session, set, card, document, page, job, then DELETE FROM users → all child rows gone
async def test_session_token_hash_unique(db_session)
```
- [ ] **Step 2:** `uv run pytest tests/test_models.py tests/test_migrations.py -q` → FAIL.
- [ ] **Step 3:** Write the models and the three migrations (autogenerate, then hand-check names and CHECKs against the naming convention). Add `clean_db`.
- [ ] **Step 4:** The full suite passes, including `test_no_model_drift` (if autogenerate can't compare a CHECK, that's fine; drift must be `[]`). `make migrate` on the dev DB works. The round trip `alembic upgrade head && alembic downgrade base && alembic upgrade head` on `feynman` works.
- [ ] **Step 5:** Commit `feat(api): auth session, rate limit, study content and jobs tables`. gitleaks, push.

---

### Task 3: `FileStore` and the upload directory

**Files:**
- Create: `api/src/feynman_api/storage.py`, `api/tests/test_storage.py`
- Modify: `config.py`, `main.py`, `api/.env.example`, `.gitignore` (add `api/var/`)

**Interfaces:**
- `class InvalidStorageKey(ValueError)`
- `class FileStore(Protocol)`:
  - `async def put(self, key: str, chunks: AsyncIterator[bytes]) -> int`: returns bytes written; on any exception it removes the partial file and re-raises.
  - `def open(self, key: str) -> BinaryIO`: sync, for the worker; raises `FileNotFoundError`.
  - `async def delete(self, key: str) -> None`: a missing file is not an error.
- `class LocalFileStore(FileStore)`: `__init__(self, root: Path)`.
  - Key must match `^[0-9a-f]{32}$` (`uuid4().hex`), else `InvalidStorageKey`. Path is `root / key`.
  - Writes go to `root / f"{key}.part"` and are renamed on success. Blocking file I/O runs via `asyncio.to_thread` (no `aiofiles`).
- `def new_storage_key() -> str` returns `uuid.uuid4().hex`.
- `Settings.upload_dir: Path = Path("var/uploads")` (relative to the API's working directory, `api/`).
- `create_app(settings=None, *, file_store: FileStore | None = None, ...)`:
  - default `LocalFileStore(settings.upload_dir)`
  - stored on `app.state.file_store`
  - the lifespan runs `upload_dir.mkdir(parents=True, exist_ok=True)` (only for the default store)
- FastAPI dependency `def get_file_store(request: Request) -> FileStore`.
- conftest: `file_store` fixture = `LocalFileStore(tmp_path / "uploads")`, created. The `app` fixture passes it.

- [ ] **Step 1: Write the failing tests:**
```python
async def test_put_open_delete_roundtrip(tmp_path)        # put 3 chunks → returns total; open().read() equals the bytes; delete → open raises FileNotFoundError
async def test_delete_missing_is_noop(tmp_path)
@pytest.mark.parametrize("key", ["../x", "a/b", "ABC", "", "0"*31, "0"*33, "../../etc/passwd"])
async def test_rejects_non_uuid_hex_keys(tmp_path, key)   # put/open/delete each raise InvalidStorageKey; nothing created outside root
async def test_failed_put_leaves_no_file(tmp_path)        # the chunk iterator raises midway → exception propagates; root is empty (no .part)
async def test_app_creates_upload_dir(tmp_path)           # Settings(upload_dir=tmp_path/"u"), lifespan → dir exists
```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. `make check`.
- [ ] **Step 5:** Commit `feat(api): local file store behind a FileStore protocol`. gitleaks, push.

---

### Task 4: Passwords and breached-password check

**Files:**
- Create: `api/src/feynman_api/auth/{__init__,passwords,breach}.py`, `api/tests/{test_passwords,test_breach}.py`
- Modify: `api/pyproject.toml` / `uv.lock`: `uv add argon2-cffi httpx email-validator`, and remove `httpx` from the dev group (it is now runtime). `config.py`, `.env.example`.

**Interfaces:**
- `passwords.py`:
  - `PASSWORD_MIN = 12`, `PASSWORD_MAX = 128`
  - `def normalize_password(raw: str) -> str` (NFKC)
  - `async def hash_password(password: str) -> str`
  - `async def verify_password(stored_hash: str, password: str) -> bool` (returns False on mismatch or invalid hash; never raises for a wrong password)
  - `def needs_rehash(stored_hash: str) -> bool`
  - `async def verify_dummy(password: str) -> None`: verifies against a module-level hash of a constant, used when the email is unknown, so login timing doesn't reveal accounts *(orch.)*
  - One `argon2.PasswordHasher()` with library defaults. Hash and verify run in `asyncio.to_thread`. The normalised password is what gets hashed and verified.
- `breach.py`:
  - `class BreachChecker(Protocol): async def is_breached(self, password: str) -> bool`
  - `class HibpBreachChecker`: `__init__(self, client: httpx.AsyncClient, timeout: float)`.
    - Sends `GET https://api.pwnedpasswords.com/range/{SHA1[:5]}` with headers `Add-Padding: true` and `User-Agent: feynman-flashcard`.
    - Parses `SUFFIX:COUNT` lines and returns True only if the suffix matches with **COUNT > 0** (padding lines have count 0).
    - On any `httpx.HTTPError` or timeout, or a non-200, it logs `WARNING "HIBP check unavailable (%s); allowing password"` with the exception type name only, and returns False (fail-open).
  - `class StaticBreachChecker`: `__init__(self, breached: Collection[str] = ())`. For tests and when HIBP is disabled.
- Settings: `hibp_enabled: bool = True`, `hibp_timeout_seconds: float = 2.0`.
  - `create_app(..., breach_checker: BreachChecker | None = None)`: an injected checker is stored on `app.state.breach_checker` in `create_app`. Otherwise **the lifespan** builds the default and stores it there: `HibpBreachChecker(httpx.AsyncClient(), hibp_timeout_seconds)` if `hibp_enabled` (the client is closed at shutdown), else `StaticBreachChecker()`. Dependency `def get_breach_checker(request) -> BreachChecker`.
  - conftest `test_settings` sets `hibp_enabled=False`, and the `app` fixture passes `StaticBreachChecker({"breached-password-123"})`.

- [ ] **Step 1: Write the failing tests:**
```python
async def test_hash_and_verify(): h = await hash_password("correct horse battery"); assert h.startswith("$argon2id$"); assert await verify_password(h, "correct horse battery"); assert not await verify_password(h, "wrong")
async def test_nfkc_normalisation(): h = await hash_password(normalize_password("ﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁ")); assert await verify_password(h, normalize_password("fifififififififififififi"))
def test_needs_rehash_detects_old_params(): an argon2 hash made with time_cost=1 → needs_rehash True; a default hash → False
async def test_verify_invalid_hash_returns_false()
# test_breach.py: HibpBreachChecker with httpx.AsyncClient(transport=httpx.MockTransport(handler))
async def test_hibp_sends_only_prefix_and_padding(): handler records request; path == f"/range/{sha1('pw-under-test')[:5].upper()}"; "Add-Padding" header == "true"; full hash not in str(request.url)
async def test_hibp_match_with_count_is_breached()       # response contains f"{suffix}:42"
async def test_hibp_padding_line_with_zero_count_not_breached()  # f"{suffix}:0"
async def test_hibp_timeout_fails_open(caplog)           # handler raises httpx.ReadTimeout → False; "HIBP check unavailable" in caplog; password not in caplog.text
async def test_hibp_500_fails_open()
```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. `make check`.
- [ ] **Step 5:** Commit `feat(api): argon2id password hashing and HIBP range check (fail-open)`. gitleaks, push.

---

### Task 5: Sessions, rate limiter, CSRF/Origin, clock, error type

**Files:**
- Create: `api/src/feynman_api/{clock,auth/sessions,auth/rate_limit,auth/csrf,auth/dependencies}.py`, `api/tests/{test_sessions,test_rate_limit}.py`
- Modify: `errors.py`, `main.py`, `config.py`, `.env.example`

**Interfaces:**
- `clock.py`: `Clock = Callable[[], datetime]`; `def system_clock() -> datetime` (aware UTC). `create_app(..., clock: Clock | None = None)` sets `app.state.clock`. Dependency `def get_clock(request) -> Clock`.
  - conftest: a `FrozenClock` class (`now`, `advance(**timedelta_kwargs)`, `__call__`) and a `clock` fixture, passed to the `app` fixture.
- `errors.py`:
  - `class AppError(Exception)`: `__init__(self, status: int, code: str, message: str, *, headers: Mapping[str, str] | None = None)`
  - a handler producing the standard shape
  - Fixed codes and messages, used verbatim by every later task (the copy is the orchestrator's call):

| Status | code | message |
|---|---|---|
| 401 | `not_authenticated` | `Not signed in.` |
| 401 | `invalid_credentials` | `Invalid email or password.` |
| 403 | `csrf_failed` | `Request blocked. Refresh the page and try again.` |
| 403 | `registration_not_allowed` | `We couldn't create an account with the details provided.` |
| 409 | `email_taken` | `An account with this email already exists.` |
| 422 | `password_breached` | `This password has appeared in a data breach. Choose a different one.` |
| 429 | `rate_limited` | `Too many attempts. Try again later.` (+ `Retry-After: <int seconds ≥ 1>`) |
| 404 | `not_found` | `Not found.` |
| 413 | `file_too_large` | `This file is larger than 20 MB.` |
| 415 | `unsupported_file_type` | `Only PDF files can be uploaded.` |

- `auth/sessions.py`:
  - constants `SESSION_COOKIE = "feynman_session"`, `IDLE = timedelta(days=7)`, `ABSOLUTE = timedelta(days=30)`, `TOUCH_INTERVAL = timedelta(minutes=1)`
  - `def hash_token(token: str) -> bytes` (SHA-256 digest)
  - `async def create_session(db: AsyncSession, user_id: UUID, now: datetime) -> tuple[str, AuthSession]`:
    - token `secrets.token_urlsafe(32)`, `csrf_token=secrets.token_urlsafe(32)`
    - `created_at = last_seen_at = now`, `expires_at = now + ABSOLUTE`
    - first deletes this user's expired sessions
    - returns the plain token, which is never stored
  - `async def resolve_session(db, token: str | None, now: datetime) -> AuthSession | None`:
    - None if the token is missing or unknown
    - if `now >= expires_at` or `now >= last_seen_at + IDLE`: delete the row and return None
    - if `now - last_seen_at >= TOUCH_INTERVAL`: update `last_seen_at`
    - **commits** after a touch or a lazy delete (so a GET request keeps an active session alive and expired rows really go)
  - `async def delete_session(db, session_id: UUID) -> None`
  - `def set_session_cookie(response: Response, token: str, settings: Settings) -> None`: `httponly=True`, `samesite="lax"`, `path="/"`, `max_age=2592000`, `secure=settings.session_cookie_secure`
  - `def clear_session_cookie(response, settings) -> None`
- `Settings.session_cookie_secure: bool = True`. conftest `test_settings` uses `False`; dev `.env` uses `false` (Task 1).
- `auth/rate_limit.py`, fixed windows aligned to the epoch:
  - `async def hit(db, key: str, limit: int, window: timedelta, now: datetime) -> RateLimitResult`: `INSERT … ON CONFLICT (key, window_start) DO UPDATE SET count = count + 1 RETURNING count`, then **commit**, so the count survives the 401/403/429 that may follow. `clear` and `prune` commit too.
  - `async def peek(db, key, limit, window, now) -> RateLimitResult`: reads only
  - `async def clear(db, key: str) -> None`
  - `@dataclass(frozen=True) class RateLimitResult: allowed: bool; retry_after: int` (seconds to window end, ceil, ≥ 1). For `hit`, `allowed` is `count <= limit`; for `peek`, `count < limit`.
  - `def email_key(email: str) -> str` = `"login:email:" + sha256(email.lower()).hexdigest()`; `def ip_key(prefix: str, ip: str) -> str`
  - `async def prune(db, now)` deletes windows older than 1 day; called at the start of each login and register (a sequential scan is fine at MVP volume) *(orch.)*
  - Settings: `login_email_failure_limit=5`, `login_ip_limit=20`, `login_window_seconds=900`, `register_ip_limit=5`, `register_window_seconds=3600`.
- `auth/csrf.py`:
  - `UNSAFE_METHODS = {"POST","PUT","PATCH","DELETE"}`
  - `def origin_allowed(request, settings) -> bool`: `Origin` header present and in `settings.cors_origins`. A missing Origin is **not** allowed.
  - `def csrf_token_valid(request, session: AuthSession) -> bool` uses `hmac.compare_digest` on the `X-CSRF-Token` header.
- `auth/dependencies.py`:
  - `@dataclass class CurrentUser: user: User; session: AuthSession`
  - `async def current_user(request, db = Depends(get_session), clock = Depends(get_clock)) -> CurrentUser`: reads the cookie and calls `resolve_session`; on failure raises 401 `not_authenticated`. For unsafe methods it then checks `origin_allowed` **and** `csrf_token_valid`, else 403 `csrf_failed`. Auth comes first, then CSRF, so every authenticated unsafe route gets CSRF from this one dependency.
  - `async def require_origin(request) -> None`: 403 `csrf_failed` if not `origin_allowed`. Used by register and login.
  - `def client_ip(request) -> str` = `request.client.host` or `"unknown"` (no `X-Forwarded-For`).

- [ ] **Step 1: Write the failing tests** (DB tests use `db_session`; times come from explicit `now` values):
```python
async def test_session_token_stored_only_hashed(db_session)   # token, s = create_session(...); s.token_hash == sha256(token).digest(); token not in any column of the row (select all columns, str() them)
async def test_resolve_valid_and_unknown(db_session)
async def test_idle_expiry(db_session)       # resolve at now+7d-1s → ok (and last_seen_at updated); then at that time+7d → None and row deleted
async def test_absolute_expiry(db_session)   # touch every 6 days; at created+30d → None
async def test_last_seen_throttled(db_session)  # resolve at +30s → last_seen_at unchanged; at +61s → updated
async def test_touch_persists_across_sessions(db)  # resolve at +2min in one session; a NEW session reads last_seen_at == +2min (pins the commit)
async def test_rate_limit_hit_survives_rollback(db)  # hit, then session.rollback(); a new session still sees count 1
async def test_create_session_prunes_users_expired_sessions(db_session)
async def test_rate_limit_hit_counts_and_blocks(db_session)  # limit 3: hits 1..3 allowed, 4th not; retry_after == seconds to window end
async def test_rate_limit_new_window_resets(db_session)
async def test_rate_limit_clear(db_session)
def test_email_key_hashes_email(): "a@x.com" not in email_key("A@x.com"); email_key("A@x.com") == email_key("a@x.com")
```
  The dependency-level tests (401/403 through real routes) are in Task 6.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. `make check`.
- [ ] **Step 5:** Commit `feat(api): hashed server-side sessions, postgres rate limiter, csrf/origin checks`. gitleaks, push.

---

### Task 6: Auth routes

**Files:**
- Create: `api/src/feynman_api/routes/auth.py`, `api/src/feynman_api/auth/schemas.py`, `api/tests/{test_auth_routes,test_csrf_matrix,test_auth_logs}.py`
- Modify: `main.py` (include the router), conftest (helpers), `web/src/api/schema.gen.ts` (regenerated)

**Interfaces:**
- Schemas:
  - `UserOut{id: UUID, email: str, created_at: datetime}`
  - `SessionOut{user: UserOut, csrf_token: str}`
  - `RegisterIn{email: EmailStr, password: str, birth_month: int (1–12), birth_year: int}`:
    - the password is NFKC-normalised by a validator, then must be 12–128 chars, with a message that never echoes the value
    - `birth_year` must be between `today.year - 120` and `today.year`
  - `LoginIn{email: EmailStr, password: str (max 1024; no min, so short wrong passwords get 401 not 422)}`
  - `DeleteAccountIn{password: str}`
  - Emails are stored and compared lower-cased and stripped.
- Routes (design §7.3; all responses documented with `responses={…: {"model": ErrorResponse}}`):
  - `POST /auth/register`, deps `require_origin`. Steps in order:
    1. `prune` the rate-limit windows.
    2. Per-IP `hit("register:ip:<ip>", register_ip_limit, …)`; over the limit → 429.
    3. Age check: `age = today.year - birth_year - (1 if birth_month > today.month else 0)`; `age < 13` → 403 `registration_not_allowed`, nothing written except the rate-limit counter.
    4. `breach_checker.is_breached` → 422 `password_breached`.
    5. Insert the user with `age_verified_at=now`, catching the unique violation → 409 `email_taken`.
    6. `create_session`, set the cookie → **201** `SessionOut`.
    `today` comes from the clock (UTC).
  - `POST /auth/login`, deps `require_origin`. Order (design §7.8):
    1. `prune`.
    2. `hit` the per-IP key (429 if over).
    3. `peek` the per-email key (429 if over, **before** any password check).
    4. Look up the user: unknown → `verify_dummy` then 401; wrong password → `hit` the email key, then 401 `invalid_credentials`.
    5. On success: `clear` the email key, rehash if `needs_rehash`, delete the session from any incoming cookie, `create_session`, set the cookie → 200 `SessionOut`.
  - `POST /auth/logout`, dep `current_user`: delete the row, clear the cookie → 204.
  - `GET /auth/session`, dep `current_user` → 200 `SessionOut` (same csrf token as stored).
  - `DELETE /auth/account`, dep `current_user`, body `DeleteAccountIn`:
    1. A wrong password → 401 `invalid_credentials`. This is **not** `not_authenticated`, so the SPA doesn't log out.
    2. Collect the user's `documents.storage_key` values, `DELETE` the user (the cascade removes everything, including sessions), and commit.
    3. Then `file_store.delete` each key (log failures, don't raise). Clear the cookie → 204.
- conftest helpers:
  - `ORIGIN = {"Origin": "http://localhost:5173"}`
  - `async def register(client, email="a@example.com", password="a-long-passphrase", **kw) -> httpx.Response` (birth 1 / today.year - 20 by default)
  - `async def auth_headers(client) -> dict[str, str]`: `ORIGIN | {"X-CSRF-Token": <from GET /auth/session>}`
  - `user_client` / `other_user_client` fixtures: two `httpx.AsyncClient`s on the same app, each registered and logged in with its own cookie jar.

- [ ] **Step 1: Write the failing tests** (`clean_db` on all):
```python
# test_auth_routes.py
async def test_register_success(api_client)              # 201; body.user.email lower-cased; csrf_token non-empty; users.age_verified_at not null; no column named like 'birth' exists in users
async def test_register_sets_session_cookie_flags(api_client)  # Set-Cookie for feynman_session has HttpOnly, SameSite=lax, Path=/, Max-Age=2592000; no Secure (test settings)
async def test_secure_flag_follows_setting()             # app with session_cookie_secure=True → "Secure" in Set-Cookie
async def test_register_duplicate_email_409()            # second register with "A@Example.com" → 409 email_taken
@pytest.mark.parametrize("pw", ["x"*11, "x"*129])
async def test_register_password_length_422(pw)         # 422 validation_error; pw not in r.text
async def test_register_breached_422()                  # password "breached-password-123" → 422 password_breached, no user row
async def test_register_under_13_refused_neutrally(clock)  # birth = this month, year-12 → 403 registration_not_allowed; message has no digits and no "age"/"13"; no user row
async def test_register_13th_birthday_month_allowed(clock)  # birth_month == today.month, birth_year == today.year-13 → 201
async def test_register_requires_origin()               # no Origin → 403 csrf_failed; Origin http://evil.example → 403
async def test_register_rate_limited_per_ip()           # 6th attempt in the hour → 429 rate_limited with integer Retry-After
async def test_login_success_rotates_session()          # register (cookie A), login → new cookie B ≠ A; A no longer resolves
async def test_login_wrong_password_generic(); async def test_login_unknown_email_generic()  # both 401, identical body
async def test_login_email_lockout_blocks_correct_password(clock)  # 5 wrong → 401 each; 6th with correct pw → 429 + Retry-After; clock.advance(minutes=15) → correct pw 200
async def test_login_success_clears_email_failures()    # 4 wrong, 1 right, 4 wrong → all 401 (no 429)
async def test_login_ip_limit()                         # 21st attempt from the same IP within 15 min → 429
async def test_login_rehashes_outdated_hash(db)        # set the user's password_hash to an argon2 hash made with time_cost=1; login 200 → stored hash changed and needs_rehash() is False
async def test_session_endpoint(); async def test_session_401_without_cookie()  # 401 not_authenticated
async def test_logout_invalidates_session()             # logout 204; GET /auth/session with the old cookie → 401
async def test_idle_expiry_via_api(clock)               # clock.advance(days=7, seconds=1) → GET /auth/session 401
async def test_delete_account_wrong_password_keeps_session()  # 401 invalid_credentials; GET /auth/session still 200
async def test_delete_account_removes_rows_and_files(file_store)  # create a user, write a file via file_store.put and a documents row (direct DB insert as app); DELETE /auth/account → 204; no rows for that user in any table; file gone; cookie cleared
# test_csrf_matrix.py
async def test_every_unsafe_route_enforces_origin_and_csrf(app, user_client)
#   enumerate app.routes (APIRoute) × methods ∩ UNSAFE_METHODS; fill path params with uuid4(); for each:
#   (a) authenticated, correct CSRF, Origin missing → 403 csrf_failed; (b) Origin evil → 403;
#   (c) for every unsafe route except POST /auth/register and POST /auth/login: correct Origin, no X-CSRF-Token → 403; wrong token → 403.
#   register/login get only (a)/(b). Assert the enumerated set is non-empty and includes ("POST","/auth/logout").
# test_auth_logs.py
async def test_no_secrets_in_logs(api_client, caplog)   # SENTINEL = a unique password generated at runtime (e.g. "Zq-" + secrets.token_hex(8) + "-9!"), never a literal: gitleaks flags a literal; caplog.set_level(DEBUG); register(password=SENTINEL, birth_year=1987, birth_month=7) → login → session → logout → login → delete account; assert SENTINEL not in caplog.text, "birth_" not in caplog.text, cookie token and csrf token not in caplog.text; **positive control:** a known log line from the flow is present (e.g. the HIBP-disabled path or a `logger.info("user registered")` the route emits with the user id only), so the test can't pass on empty logs. Build the app in a fixture, never in the test body
```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. Run `make gen-types`. **Step 4:** Run → PASS; `make check`.
- [ ] **Step 5:** Commit `feat(api): register, login, logout, session and account deletion endpoints`. gitleaks, push.

---

### Task 7: Study sets and flashcards

**Files:**
- Create: `api/src/feynman_api/routes/{study_sets,flashcards}.py` (schemas inline or in `routes/schemas.py`), `api/tests/{test_study_sets,test_flashcards,test_ownership}.py`
- Modify: `main.py`, `schema.gen.ts`

**Interfaces:**
- Schemas:
  - `DocumentSummary{id: UUID, status: Literal["processing","ready","failed"], page_count: int | None, original_filename: str, error_message: str | None}`. `id` (for polling) and `error_message` (so a failed set shows its real message after a reload) are additions to design §7.3's summary *(orch.)*.
  - `StudySetOut{id, title, description: str | None, card_count: int, document: DocumentSummary | None, created_at, updated_at}`
  - `StudySetCreate{title: str (strip; 1–120), description: str | None (≤ 1000)}`
  - `StudySetUpdate{title?: str, description?: str | None}`: an omitted field is unchanged; an explicit `null` description clears it. Use `model_fields_set`.
  - `FlashcardOut{id, study_set_id, front, back, origin: Literal["manual","generated"], created_at, updated_at}`
  - `FlashcardCreate{front: str (1–500), back: str (1–2000)}`: stored **unmodified** (line breaks kept); rejected if `value.strip() == ""`.
  - `FlashcardUpdate{front?, back?}`: same rules.
- Ownership helpers (in `routes/study_sets.py` or `auth/ownership.py`), the **only** way routes load owned rows:
  - `async def get_owned_set(db, user_id, set_id) -> StudySet` (raises 404 `not_found`)
  - `async def get_owned_card(db, user_id, card_id) -> Flashcard` (joins `study_sets` on `user_id`)
  - Task 9 adds `get_owned_document`.
  - Never load by id and then compare owners; the `WHERE` includes `user_id`.
- Routes (all `Depends(current_user)`):
  - `GET /study-sets` returns the user's own sets, newest first, with `card_count` and `document`, in **one** query (a subquery count plus an outer join; no N+1)
  - `POST /study-sets` → 201
  - `GET/PATCH/DELETE /study-sets/{set_id}`. DELETE → 204: read the document's `storage_key` if any, delete the set, commit, then `file_store.delete` (failures logged, not raised).
  - `GET /study-sets/{set_id}/flashcards`, ordered by `created_at, id`
  - `POST /study-sets/{set_id}/flashcards` → 201
  - `PATCH/DELETE /flashcards/{card_id}`; DELETE → 204
- Test helpers in `test_ownership.py`: `@dataclass class Ids: set_id: UUID; card_id: UUID; document_id: UUID | None = None`, and `OWNED_ENDPOINTS: list[tuple[str, str, Callable[[Ids], str], dict | None]]` (method, route path template exactly as in `APIRoute.path`, URL builder, JSON body). Task 9 sets `document_id` (inserting a document row for A's set via `db`) and appends the document entries.

- [ ] **Step 1: Write the failing tests:**
```python
# test_study_sets.py
async def test_create_list_get_update_delete_set(user_client)  # full happy path; list newest first; card_count counts; document is None
async def test_set_title_validation()          # "", "   ", 121 chars → 422; 120 OK
async def test_patch_description_null_clears()
async def test_delete_set_removes_cards_document_pages_and_file(user_client, file_store, db)  # insert a document + page + file for the set; DELETE → 204; rows gone; file gone
async def test_delete_set_file_delete_failure_is_logged_not_raised(monkeypatch, caplog)  # file_store.delete raises OSError → still 204; warning logged
async def test_list_sets_requires_auth(api_client)  # 401 not_authenticated
# test_flashcards.py
async def test_card_crud_and_order(user_client)  # 3 cards → listed in creation order; patch front; delete
async def test_card_preserves_line_breaks()      # front "a\nb" round-trips exactly
@pytest.mark.parametrize("front,back", [("", "b"), ("  ", "b"), ("x"*501, "b"), ("f", "x"*2001)])
async def test_card_validation(front, back)      # 422
async def test_card_origin_is_manual()
# test_ownership.py
async def test_ownership_matrix(user_client, other_user_client)
#   A creates a set + card; for each OWNED_ENDPOINTS entry, B's request with A's ids → 404 with body == the body for a random uuid4 id; afterwards A's set and card are unchanged (GET as A)
async def test_ownership_matrix_covers_every_id_route(app)
#   {(method, route.path) for APIRoute in app.routes if "{" in route.path} == {(m, p) for m, p, *_ in OWNED_ENDPOINTS}
async def test_list_sets_shows_only_own()
```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement; `make gen-types`. **Step 4:** Run → PASS; `make check`.
- [ ] **Step 5:** Commit `feat(api): study sets and flashcards with owner-scoped access`. gitleaks, push.

---

### Task 8: Job queue and worker

**Files:**
- Create: `api/src/feynman_api/jobs/{__init__,queue,registry,worker}.py`, `api/src/feynman_api/jobs/handlers/__init__.py`, `api/src/feynman_api/worker.py`, `api/tests/{test_queue,test_worker}.py`
- Modify: `config.py`, `.env.example`, `Makefile` (`worker: cd api && uv run python -m feynman_api.worker`)

**Interfaces:**
- `queue.py`:
  - `async def enqueue(db: AsyncSession, *, kind: str, payload: dict[str, Any], user_id: UUID) -> Job`: adds and flushes in the caller's transaction; never commits.
  - `async def claim(db: AsyncSession, lease: timedelta) -> Job | None`: one statement, `UPDATE jobs SET status='running', attempts=attempts+1, locked_until=now()+:lease, updated_at=now() WHERE id = (SELECT id FROM jobs WHERE (status='queued' AND run_after<=now()) OR (status='running' AND locked_until<now()) ORDER BY run_after, created_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *`. The caller commits.
  - `async def mark_succeeded(db, job: Job, result: dict | None) -> bool`
  - `async def mark_retry(db, job, error: str, delay: timedelta) -> bool` (back to `queued`, `run_after=now()+delay`, `locked_until=NULL`)
  - `async def mark_failed(db, job, error: str) -> bool`
  - Each `mark_*` does `UPDATE … WHERE id=:id AND status='running' AND attempts=:attempts` and returns False if 0 rows match. That means the lease was lost, and the caller rolls back *(orch.)*. `last_error` is truncated to 500 chars.
- `registry.py`:
  - `class PermanentJobError(Exception)`: `__init__(self, user_message: str)`, where `user_message` is a fixed user-facing string.
  - `class JobHandler(Protocol)`:
    - `async def run(self, db: AsyncSession, job: Job, ctx: WorkerContext) -> dict[str, Any] | None`
    - `async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None`
  - `GENERIC_FAILURE = "Something went wrong while processing this PDF. Try uploading it again."` (design §7.6 step 7). 2a's only handler is PDF-specific; a per-handler message can come later.
  - `@dataclass class WorkerContext: settings: Settings; file_store: FileStore`
  - `HANDLERS: dict[str, JobHandler]` and `def register(kind: str, handler: JobHandler) -> None`
- `jobs/worker.py`:
  - `async def run_once(sessionmaker: async_sessionmaker[AsyncSession], ctx: WorkerContext, handlers: Mapping[str, JobHandler]) -> bool`: returns True if it processed a job. The `Job` from the claim session is reused in later sessions, so the sessionmaker **must** have `expire_on_commit=False` (use `create_sessionmaker`); later sessions re-select or `merge` the row as needed.
  - `async def run_forever(sessionmaker, ctx, handlers, stop: asyncio.Event) -> None`: polls every `job_poll_interval_seconds` when idle; checks `stop` between jobs and never mid-job.
  - `def main() -> None`: `Settings()`, its own engine as `feynman_app`, `LocalFileStore(settings.upload_dir)`, SIGINT/SIGTERM set `stop`, logs start and stop. `feynman_api/worker.py` calls `jobs.worker.main()` under `if __name__ == "__main__"`.
  - `run_once` algorithm:
    1. **Claim** in its own transaction and commit. Unknown `kind` → `mark_failed(job, "unknown job kind")`.
    2. If `job.attempts > job.max_attempts` (a reclaimed job whose lease expired on its last try), go straight to the failure path (step 4) with `GENERIC_FAILURE` and don't run it.
    3. **Run** in a new transaction: `result = await handler.run(db, job, ctx)`, then `mark_succeeded`, then commit (handler writes and the job outcome commit together). If `mark_*` returns False, roll back and log.
    4. On `PermanentJobError as e`: roll back. In a new transaction, `mark_failed(job, e.user_message)` and `handler.on_failed(db, job, e.user_message)`, then commit.
    5. On any other `Exception`: roll back and log the traceback at ERROR. If `attempts < max_attempts`: `mark_retry(job, type(exc).__name__, backoff)` with `backoff = job_backoff_base_seconds * 2**attempts` seconds. Else `mark_failed(job, type(exc).__name__)` plus `handler.on_failed(db, job, GENERIC_FAILURE)`, then commit. `last_error` never holds `str(exc)` or a traceback.
- Settings: `job_lease_seconds: int = 300`, `job_poll_interval_seconds: float = 1.0`, `job_backoff_base_seconds: float = 10.0`.
- Tests register throwaway handlers (`OkHandler`, `FlakyHandler(fail_times)`, `PermanentHandler`, `RecordingHandler`) in a local dict passed as `handlers`; they don't touch the global registry.

- [ ] **Step 1: Write the failing tests** (`clean_db`; jobs committed through real sessions as `feynman_app`):
```python
# test_queue.py
async def test_enqueue_is_in_callers_transaction()     # enqueue then rollback → no row
async def test_claim_due_job_sets_running_and_lease()  # attempts 1, locked_until ≈ now+lease
async def test_claim_skips_future_run_after()
async def test_expired_lease_is_reclaimed()            # job running with locked_until in the past → claimed again, attempts 2
async def test_skip_locked_second_claimer_gets_nothing()  # session A claims (uncommitted); session B claim → None; A commits
async def test_concurrent_claimers_get_distinct_jobs() # 5 jobs; 5 claims via asyncio.gather on 5 separate sessions → 5 distinct ids
async def test_mark_fails_after_lease_lost()           # claim; another claimer reclaims after expiry (attempts bumped) → original mark_succeeded returns False
# test_worker.py
async def test_success_stores_result()                 # OkHandler → status succeeded, result stored, locked_until null
async def test_transient_error_retries_with_backoff()  # FlakyHandler(fail_times=1): after run_once status queued, attempts 1, run_after ≈ now + 20s (10*2**1), last_error == "RuntimeError"; set run_after to past, run_once → succeeded
async def test_transient_exhaustion_fails_and_calls_on_failed()  # always-raise; force run_after due between runs; after 3 runs status failed; on_failed called once with GENERIC_FAILURE
async def test_permanent_error_fails_immediately()     # PermanentHandler("Nope.") → failed after 1 run, last_error "Nope.", on_failed("Nope.")
async def test_reclaimed_exhausted_job_fails()         # job running, attempts 3, max 3, lease expired → run_once fails it with GENERIC_FAILURE; handler.run NOT called
async def test_handler_writes_roll_back_on_error()     # handler inserts a study_set then raises → no study_set row
async def test_last_error_never_contains_exception_text()  # raise RuntimeError("secret-path /etc/x") → last_error == "RuntimeError"
async def test_run_forever_stops_on_event()            # stop.set() while idle → returns within 2 poll intervals (interval 0.05)
```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS; `make check`. Manual: `make worker` starts, logs that it's polling, and exits cleanly on Ctrl-C.
- [ ] **Step 5:** Commit `feat(api): postgres job queue with leases, retries and a worker process`. gitleaks, push.

---

### Task 9: PDF upload endpoint with the size cap, and document status

**Files:**
- Create: `api/src/feynman_api/upload_limit.py`, `api/src/feynman_api/routes/documents.py`, `api/tests/{test_upload,test_documents}.py`
- Modify: `main.py`, `config.py`, `pyproject.toml`/`uv.lock` (`uv add python-multipart`), `tests/test_ownership.py` (append entries), `schema.gen.ts`

**Interfaces:**
- `Settings.max_upload_bytes: int = 20 * 1024 * 1024` (20 MiB = 20 971 520 bytes; "20 MB" in copy) *(orch.)*; `upload_multipart_allowance_bytes: int = 64 * 1024`.
- `class BodySizeLimitMiddleware` (pure ASGI): `__init__(self, app, *, path: str, max_bytes: int)`. Applies only to `POST` requests with `scope["path"] == path`.
  - A declared `Content-Length` > `max_bytes` → sends 413 `file_too_large` immediately, without reading the body.
  - Otherwise it wraps `receive` to count `http.request` body bytes. Once the count exceeds `max_bytes` it sets a flag and returns `{"type": "http.disconnect"}` instead of the chunk, which stops the parser reading. It also wraps `send`: while the flag is set, the inner app's response messages are **dropped**, and after the inner app returns the middleware sends the 413 `file_too_large` body itself. Don't rely on an exception from `receive` reaching the middleware: FastAPI wraps any non-`HTTPException` raised during `request.form()` as a 400.
  - `max_bytes` = `max_upload_bytes + upload_multipart_allowance_bytes`.
- Route `POST /documents` (`Depends(current_user)`, `file: UploadFile`, `title: str | None = Form(None)`):
  1. Read the first 5 bytes. Not `b"%PDF-"` → 415 `unsupported_file_type`.
  2. `key = new_storage_key()`, then `file_store.put(key, chunks)`. The chunk generator yields the first bytes and then 64 KiB reads, counting, and raises `AppError(413, "file_too_large", …)` once the total exceeds `max_upload_bytes`. `put` deletes the partial file.
  3. In one transaction: create the `StudySet` (title = `title.strip()` if given, else derived from the filename), the `Document` (`status="processing"`, `size_bytes`, `original_filename`) and `enqueue(kind="extract_pdf", payload={"document_id": str(doc.id)}, user_id=…)`. Commit. If the transaction fails, `file_store.delete(key)` and re-raise.
  4. → **202** `UploadOut{study_set: StudySetOut, document: DocumentOut}`.
  - Filename handling *(orch.)*: `display_name(raw: str | None) -> str`:
    - take the basename after both `/` and `\`
    - drop control characters, collapse whitespace, strip
    - truncate to 255
    - empty → `"document.pdf"`
    Title = `display_name` without a trailing `.pdf` (case-insensitive), truncated to 120, or `"Untitled PDF"` if empty. The filename is **never** used in a path.
- `DocumentOut{id, study_set_id, status, page_count: int | None, error_message: str | None, original_filename: str}`.
- `GET /documents/{document_id}` (owner-scoped via `get_owned_document`, which joins `study_sets.user_id`) → `DocumentOut`.
- Patch targets for tests: `feynman_api.routes.documents.enqueue` (import `enqueue` by name into that module).
- `OWNED_ENDPOINTS` gains `("GET", "/documents/{document_id}", …)`. The CSRF matrix test now covers `POST /documents` automatically.
- Middleware order after this task: call `add_middleware(BodySizeLimitMiddleware, …)` **before** `ServerErrorJSONMiddleware` and `CORSMiddleware`, so it runs innermost and its 413 still gets CORS headers.
- `routes/documents.py` imports `jobs.queue` only. Neither `jobs/__init__.py` nor anything the API imports pulls in `jobs.handlers` (that is what keeps pypdfium2 out of the API process; Task 10 tests it). Only `jobs/worker.py:main` imports `jobs.handlers`.

- [ ] **Step 1: Write the failing tests.** Fixture `tmp_tempdir`: `monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "t"))` (created). Helper `assert_nothing_stored()`: no `study_sets`/`documents`/`jobs` rows, `file_store` root empty (no `.part` either), temp dir empty. On Linux, Starlette's spooled temp files are unlinked at creation, so the temp-dir check is a cheap guard; the DB and `UPLOAD_DIR` assertions are the real evidence.
```python
async def test_upload_text_pdf_202(user_client, db)  # filename "text.pdf", body b"%PDF-1.4\n%test\n" (the API doesn't parse PDFs) → 202; set title == "text"; document processing; one queued extract_pdf job whose payload document_id matches; file present under the key
async def test_upload_title_override()
async def test_upload_non_pdf_415(tmp_tempdir)       # b"hello" named x.pdf → 415 unsupported_file_type; assert_nothing_stored
async def test_upload_too_large_declared_content_length(tmp_tempdir)  # Content-Length: 30_000_000 with a small body (if httpx rewrites the header, drive the ASGI app directly with a hand-built scope) → 413; assert_nothing_stored
async def test_upload_too_large_chunked(tmp_tempdir)  # httpx content=async generator (no Content-Length) streaming a multipart body > cap → 413; assert_nothing_stored
async def test_upload_too_large_by_one_byte_in_handler(tmp_tempdir)  # file of b"%PDF-" + (20 MiB - 5 + 1) bytes, total under middleware cap → 413 from the handler; assert_nothing_stored
async def test_upload_exactly_20_mib_ok()             # 20 MiB exactly → 202
async def test_upload_filename_never_used_as_path()   # filename "../../evil.pdf" → stored key is 32 hex chars; original_filename == "evil.pdf"; nothing outside root
async def test_upload_requires_auth_and_csrf()        # no cookie → 401; no CSRF → 403 (also covered by the matrix)
async def test_upload_db_failure_removes_file(monkeypatch)  # make enqueue raise → 500; file_store root empty
# test_documents.py
async def test_get_document_status(user_client)
async def test_get_other_users_document_404()          # also in the matrix
```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement; `make gen-types`. **Step 4:** Run → PASS, including `test_ownership_matrix_covers_every_id_route` and the CSRF matrix. `make check`.
- [ ] **Step 5:** Commit `feat(api): pdf upload with streaming size cap, document status endpoint`. gitleaks, push.

---

### Task 10: `extract_pdf` handler and fixture PDFs

**Files:**
- Create: `api/src/feynman_api/jobs/handlers/extract_pdf.py`, `api/tests/test_extract_pdf.py`, `api/tests/fixtures/{make_fixtures.py,README.md,text.pdf,image_only.pdf,too_many_pages.pdf,corrupt.pdf}`
- Modify: `pyproject.toml`/`uv.lock` (`uv add pypdfium2`; add a mypy `ignore_missing_imports` override for `pypdfium2*` **only if** it ships no type info), `jobs/handlers/__init__.py` (registers `"extract_pdf"`)

**Interfaces:**
- Messages, **exact** (design §7.6):
  - `MSG_UNREADABLE = "This file couldn't be read as a PDF."`
  - `MSG_TOO_MANY_PAGES = "This PDF has more than 200 pages."`
  - `MSG_NO_TEXT = "This PDF looks scanned or has no selectable text, so it can't be read yet."`
  - The generic message is `GENERIC_FAILURE` (Task 8).
- `class ExtractPdfHandler(JobHandler)`:
  - `run`:
    1. Load the document `FOR UPDATE` by `payload["document_id"]`. Missing → return `{"skipped": "document_deleted"}`.
    2. In `asyncio.to_thread`: open `ctx.file_store.open(key)` with `pdfium.PdfDocument` (the module does `import pypdfium2 as pdfium`; tests patch `feynman_api.jobs.handlers.extract_pdf.pdfium.PdfDocument`). `PdfiumError` or `FileNotFoundError` → `PermanentJobError(MSG_UNREADABLE)`.
    3. `len(pdf) > settings.max_pdf_pages` → `PermanentJobError(MSG_TOO_MANY_PAGES)`.
    4. For each page: `page.get_textpage().get_text_range()`. Close textpages, pages and the document (in `finally`).
    5. Delete the existing `document_pages` for the document, insert one row per page (`page_number` from 1), set `page_count`.
    6. If the total non-whitespace chars across all pages are fewer than `settings.min_document_text_chars` → `PermanentJobError(MSG_NO_TEXT)`.
    7. Else `status="ready"`, `error_message=None`, and return `{"page_count": n}`.
  - `on_failed(db, job, msg)`: if the document still exists, `status="failed"` and `error_message=msg`. The pages written in this attempt were rolled back with the transaction.
- Settings: `max_pdf_pages: int = 200`, `min_document_text_chars: int = 100`.
- Fixtures: `make_fixtures.py` uses **only the stdlib**. It writes minimal valid PDFs by hand: objects, Helvetica `BT … Tj ET` content streams, and a correct xref.
  - `text.pdf`: 3 pages, each with a sentence over 60 chars
  - `image_only.pdf`: 1 page whose content stream only draws a filled rectangle (no text)
  - `too_many_pages.pdf`: 201 empty pages
  - `corrupt.pdf`: `b"%PDF-1.7\n"` followed by garbage bytes
  `README.md` says how to regenerate them (`cd api && uv run python tests/fixtures/make_fixtures.py`) and that the script is not a runtime dependency. Committed PDFs total < 200 KB.

- [ ] **Step 1: Write the failing tests** (through `run_once` with the real `ExtractPdfHandler`, a document row and a file put into a tmp `LocalFileStore`):
```python
async def test_text_pdf_becomes_ready()          # status ready, page_count 3, document_pages 1..3 with the expected sentences, job succeeded
async def test_reprocessing_replaces_pages()     # run twice (re-enqueue) → still exactly 3 pages
async def test_too_many_pages_fails_with_message()  # status failed, error_message == MSG_TOO_MANY_PAGES, job failed after 1 attempt
async def test_image_only_fails_with_message()   # MSG_NO_TEXT; no document_pages rows
async def test_corrupt_pdf_fails_with_message()  # MSG_UNREADABLE
async def test_missing_file_fails_unreadable()
async def test_document_deleted_mid_processing_is_noop()  # enqueue, then delete the set, then run_once → job succeeded with result {"skipped": "document_deleted"}
async def test_unexpected_error_exhausts_to_generic(monkeypatch)  # monkeypatch extract_pdf.pdfium.PdfDocument to raise RuntimeError; run 3 times (making run_after due) → document failed with GENERIC_FAILURE; never left "processing"
def test_extraction_not_imported_by_api():       # import feynman_api.main in a subprocess (`python -c`) and assert "pypdfium2" not in sys.modules
```
- [ ] **Step 2:** Generate the fixtures, then run → FAIL. **Step 3:** Implement and register. **Step 4:** Run → PASS; `make check`.
- [ ] **Step 5: Manual end-to-end (API only).** `make api` and `make worker`. With curl, register (with `-H 'Origin: http://localhost:5173'`, keeping the cookie jar), `POST /documents` with `tests/fixtures/text.pdf` and the CSRF header, then poll `GET /documents/{id}` → `ready` within a few seconds. Record the output (redact the cookie).
- [ ] **Step 6:** Commit `feat(api): extract_pdf worker handler with page, size and scanned-pdf limits`. gitleaks, push.

---

### Task 11: Web foundation: Tailwind + shadcn, tokens, client middleware, auth state, routes

**Files:**
- Create: `web/components.json`, `web/src/index.css`, `web/src/lib/utils.ts`, `web/src/components/ui/*` (via the CLI), `web/src/components/{AppShell,RequireAuth}.tsx`, `web/src/auth/{AuthProvider.tsx,useAuth.ts,safeNext.ts}`, `web/src/test/tokens.test.ts`, `web/src/auth/*.test.ts(x)`, `web/src/api/client.test.ts` (extend)
- Modify: `package.json`/lock, `vite.config.ts` (add `@tailwindcss/vite`, alias `@` → `src`), `tsconfig.json` and `tsconfig.app.json` (`baseUrl`/`paths` `@/*`), `src/main.tsx` (import `index.css`, wrap in `AuthProvider`, mount `<Toaster />`), `src/App.tsx`, `src/pages/NotFoundPage.tsx`, `src/api/client.ts`

**Interfaces:**
- Setup:
  - `npm i tailwindcss @tailwindcss/vite`, then `npx shadcn@latest init`. Choose **Radix** primitives (not Base UI) if asked, base colour **neutral**, CSS variables **yes**.
  - Add the components `button input label card dialog alert-dialog textarea badge sonner separator` plus `native-select` if the registry has it. Otherwise make a `src/components/ui/native-select.tsx` wrapping `<select>` with token classes. Native selects keep jsdom tests simple *(orch.)*.
  - Remove `next-themes` from the sonner wrapper (`theme="light"`) and from `package.json`. Remove any font package the CLI adds, and use a system font stack token.
  - Add `.prettierignore`/ESLint entries only if needed for generated `components/ui` (prefer formatting them).
- Tokens: `index.css` holds `@import "tailwindcss"; @import "tw-animate-css";` and the shadcn `:root` variables plus `@theme inline`. Change **one** accent: `--primary` (and `--ring`) = indigo `oklch(0.511 0.262 276.966)`, with `--primary-foreground` = `oklch(0.985 0 0)` *(orch.: indigo matches the owner-viewed mockup; changing it is a one-line edit)*. No `.dark` block.
- `client.ts` additions:
  - `export function setCsrfToken(token: string | null): void`
  - `export function setUnauthenticatedHandler(fn: (() => void) | null): void`
  - `api.use({ onRequest, onResponse })`:
    - `onRequest` adds `X-CSRF-Token` when the method is not GET/HEAD/OPTIONS and a token is set
    - `onResponse`: if `status === 401` and the URL path is not `/auth/session`, read `response.clone().json()`; if `error.code === "not_authenticated"`, call the handler
  - `export function errorMessage(error: unknown, fallback = "Something went wrong. Try again."): string` returns `error.error.message` when present.
- `AuthProvider` context `AuthState`:
  - `{ status: "loading" | "signed_in" | "signed_out"; user: UserOut | null; signedIn(s: SessionOut): void; signedOut(): void; refresh(): Promise<void> }`
  - On mount it calls `GET /auth/session`: 200 → `signed_in` + `setCsrfToken`; any 401 → `signed_out` (no navigation).
  - It registers `setUnauthenticatedHandler` to call `signedOut()` and `navigate("/login?next=" + encodeURIComponent(location.pathname + location.search))`.
  - `useAuth()` throws outside the provider. `AuthProvider` uses `useNavigate`, so `main.tsx` nests `BrowserRouter > AuthProvider > App` (tests: `MemoryRouter > AuthProvider`).
- `safeNext(next: string | null): string` returns `next` only if it starts with `/`, not `//`, and contains no `\`; otherwise `"/sets"`.
- `RequireAuth`: `loading` → text `Loading…`; `signed_out` → `<Navigate to={"/login?next=" + encodeURIComponent(path+search)} replace />`; else `<Outlet />` inside `AppShell`.
- `AppShell`: a header with `Feynman Flashcard` (link to `/sets`) and nav links `Study sets` (`/sets`) and `Account` (`/account`).
- Routes (`App.tsx`):
  - `/login`, `/register`, `/status` (`StatusPage`, unchanged)
  - `/` → `<Navigate to="/sets" />` (`RequireAuth` then handles signed-out, so a signed-out visitor lands on `/login?next=%2Fsets`; that's acceptable)
  - under `RequireAuth`: `/sets`, `/sets/:setId`, `/sets/:setId/review`, `/account`
  - `*` → `NotFoundPage`
  Pages that don't exist yet are placeholder components with their heading only; Tasks 12–14 replace them.
- `NotFoundPage`: `Page not found` and a link `Go to your study sets` → `/sets`.
- `tokens.test.ts`: uses `node:fs` `globSync` over `src/pages/**/*.tsx`, `src/components/*.tsx`, `src/auth/**/*.tsx` and `src/App.tsx` (**not** `src/components/ui/**`), and fails with the file and match on:
  - `/\b(?:bg|text|border|ring|outline|fill|stroke|from|via|to|divide|placeholder|decoration|shadow|accent|caret)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black|white)(?:-\d{2,3})?(?:\/\d+)?\b/`
  - `/#[0-9a-fA-F]{3,8}\b/`
  - `/\b(?:rgb|rgba|hsl|hsla|oklch)\(/`
  - `/style=\{\{[^}]*colou?r/i`

- [ ] **Step 1: Write the failing tests:**
```ts
// client.test.ts (extend)
"adds X-CSRF-Token on POST/PATCH/DELETE when set, never on GET"   // stub fetch, inspect Request headers
"calls the unauthenticated handler on 401 not_authenticated"
"does not call it on 401 invalid_credentials"
"does not call it on 401 from /auth/session"
// safeNext.test.ts
safeNext("/sets/1?x=2") === "/sets/1?x=2"; safeNext("//evil.com") === "/sets"; safeNext("https://evil.com") === "/sets"; safeNext("/\\evil") === "/sets"; safeNext(null) === "/sets"
// RequireAuth.test.tsx (MemoryRouter + AuthProvider with fetch stubbed)
"signed-out user at /sets/abc is redirected to /login?next=%2Fsets%2Fabc"
"signed-in user sees the outlet and the nav"
"on /register a 401 from /auth/session does not redirect"
// tokens.test.ts
"screens use semantic token classes only"   // passes on the real tree; a sub-test feeds the checker a string "bg-indigo-600" and "#fff" and expects matches (proves the regexes work)
```
- [ ] **Step 2:** `npm test` → FAIL. **Step 3:** Install, init shadcn, implement. **Step 4:** `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build` → green; `make check`. `git diff --stat package.json`: only approved packages were added (paste the dependency diff in the task report).
- [ ] **Step 5:** Commit `feat(web): tailwind + shadcn foundation, theme tokens, csrf client middleware, auth provider and route guard`. gitleaks, push.

---

### Task 12: Login, register and account pages

**Files:**
- Create/replace: `web/src/pages/{LoginPage,RegisterPage,AccountPage}.tsx` (+ `.test.tsx`)

**Interfaces:**
- Consumes `useAuth`, `api`, `errorMessage`, `safeNext`, and the generated types for `/auth/*`.
- **LoginPage** (`/login`): heading `Log in`; labelled `Email`, `Password`; button `Log in`; link `Create an account` → `/register`.
  - On 200: `signedIn(body)`, then navigate to `safeNext(searchParams.get("next"))`.
  - On error: show `errorMessage(error)` in an inline alert (`role="alert"`).
  - The button is disabled while submitting. A signed-in user visiting `/login` is redirected to `/sets`.
- **RegisterPage** (`/register`): heading `Create your account`.
  - Fields: `Email`; `Password` with hint text `At least 12 characters`; `Birth month` (native select, empty placeholder `Month`, options `January`…`December` with values 1–12); `Birth year` (native select, placeholder `Year`, options current year down to current year − 100, **no default selection**).
  - Button `Create account`; link `Already have an account? Log in` → `/login`.
  - Client-side: all fields required, password length ≥ 12 (shows the hint as an error). Nothing on the page mentions an age limit.
  - On 201: `signedIn` → `/sets`. On error: the server message in an alert (`registration_not_allowed` shows its neutral message verbatim).
- **AccountPage** (`/account`): heading `Account`, the email shown, button `Log out`, and a danger section with button `Delete account`.
  - `Log out` calls `POST /auth/logout`, then `signedOut()` → `/login`.
  - `Delete account` opens an AlertDialog with title `Delete your account?`, body `This permanently deletes your account, all your study sets, cards and uploaded PDFs. This can't be undone.`, a `Password` field, `Cancel`, and a destructive button `Delete my account`.
  - On 204: `signedOut()`, toast `Your account has been deleted.`, navigate to `/register`.
  - On 401 `invalid_credentials`: an inline error in the dialog; the user **stays signed in**.

- [ ] **Step 1: Write the failing tests** (fetch stubbed per URL):
```ts
// LoginPage.test.tsx
"submits email and password and navigates to next"   // ?next=%2Fsets%2F42 → lands on /sets/42
"ignores an unsafe next"                       // ?next=//evil.com → /sets
"shows Invalid email or password. on 401 and stays on /login"   // and the unauthenticated handler did NOT fire (no redirect away)
"shows the rate-limit message on 429"
// RegisterPage.test.tsx
"shows the password hint 'At least 12 characters'"
"month select has 12 options plus placeholder; year select has 101 years and no default value"
"no visible text outside the year <option>s matches /\\b13\\b|\\bage\\b|old enough/i"
"shows server error messages (email_taken, password_breached, registration_not_allowed)"
"posts birth_month and birth_year as numbers"
// AccountPage.test.tsx
"wrong password shows an error and keeps the user signed in"   // 401 invalid_credentials → dialog error visible; AppShell nav still rendered
"successful delete signs out and goes to /register"
"log out calls /auth/logout then shows the login page"
```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Web checks green; `make check`.
- [ ] **Step 5:** Commit `feat(web): login, register (neutral age screen) and account pages`. gitleaks, push.

---

### Task 13: Sets, set detail and review pages

**Files:**
- Create/replace: `web/src/pages/{SetsPage,SetDetailPage,ReviewPage}.tsx` (+ tests), `web/src/components/{SetFormDialog,CardFormDialog,ConfirmDialog,DocumentStatus}.tsx`, `web/src/lib/shuffle.ts` (+ `shuffle.test.ts`)

**Interfaces:**
- **SetsPage** (`/sets`): heading `Your study sets`, buttons `New set` and `Upload PDF` (the latter is a placeholder until Task 14).
  - Each set is a card linking to `/sets/:id`: the title, `1 card` / `N cards`, and the document badge `Processing…` / `Ready` / `Failed` when a document exists.
  - Empty state: `No study sets yet. Create one or upload a PDF.`
  - `New set` opens a dialog (`Title` required, max 120; `Description` optional, max 1000; button `Create`). On 201: toast `Study set created.` and navigate to it.
- **SetDetailPage** (`/sets/:setId`): the title and description, with an `Edit` button opening the same dialog (button `Save`).
  - The document area uses `DocumentStatus` (Task 14 adds polling; here it renders the static status).
  - Cards list (front and back, line breaks shown with `whitespace-pre-wrap`): `Add card` opens a dialog (`Front` textarea, max 500; `Back` textarea, max 2000; button `Add`), and each card has `Edit` and `Delete`. Delete asks `Delete this card?` → `Delete`.
  - `Review` button links to `/sets/:id/review`; it is disabled with zero cards. `Delete set` asks `Delete this study set? Its cards and PDF will be deleted too.` → `Delete`, then toast `Study set deleted.` → `/sets`.
  - A 404 shows `Study set not found.` with a link back to `/sets`.
  - Toasts on failures use `errorMessage`.
- **ReviewPage** (`/sets/:setId/review`): shows one card at a time, starting with the front, and `Card i of n`.
  - Click the card or press **Space** to flip (front ↔ back).
  - **ArrowRight** or `Next`, **ArrowLeft** or `Previous`; these don't wrap, and the buttons are disabled at the ends. Moving resets to the front.
  - `Shuffle` toggle (`aria-pressed`): on → a random order via Fisher–Yates over a copy, restarting at card 1; off → creation order, restarting at card 1. The RNG is injectable for tests: `export function shuffle<T>(items: readonly T[], random: () => number = Math.random): T[]` in `web/src/lib/shuffle.ts`.
  - With 0 cards: `This set has no cards yet.`, plus a link back.
  - Keyboard handlers ignore events whose target is an input, textarea or button (to avoid double handling).

- [ ] **Step 1: Write the failing tests:**
```ts
// SetsPage.test.tsx
"lists sets with card counts and document badges"; "empty state text"; "create set dialog posts and navigates"
// SetDetailPage.test.tsx
"add, edit, delete card call the right endpoints by id"; "review disabled with no cards"; "delete set confirms then navigates to /sets"; "404 shows Study set not found."
"preserves line breaks in card text"
// ReviewPage.test.tsx
"shows Card 1 of 3 and the front; Space flips to back; ArrowRight goes to card 2 front"
"Previous disabled on first card, Next disabled on last"
"shuffle with a seeded random reorders and restarts at Card 1"
// shuffle.test.ts
"returns a permutation and does not mutate input"
```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Web checks green (including `tokens.test.ts`); `make check`.
- [ ] **Step 5:** Commit `feat(web): study sets list, set detail with card editing, and review screen`. gitleaks, push.

---

### Task 14: PDF upload and status polling

**Files:**
- Create: `web/src/components/UploadPdfButton.tsx` (+ test); `web/src/components/DocumentStatus.test.tsx`
- Modify: `DocumentStatus.tsx`, `SetsPage.tsx`

**Interfaces:**
- `UploadPdfButton`: a hidden `<input type="file" accept="application/pdf,.pdf">` triggered by the `Upload PDF` button.
  - Client checks: the name must end in `.pdf` (case-insensitive), else toast `Choose a PDF file.`; size must be ≤ `20 * 1024 * 1024`, else toast `This file is larger than 20 MB.`. The server still decides.
  - Sends `POST /documents` as multipart `FormData` with field `file`, through `api` using a `bodySerializer` that builds the `FormData` (don't set `Content-Type`). The button shows `Uploading…` while busy.
  - On 202: toast `Upload received. Processing…` and navigate to `/sets/:study_set.id`. On error: toast `errorMessage(error)`.
- `DocumentStatus({ document }: { document: DocumentSummary })`:
  - `ready` → `Ready · N pages` (`1 page` singular)
  - `failed` → the server's `error_message` (fallback `GENERIC` copy: `Something went wrong while processing this PDF. Try uploading it again.`)
  - `processing` → `Processing…`, polling `GET /documents/{id}` every **2000 ms**; it stops on `ready`/`failed` or after **10 minutes** (600 000 ms since mount), then shows `This is taking longer than expected. Check back later.`
  - The interval is cleared on unmount. A poll that errors keeps polling (the stop condition still applies).
  - Constants `POLL_MS = 2000` and `POLL_LIMIT_MS = 600_000` are exported for tests.

- [ ] **Step 1: Write the failing tests** (`vi.useFakeTimers()`):
```ts
"polls every 2 s and stops on ready"             // fetch: processing, processing, ready → 3 calls; after ready, advancing 10 s makes no further calls; shows "Ready · 3 pages"
"shows the server failure message and stops"
"stops after 10 minutes and shows the timeout copy"
"clears the interval on unmount"
// UploadPdfButton.test.tsx
"rejects a non-pdf name with 'Choose a PDF file.' and sends nothing"
"rejects > 20 MB with 'This file is larger than 20 MB.' and sends nothing"   // File with size override via Object.defineProperty
"posts multipart with field 'file' and the CSRF header, then navigates to the set"
"shows the server 413/415 message"
```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Web checks green; `make check`.
- [ ] **Step 5: Owner's manual browser check (exit criteria, design §2).** Run `make db`, `make migrate`, `make api`, `make worker`, `make web`. Check `curl -s localhost:5173` from WSL. Then **ask the owner** to run, in the **Windows** browser at `http://localhost:5173`:
  1. register
  2. log out and log in
  3. create a set
  4. add, edit and delete cards
  5. review (flip with Space, arrows, shuffle)
  6. upload `api/tests/fixtures/text.pdf` and watch it reach `Ready · 3 pages`
  7. upload `image_only.pdf` and see the scanned message
  8. delete a set
  9. delete the account
  Also ask them to confirm in DevTools → Application → Cookies that `feynman_session` is HttpOnly. **Wait** for their answer and record it verbatim for the PR. Fix anything they report before continuing.
- [ ] **Step 6:** Commit `feat(web): pdf upload with client checks and document status polling`. gitleaks, push.

---

### Task 15: `make check`, CI, docs, project record, draft PR

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `memory.md`, `docs/planning-handoff.md` (§1/§5 only where 2a changed them), `api/.env.example` (complete), `.github/workflows/ci.yml` (only if a real CI failure needs it)

- [ ] **Step 1:** `make check` → passes. Record the pytest and vitest counts. `gitleaks git --redact -v .` → no leaks. `git log --all --name-only --format= | grep -E '(^|/)\.env($|\.)' | grep -v example` → no output. `git status --porcelain` → only intended changes; nothing under `api/var/`.
- [ ] **Step 2: CI.** Push, then `gh run watch --exit-status $(gh run list --branch phase-2a-foundations --limit 1 --json databaseId -q '.[0].databaseId')` → all jobs succeed.
  - Fix genuine failures in `ci:`/`fix:` commits and repeat.
  - Zero-step failures are an account problem: stop and tell the owner.
  - The run URL goes in the PR.
  CI needs no new env: tests set their own settings, and `UPLOAD_DIR` defaults work.
- [ ] **Step 3: Docs.**
  - **README:** add `make worker` to the daily-use commands, and a short "What works" list (accounts, sets/cards, review, PDF upload). Note that the worker must run for uploads to finish.
  - **CLAUDE.md:**
    - status banner: 2a built, on PR, pending merge
    - stack table: the auth/jobs row is now built; add styling
    - repo map: the new modules
    - data model: the new tables
    - HTTP API: the new endpoints and error codes
    - commands: `make worker`
    - gotchas: the worker must run; the `SESSION_COOKIE_SECURE=false` dev setting; `clean_db` for committing tests; the shadcn `components/ui` are ours to edit; tokens live only in `index.css`
    - test counts
    Keep the vision, notes, decision-process and handoff sections in substance.
  - **planning-handoff.md:** §1/§5 only if something 2a did changes them.
- [ ] **Step 4: `memory.md`.** Bump "Last updated". Add a session-log entry "Implementation run: Phase 2a" covering: the commits per task, the test counts, the CI run URL, the owner's browser check (verbatim), deviations with reasons, and anything incomplete. Update §3 Repository state (branch, draft PR URL) and §4 next steps (the orchestrator reviews the PR; the owner merges; then the 2b decision round). Commit `docs: update README, CLAUDE.md and memory for phase 2a`. gitleaks, push, then re-run the Step 2 CI watch.
- [ ] **Step 5: Draft PR.** `gh pr create --draft --base main --head phase-2a-foundations --title "Phase 2a: accounts, study sets, PDF upload and job queue" --body-file <tmpfile>`. The body has:
  - a summary
  - the design §2 exit criteria as a checklist, each with evidence (test names, commands, the CI run link)
  - Review Focus 1–8, each with its pinning test names
  - the owner's browser check result
  - the dependencies added (with `pyproject.toml`/`package.json` diffs summarised)
  - deviations from the plan
  - "Owner merges after orchestrator review"
  - a last line of `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
  **Do not merge or mark it ready.** Report the PR URL to the owner and stop.
