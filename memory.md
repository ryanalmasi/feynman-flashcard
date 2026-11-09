# memory.md: running project context

> **Purpose:** the repo's own record of what has happened so far, so a fresh agent session can pick up without the old conversation.
> **Rule:** update this file **first** during any handoff. The handoff prompt (`handoff-prompts/orchestrator-handoff-N.md`) is written **last**, after this file and the docs are current. See "Handoffs" in `CLAUDE.md`.
> **Not the same as** Claude Code's private auto-memory (`~/.claude/projects/.../memory/MEMORY.md`). That one is outside the repo. This file is versioned with the project and is the source of truth for project state.

**Last updated:** 2026-11-09 (Phase 1 merged with CI green; Phase 2 decided through 2a: ADRs 0012–0018 and the approved 2a design. Next: write the 2a plan)
**Phase 2a implementation in progress (see the Phase 2a entry in §2; resume prompt `handoff-prompts/implementer-phase-2a-resume-1.md`).**
**Latest handoff written:** #3 (`handoff-prompts/orchestrator-handoff-3.md`), plus the implementer kickoffs `handoff-prompts/implementer-phase-1.md` and `implementer-phase-1-fixups.md`

---

## 1. Project snapshot

- **What it is:** a study tool built around the Feynman technique: the student teaches a topic to an AI, gets a multi-stage score and feedback, and reviews AI-generated flashcards built from their PDF or topic.
- **What exists in code today:** the Phase 1 foundation, merged to `main` (`3185eb1`): FastAPI app with `GET /health`, Postgres 18 in Docker with migrator/app roles, migration `0001_users` (`users`, `auth_identities`), LLM/embedder interfaces with fakes and contract tests, a Vite React TS status page with a generated typed API client, `make` targets, pre-commit + gitleaks, and a GitHub Actions workflow (green). No product features yet. `CLAUDE.md` and `README.md` describe this structure; the Jan-2025 prototype is in git history at `5aba556`.
- **Current phase:** **Phase 1 complete and merged (2026-11-09). Phase 2 (MVP) is split into 2a/2b/2c (ADR 0012). 2a's decisions are made and its design is approved; its task plan is not written yet.** Phase order: 1. refactor/restructure → 2. MVP → 3. improvements (`docs/planning-handoff.md` §0).
- **Repo location (changed in session 2):** `~/code/feynman-flashcard` (WSL Linux filesystem). The old copy at `/mnt/c/Users/ryana/Documents/Github/feynman-flashcard` is **stale** and should be renamed or deleted. Don't work there.

## 2. Session log

### Session 1 (2026-11-08): mapping, research, planning docs
Models: Opus 5.5, then Sonnet 5.5. Nothing was implemented.
- Wrote `CLAUDE.md` (repo map, known bugs) and `docs/planning-handoff.md` (roadmap §0, scoring design §2, research §3, costs and pricing §4/§4b, open decisions §5).
- Set up `memory.md`, the `/handoff` skill, and the context-usage hook (§5 below).
- Owner decided: the phase order; explain every decision first, with the owner having final say; lean Postgres; multi-stage scoring; the handoff workflow.

### Session 2 (2026-11-08 → 2026-11-09): Phase 1 decision round + implementation plan
Model: Opus 5.5 (orchestrator). No application code was changed.

**Completed**
1. Ran the Phase 1 decision round with the owner, one or two decisions at a time, and recorded **ADRs 0001–0011** in `docs/adr/` (index: `docs/adr/README.md`).
2. Wrote the design spec `docs/superpowers/specs/2026-11-08-phase-1-foundation-design.md`. A builder-check subagent reviewed it, and the owner **approved** it on 2026-11-09.
3. Wrote **`docs/implementation-plan.md`**: Phase 1 as Tasks 0–9 (TDD, one commit and push per task), Review Focus items, and a **Phase 2 milestone outline marked NOT FOR EXECUTION** (M1 auth → M9 usage logging, with the decisions each needs first).
4. Wrote `docs/setup-prerequisites.md` (machine setup and a verification block), after checking the machine.
5. Moved the repo to `~/code/feynman-flashcard` (the owner copied it; permissions were fixed to 644/755 and `core.filemode=true`).

**Decisions the owner made (all in ADRs)**
| ADR | Decision |
|---|---|
| 0001 | Backend: FastAPI, Python 3.13, uv. Baseline embeddings will be a local model (chosen in Phase 2) |
| 0002 | Frontend: Vite + React + TS SPA, Node 26 LTS (Node 26 became LTS on 2026-10-28; the docs originally said 24) |
| 0003 | Layout: `api/ web/ infra/ docs/` + root Makefile, one repo |
| 0004 | Postgres 18 (Docker), SQLAlchemy 2 async + Alembic, `feynman_migrator` / `feynman_app` least-privilege roles |
| 0005 | Auth: own server-side sessions in Postgres (HttpOnly cookie, CSRF). **Email+password in the MVP; "Continue with Google" is the first post-MVP auth feature.** Phase 1 schema: nullable `password_hash` + an `auth_identities` table. No DOB until the privacy decision |
| 0006 | Config: pydantic-settings, `.env.example` only. Leak defences: root `.gitignore` + gitleaks (pre-commit + CI). **GitHub push protection deferred** (public repo, single contributor) |
| 0007 | LLM layer: own thin Protocols (`stream_chat`, `generate_structured`, `Embedder`) with `Usage` on every call, fixed error types, fakes + contract tests. Exact signatures in spec §7.4 |
| 0008 | Background jobs: Postgres-backed queue + worker, **built in Phase 2** (procrastinate vs. hand-rolled decided then) |
| 0009 | Tooling: ruff, mypy strict, pytest on real Postgres; ESLint + Prettier, Vitest; openapi-typescript + openapi-fetch with a drift check; GitHub Actions (api, web, secrets) |
| 0010 | Old prototype: clean restart; keep only the 7 images (moved to `web/src/assets/images/`) |
| 0011 | Git: branch `phase-1-foundation`, one commit per task as `ryanalmasii <ryanalmasii@gmail.com>` (via `-c` flags), **pushed**, **draft PR** at the end. **The owner is the final reviewer and the only one who merges** |

Machine and setup decisions: **Docker Engine inside WSL** (not Docker Desktop); repo in the Linux filesystem.

**Calls made by the orchestrator (flagged to the owner, not explicitly vetoed):** the LLM interface signatures (spec §7.4); planning docs reach git via the implementer's Task 0 commit on the phase branch; `make env` generates random dev passwords; browser-facing dev URLs use `localhost`; `asgi-lifespan` is pre-approved as a test-only dependency; the app role has no `TEMPORARY` privilege on the `feynman` and `feynman_test` databases (PUBLIC still has default CONNECT/TEMPORARY on the `postgres` database; no data exposure, see open items).

**Still open (Phase 2 decisions, see the plan's Phase 2 outline):** LLM provider, embedding model, privacy/age policy, scoring parameters, UI styling approach, job-queue library, file storage, MVP scope confirmation. Phase 3: voice, pricing/billing.

### Session 3 (2026-11-09): Phase 1 review, fix-ups, merge; Phase 2 planning starts
Model: Opus 5.5 (orchestrator). No application code written by the orchestrator.

**Completed**
1. Reviewed draft PR #1 task by task against the plan, spec §2–§4 and ADRs; re-ran `make check` locally (36 pytest / 7 vitest) and checked role privileges against the live DB. Verdict: conformant. Findings: F1 CI never ran (GitHub billing lock), F2 gitleaks path-allowlisted all `*.env.example`, F3 app role could CONNECT/TEMP on the `postgres` DB, F4 app role had DML on `alembic_version`, F5 health timeout untested, F6 status page treated any error body as a health body, F7 500s carry no CORS headers (deferred to Phase 2 M1), F8 hygiene.
2. Wrote `handoff-prompts/implementer-phase-1-fixups.md`; the owner approved all fixes. A Sonnet implementer did F2–F6 + F8 (entry below). Orchestrator re-review: clean; `make check` 40 pytest / 8 vitest; action SHAs verified against their tags.
3. The owner fixed the GitHub billing lock (the $0 "usage blocked" budgets were not the cause; it was an account-level lock). CI re-run **42547339617 green** on `ff0ae19`: api 16/16, web 17/17, secrets 6/6 steps (https://github.com/ryanalmasi/feynman-flashcard/actions/runs/42547339617).
4. **The owner merged PR #1 on 2026-11-09 (squash merge → `3185eb1` on `main`).** The per-task commits remain on the `phase-1-foundation` branch and in the PR.

**Owner decisions:** approved fix-up scope including the new UI copy `API error (HTTP <status>)`, CI `push` trigger limited to `main`, actions pinned by SHA.

5. **Phase 2 decision round (2a), each recorded as an ADR (all Accepted by the owner 2026-11-09):**
| ADR | Decision |
|---|---|
| 0012 | MVP scope confirmed as planning doc §0 (generated flashcards stay in). Phase 2 split: **2a** auth + sets/cards + PDF upload/job queue (no LLM); **2b** Knowledge Map + generated cards; **2c** tutor + scoring + feedback + usage logging. Each its own branch, draft PR, owner merge |
| 0013 | Age policy: **13+ neutral age screen** (birth month/year asked, never stored or logged); only `users.age_verified_at`. Account deletion is in 2a |
| 0014 | UI: **Tailwind CSS 4 + shadcn/ui**; all design tokens in one file; screens use semantic token classes only; neutral theme + one accent, light mode. Owner chose this after viewing mockups, on condition it stays flexible |
| 0015 | Job queue: **own `jobs` table + worker** (`FOR UPDATE SKIP LOCKED`, leases, backoff); not procrastinate (needs psycopg 3) or pgqueuer |
| 0016 | Files: **local disk behind `FileStore`**, UUID keys; PDF only, 20 MB, 200 pages, text-based only; deleted with set/account |
| 0017 | Auth details: **12-char password minimum** (owner's pick; below NIST's 15 for single-factor, recorded), max ≥ 64 (128), no composition rules; HIBP range API fail-open; Postgres-backed rate limits; per-session CSRF token + Origin check; SHA-256-hashed session tokens; 7-day idle / 30-day max; argon2-cffi |
| 0018 | One PDF per study set; card front ≤ 500 / back ≤ 2000 plain text; `auth_sessions` vs later `study_sessions` naming; **pypdfium2**, PDF parsing only in the worker |
6. Wrote the **2a design** `docs/superpowers/specs/2026-11-09-phase-2a-foundations-design.md`. A builder-check subagent raised 5 questions: the owner answered two (upload limit enforced by a pure-ASGI body-size cap on `/documents` + byte counting; extra deps approved: `email-validator`, `sonner`, `tw-animate-css`, `radix-ui` umbrella; **not** `next-themes`, `react-hook-form`, `zod`), and the orchestrator settled three, marked in the doc as its calls (per-email lockout blocks even the correct password, successes reset it; unexpected job errors are transient and exhausting retries fails the document with a generic message, UI polling stops after 10 min; only 401 `not_authenticated` logs the user out). **The owner approved the design on 2026-11-09.**
7. Viewed UI mockups with the owner via the brainstorming visual companion (server needed `--host 0.0.0.0` to be reachable from the Windows browser under WSL; files under gitignored `.superpowers/`).

**Still open:** 2b decisions (LLM provider + models with prices re-verified, provider data-retention/training settings, Knowledge Map details, card count/style); 2c decisions (embedding model, scoring parameters τ/weights/δ/insufficient-evidence threshold, tutor prompt and session limits, feedback format, usage-data retention). Launch-time: EU 13–15 users, ToS/privacy policy wording.

### Implementation run: Phase 1 fix-ups (2026-11-09)
Model: Sonnet 5.5 implementer (single session, no subagents), following `handoff-prompts/implementer-phase-1-fixups.md` (orchestrator session 3 review of PR #1). Scope was closed: F2-F6 and F8 only. F1 (CI billing lock) is the owner's; F7 is deferred to Phase 2.

| Fix | Commit | What / evidence |
|---|---|---|
| F2 | `9d08911` | `.gitleaks.toml`: removed the `*.env.example` path allowlist (kept `ci-(postgres\|migrator\|app)`). `gitleaks git` clean; `gitleaks dir` flags only the gitignored local `infra/.env` (3 generated dev passwords; never tracked); the `change-me` placeholders are not flagged, so no placeholder allowlist was needed. Canary `canary.env.example` (github-pat) made `pre-commit run gitleaks-system` **fail** (exit 1); never committed. Note: the config change must be staged first, because pre-commit stashes unstaged files and a first attempt silently used the old config and passed. |
| F3 | `292b561` | `01-roles.sh`: `REVOKE CONNECT, TEMPORARY ON DATABASE postgres FROM PUBLIC`. New test `test_app_cannot_connect_to_postgres_database` (asserts `InsufficientPrivilegeError` in the exception chain) failed first ("DID NOT RAISE"), passes after `make db-reset && make migrate`. Healthcheck, `make db` probe and `make db-psql` still work. |
| F4 | `c18a97c` | `0001_users.py` `upgrade()`: `REVOKE ALL ON TABLE alembic_version FROM feynman_app`. New parametrized test (SELECT and UPDATE raise `InsufficientPrivilegeError`) failed first, passes after. `upgrade head && downgrade base && upgrade head` works on the dev DB; migration tests green. |
| F5 | `5079898` | `test_health_db_timeout_returns_503` (hanging `_probe`, 0.1s timeout, 503 body, < 1s). Passed with no code change; a mutation check (timeout forced to 30s) made it fail, so it is sensitive. |
| F6 | `8e07450` | `StatusPage`: 2xx -> as before; 503 with a health body -> "API: ok / Database: error"; any other non-2xx -> `API error (HTTP <status>)`; network failure unchanged. New 500 test failed first. |
| F8 | `3347220` | `python-dotenv` declared in the api dev group (`pyproject.toml`, `uv.lock`); CI `push` trigger is `[main]`; actions pinned by SHA (`actions/checkout` `3d3c42e5...` v7, `actions/setup-node` `949feb24...` v7, `astral-sh/setup-uv` `68559e99...` v10.3.3); the gitleaks job verifies the tarball with `sha256sum -c --ignore-missing` against `gitleaks_8.30.1_checksums.txt` before extracting (proved locally: OK on the real file, FAILED and exit 1 on a tampered copy). |

**Verification**
- `make check` passes: **40 pytest** (36 + F3 +1, F4 +2, F5 +1) and **8 vitest** (7 + F6 +1); ruff, mypy strict, ESLint, Prettier, tsc, build and the types-drift check clean. `gitleaks git --redact -v .` clean. `git log --all --name-only | grep '.env'` (excluding examples): no output.
- CI at the time was blocked by the GitHub billing lock (run 42547257090). **Superseded:** after the owner's billing fix, the re-run 42547339617 went green (see Session 3).

**Deviations:** F3's test builds the engine from `TEST_DATABASE_URL` with the database swapped to `postgres` and walks the exception chain (SQLAlchemy wraps the asyncpg error). Otherwise none.

### Implementation run: Phase 1 (2026-11-09)
Model: Sonnet 5.5 implementers, driven by an orchestrator/controller using subagent-driven development with a fresh reviewer per task. Plan: `docs/implementation-plan.md` Tasks 0-9.

**Built (one commit per task, all pushed to `phase-1-foundation`)**
- Task 0 (`e7bd5b9..7666f97`): prerequisites verified; planning docs, ADRs, spec committed.
- Task 1 (`a9f9cd1`): prototype removed (kept 7 images), root `.gitignore`, `.gitattributes`, pre-commit config, gitleaks.
- Task 2 (`bbc2a35`, fix `956c9b5`): Postgres 18 compose, least-privilege role init script, `scripts/dev-env.sh`, `make env/db/db-down/db-reset/db-psql`.
- Task 3 (`0d0c255`): `Settings`, `create_app()`, JSON error shape and handlers, CORS.
- Task 4 (`eccda9b`, fixes `61c6e68`, `747fc6b`): async DB layer, Alembic, `0001_users` migration, role/privilege and migration round-trip tests.
- Task 5 (`374a451`): `GET /health` with a bounded DB probe.
- Task 6 (`4882a94`): LLM provider and embedder Protocols, fakes, contract tests.
- Task 7 (`814c9e4`, `d82c6f2`): Vite React TS skeleton, typed openapi-fetch client, status page, types drift check; switched oxlint to ESLint.
- Task 8 (`5c32df1`, `3abaff5`): `make check` and GitHub Actions (api, web, secrets jobs).
- Task 9: README and CLAUDE.md rewrite, this record.

**Verification**
- Locally: 36 pytest tests and 7 vitest tests pass; `make check` passes (lint, test, build, types drift).
- **CI was not verified at the time (superseded: green in run 42547339617, see Session 3).** The workflow ran twice (run ids 42543755654 and 42543763849; https://github.com/ryanalmasi/feynman-flashcard/actions/runs/42543763849) and all three jobs failed with zero steps executed: "The job was not started because your account is locked due to a billing issue." The workflow was only statically reviewed. Assumptions untested on a real runner: the gitleaks tarball install, the Postgres service container, and the roles script over TCP. **The owner must resolve the GitHub billing issue, then re-run CI** (`gh run rerun <id>` or push a commit).
- Owner's manual check (Task 7 step 5): the owner opened http://localhost:5173 in the Windows browser and confirmed it shows "API: ok" and "Database: ok".

**Deviations from the plan (all reviewed; none change an ADR)**
- `.superpowers/` added to `.gitignore` (agent scratch workspace); root `.DS_Store` removed; README whitespace fix.
- `pass_filenames: false` on the `gitleaks-system` pre-commit hook.
- pre-commit revs: ruff-pre-commit bumped to v0.17.4 to match the version uv resolves (other hooks left at their earlier revs).
- Compose healthcheck uses `pg_isready -h 127.0.0.1` (TCP) so the check cannot pass during the entrypoint's temporary init server.
- The `make db` credential probe uses `-h db`, because loopback inside the container is trust-auth and would always succeed.
- API: `hatchling` build backend added (src layout needs one); pytest `asyncio_default_fixture_loop_scope = "function"`; CORS `allow_methods` GET/POST/PUT/PATCH/DELETE and `allow_headers` Content-Type; explicit `uq_auth_identities_provider_subject` constraint name; DB role tests parametrized; conftest prints a `make db` / `make db-reset` hint for every unreachable-DB failure (including wrapped invalid-password errors); `asgi-lifespan` added as a test-only dev dependency (pre-approved).
- LLM layer: `T` bound to `BaseModel` with `noqa UP046` on `Generic[T]`; `LLMRateLimitError` has keyword-only `retry_after` and a default message; the fake raises `LLMOutputValidationError` when it has no structured payloads and rejects `chunk_size`/`dimensions` < 1; a few extra tests.
- Web: TypeScript pinned `~5.9` (openapi-typescript peer); a small `fetch` wrapper in `client.ts`; the implementer first used oxlint (vite template default), contradicting the plan and ADR 0009, so it was switched to ESLint flat config + `eslint-config-prettier` (`d82c6f2`).
- `npm audit`: 10 moderate dev-only advisories (minimatch via eslint/typescript-eslint). The only fix is forcing an ESLint 9 downgrade, not applied.
- CI action pins: `actions/checkout@v7`, `actions/setup-node@v7`, `astral-sh/setup-uv@v10.3.3` (no floating `v10` tag exists; fixed in `3abaff5`); now pinned by commit SHA (`3347220`).
- `users.email` is `String` (unbounded VARCHAR) where spec §7.2 says text; the DB dependencies are named `get_session`/`get_engine` rather than the spec's `get_db`.
- TypeScript `strict` was missing after the `~5.9` pin and was restored (tsconfig.app/node) in a final-review fix.
- The CI Postgres service healthcheck was aligned with compose (`pg_isready -h 127.0.0.1 -U postgres`) in a final-review fix.
- `docs/planning-handoff.md` §1: only the "Old code" row was touched (adds the `5aba556` pointer).

**Incomplete**
- ~~CI green status (billing lock, above).~~ **Resolved**: run 42547339617 green.
- The draft PR is opened by the controller after the final whole-branch review.

**Open items for the orchestrator/owner**
- ~~`.gitleaks.toml` exempts all `*.env.example` files from scanning~~ **Resolved** in the fix-up round (`9d08911`): the path allowlist is gone; the `change-me` placeholders are not flagged, so nothing else was allowlisted.
- ~~`REVOKE CONNECT, TEMPORARY ON DATABASE postgres FROM PUBLIC`~~ **Resolved** (`292b561`).
- ~~The health-timeout branch is not pinned by a test~~ **Resolved** (`5079898`).
- `scripts/dev-env.sh` should warn when `infra/.env` is newly created but `api/.env` already exists.
- ~~CI actions are pinned by tag, not SHA~~ **Resolved** (`3347220`).
- The 500-without-CORS-headers fix is planned for Phase 2 M1.
- ~~Declare `python-dotenv` in the api dev group~~ **Resolved** (`3347220`).
- Add a try/finally to `test_migrations` and an explicit inspector assertion on `uq_users_email_lower`.
- ~~`push: phase-*` plus `pull_request` double-runs CI~~ **Resolved** (`3347220`: push trigger is `main` only).

**Deferred minors (for the orchestrator to triage)**
- T2: `make db` grep errors if `infra/.env` is missing (harmless); `db-psql` relies on socket trust; `api/.env.example` CORS_ORIGINS is unquoted JSON (fine for pydantic).
- T3: `logging.basicConfig` is a no-op if the root logger has handlers (consider `force=True`); 500s from `ServerErrorMiddleware` carry no CORS headers (Starlette limitation); `conftest` imports python-dotenv (now declared, `3347220`); the CSRF header must be added to `allow_headers` in Phase 2.
- T4: `test_migrations` assumes serial DB use and has no `finally` on the last upgrade; dead logging sections in `alembic.ini`; `type: ignore` on `orig.__cause__` is brittle; `compare_metadata` may not fully cover the functional index `lower(email)` (unverified).
- T5: ~~the db-down test doesn't prove the 2s bound~~ (resolved: `5079898` pins the timeout path); duplicated unreachable `Settings` in tests; `version()` is looked up per request.
- T6: error-propagation test uses `pytest.raises(type(err))` (accepts subclasses); no tests for structured-payload cycling or the no-structured error path; `StructuredResult.value: T` may warn on dump.
- T7: stray blank line in `index.html`; no unmount test; `typescript ~5.9` in package.json (lockfile pins exact).
- T8: ~~`push: phase-*` plus `pull_request` double-runs~~ (resolved, `3347220`); redundant `uv python install`; implicit `npm ci` dependency for `gen-types` in the web job.

### Implementation run: Phase 2a, IN PROGRESS (2026-11-09)

Implementer session 1 (Sonnet 5.5, subagent-driven-development; controller + per-task implementer + reviewer). Branch `phase-2a-foundations`, pushed. **Tasks 0-13 are complete and reviewed; Task 14 is implemented (`a04be21`) but NOT yet reviewed; Task 14 step 5 (the owner's browser check) and Task 15 remain.** The full ledger and per-task briefs/reports/review diffs are in the gitignored `.superpowers/sdd/implementation-plan-phase-2a/` (`progress.md`); it survives on this machine, but the table below is the durable summary.

| Task | Commit(s) | Notes |
|---|---|---|
| 0 docs | `370d54a` | plan line with a literal test password replaced by a runtime-generated SENTINEL (gitleaks flagged it; no config change) |
| 1 leftovers | `5f42968` | |
| 2 models/migrations | `f910470`, `655964c` | fix: CHECK names were doubled (op.f); exact-name test |
| 3 FileStore | `e16b547`, `ffb9dc1` | fix: cancellation-safe put |
| 4 passwords/HIBP | `756a003` | |
| 5 sessions/rate limit/CSRF | `e415016`, `65b614d` | fix: error table codified in errors.py; framework 404 message `Not found.` |
| 6 auth routes | `d9ad746`, `683aff0` | test hardening (age month term, matrix, NFKC, dummy verify) |
| 7 study sets/cards | `af19f8e` | |
| 8 job queue/worker | `f9dfc48`, `13bc840` | fix: failing on_failed no longer loops; lease-lost rollback pinned |
| 9 upload | `e0c5359`, `bd1c86d` | fix: file kept after commit; filename Cf/control chars; NUL rejected in title/description/front/back |
| 10 extract_pdf | `d7c6ca2`, `db541fd` | fix: NUL stripped from extracted text |
| 11 web foundation | `eeeed18`, `d1504c9` | fix: safeNext tab/newline bypass; failed session check = signed out; class-based `dark` variant |
| 12 login/register/account | `59b4b06`, `1b02676` | test hardening |
| 13 sets/detail/review | `c978f67` | |
| 14 upload + polling | `a04be21` | implemented, 98 vitest; review pending |

Counts at `a04be21`: 233 pytest, 98 vitest (`make check` green, gitleaks clean). CI NOT yet checked on this branch (Task 15 step 2; zero-step billing failures mean stop and tell the owner).

**Owner decisions to surface in the PR body (not changed by the implementer):**
1. `DELETE /auth/account` has no rate limit on password attempts (as the plan specifies): a stolen session could brute-force the password and burn argon2 CPU. Recommend a per-user failure limit.
2. FastAPI parses multipart before dependencies, so an unauthenticated caller can make the server spool up to ~20 MiB + 64 KiB to temp disk per request (gets 413, not 401). Bounded by `BodySizeLimitMiddleware`. Options: cookie-presence precheck in the middleware, or a reverse-proxy limit at deployment.
3. If `on_failed` fails persistently, a document can stay `processing` (mildly conflicts with design 7.6; strictly better than the endless loop it replaced).

**Deviations for the PR body:** CSRF matrix and ownership meta-test enumerate routes via a shared `walk_routes` (FastAPI 0.162 hides included routers from `app.routes`); unknown-email logins also count toward the per-email limiter (consistent with design 7.8); birth_year range check lives in the route (needs the clock); NUL rejection added to study-set/card schemas and upload title; upload `title` Form validated by hand (strip, 1-120); pre-commit gets no PDF exclude (`.gitattributes` has `*.pdf binary`); `@custom-variant dark (&:is(.dark *))` added to `index.css` (no `.dark` block); `tsconfig.app.json` has `types: ["node"]` globally (needed by `tokens.test.ts`); `DocumentStatus` prop is `document` and SetDetailPage passes `key={document.id}`; the plan's Task 6 sentinel-password edit (above); Task 6 implementation was written before its tests (a test-hardening follow-up with mutation checks was added).

**Deferred minors (final whole-branch review should triage):** see `progress.md`. Highlights: Task 13 review flip control lacks Enter activation/accessible name and modifier-key guard; a failed card delete does not reload; several web test gaps (set-edit PATCH body, refresh-after-mutation, load-error states); idle-expiry/rate-limit float window math; a duplicate `local json()` helper across web tests; no `pypdfium2` upper bound; no cap on extracted text size; free-text NUL handling in auth email/password not checked.

**Where to resume:** see `handoff-prompts/implementer-phase-2a-resume-1.md`.

## 3. Repository state

- **Path:** `~/code/feynman-flashcard`. **Branch:** `main` at `3185eb1` (squash merge of PR #1), pushed. `phase-1-foundation` still exists on `origin` (history of the per-task commits).
- **PR #1:** https://github.com/ryanalmasi/feynman-flashcard/pull/1 — **merged** 2026-11-09. CI green (run 42547339617); post-merge CI on `main` (run 42548513765) also green.
- **Uncommitted on `main` (orchestrator session 3; commit only when the owner asks, or let the 2a implementer's Task 0 commit them on the 2a branch as in Phase 1):**
  - modified: `memory.md`, `CLAUDE.md` (status banner, handoff number), `docs/planning-handoff.md` (§0/§1/§5), `docs/adr/README.md`
  - new: `docs/adr/0012`–`0018`, `docs/superpowers/specs/2026-11-09-phase-2a-foundations-design.md`, `handoff-prompts/orchestrator-handoff-3.md`
- `.env` files exist locally only and are gitignored. The local dev DB was reset during the fix-up round (`make db-reset && make migrate`).
- **Machine:** all prerequisites in `docs/setup-prerequisites.md` are installed and verified. The stale `/mnt/c/...` copy should still be renamed or deleted by the owner.

## 4. Open questions and next steps

1. **Next orchestrator session (#4, `handoff-prompts/orchestrator-handoff-3.md`):** write the **Phase 2a implementation plan** from the approved design, in the Phase 1 plan format (Global Constraints, Review Focus, tasks with Files/Interfaces/failing tests/steps/commit), plus the implementer kickoff `handoff-prompts/implementer-phase-2a.md`. Owner approves the plan, then runs a Sonnet implementer on branch `phase-2a-foundations`.
2. The Phase 1 leftovers are already folded into the 2a design §7.9.
3. Phase 2 decision areas (2a done; 2b/2c open) (decisions listed in the plan's Phase 2 outline: LLM provider, embedding model, privacy/age policy, scoring parameters, UI styling, job queue, file storage, MVP scope).

**Caveats**
- Library versions are not pinned in the plan by design; the lockfiles (`api/uv.lock`, `web/package-lock.json`) record what was installed.
- Third-party prices in `docs/planning-handoff.md` §3-4 are still unverified (see session 1).
- Postgres 18's volume layout (mount `/var/lib/postgresql`) was verified working in Task 2.

## 5. Handoff automation (set up in session 1)

- **Skill `/handoff`** (`.claude/skills/handoff/SKILL.md`): update `memory.md` → update docs → write `handoff-prompts/orchestrator-handoff-N.md` **last** → tell the owner to start a new session.
- **Hook** (`.claude/settings.json` → `.claude/hooks/handoff-check.py`) on `UserPromptSubmit` and `PostToolUse`: a heads-up at ≥ 250k tokens, run the handoff at ≥ 300k, and a reminder when the owner's prompt mentions a handoff. Thresholds: `HANDOFF_WARN_TOKENS` / `HANDOFF_URGENT_TOKENS`.
- Claude Code keys sessions and private memory by folder path. After the move to `~/code`, the hook config loads from the new folder's `.claude/` automatically.
