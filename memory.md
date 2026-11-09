# memory.md: running project context

> **Purpose:** the repo's own record of what has happened so far, so a fresh agent session can pick up without the old conversation.
> **Rule:** update this file **first** during any handoff. The handoff prompt (`handoff-prompts/orchestrator-handoff-N.md`) is written **last**, after this file and the docs are current. See "Handoffs" in `CLAUDE.md`.
> **Not the same as** Claude Code's private auto-memory (`~/.claude/projects/.../memory/MEMORY.md`). That one is outside the repo. This file is versioned with the project and is the source of truth for project state.

**Last updated:** 2026-11-09 (Phase 1 implementation run complete; pending orchestrator review and owner merge)
**Latest handoff written:** #2 (`handoff-prompts/orchestrator-handoff-2.md`), plus the implementer kickoff `handoff-prompts/implementer-phase-1.md`

---

## 1. Project snapshot

- **What it is:** a study tool built around the Feynman technique: the student teaches a topic to an AI, gets a multi-stage score and feedback, and reviews AI-generated flashcards built from their PDF or topic.
- **What exists in code today:** the Phase 1 foundation on branch `phase-1-foundation`: FastAPI app with `GET /health`, Postgres 18 in Docker with migrator/app roles, migration `0001_users` (`users`, `auth_identities`), LLM/embedder interfaces with fakes and contract tests, a Vite React TS status page with a generated typed API client, `make` targets, pre-commit + gitleaks, and a GitHub Actions workflow (unverified, see the session log). No product features yet. `CLAUDE.md` and `README.md` describe this structure; the Jan-2025 prototype is in git history at `5aba556`.
- **Current phase:** **Phase 1 implemented, awaiting orchestrator review of the draft PR and the owner's merge.** Then Phase 2 planning. Phase order: 1. refactor/restructure → 2. MVP → 3. improvements (`docs/planning-handoff.md` §0).
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
- **CI is NOT verified.** The workflow ran twice (run ids 42543755654 and 42543763849; https://github.com/ryanalmasi/feynman-flashcard/actions/runs/42543763849) and all three jobs failed with zero steps executed: "The job was not started because your account is locked due to a billing issue." The workflow was only statically reviewed. Assumptions untested on a real runner: the gitleaks tarball install, the Postgres service container, and the roles script over TCP. **The owner must resolve the GitHub billing issue, then re-run CI** (`gh run rerun <id>` or push a commit).
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
- CI action pins: `actions/checkout@v7`, `actions/setup-node@v7`, `astral-sh/setup-uv@v10.3.3` (no floating `v10` tag exists; fixed in `3abaff5`).
- `users.email` is `String` (unbounded VARCHAR) where spec §7.2 says text; the DB dependencies are named `get_session`/`get_engine` rather than the spec's `get_db`.
- TypeScript `strict` was missing after the `~5.9` pin and was restored (tsconfig.app/node) in a final-review fix.
- The CI Postgres service healthcheck was aligned with compose (`pg_isready -h 127.0.0.1 -U postgres`) in a final-review fix.
- `docs/planning-handoff.md` §1: only the "Old code" row was touched (adds the `5aba556` pointer).

**Incomplete**
- CI green status (billing lock, above).
- The draft PR is opened by the controller after the final whole-branch review.

**Open items for the orchestrator/owner**
- `.gitleaks.toml` currently exempts all `*.env.example` files from scanning; the final reviewer recommends allowlisting the `change-me` placeholder value instead (security-posture change; owner decides).
- Hardening `REVOKE CONNECT, TEMPORARY ON DATABASE postgres FROM PUBLIC` is an open owner decision.
- The health-timeout branch is not pinned by a test (monkeypatch `_probe` to sleep longer than the timeout).
- `scripts/dev-env.sh` should warn when `infra/.env` is newly created but `api/.env` already exists.
- CI actions are pinned by tag, not SHA.
- The 500-without-CORS-headers fix is planned for Phase 2 M1.
- Declare `python-dotenv` in the api dev group for hygiene.
- Add a try/finally to `test_migrations` and an explicit inspector assertion on `uq_users_email_lower`.
- `push: phase-*` plus `pull_request` double-runs CI.

**Deferred minors (for the orchestrator to triage)**
- T2: `make db` grep errors if `infra/.env` is missing (harmless); `db-psql` relies on socket trust; `api/.env.example` CORS_ORIGINS is unquoted JSON (fine for pydantic).
- T3: `logging.basicConfig` is a no-op if the root logger has handlers (consider `force=True`); 500s from `ServerErrorMiddleware` carry no CORS headers (Starlette limitation); `conftest` imports python-dotenv, which is only a transitive dependency; the CSRF header must be added to `allow_headers` in Phase 2.
- T4: `test_migrations` assumes serial DB use and has no `finally` on the last upgrade; dead logging sections in `alembic.ini`; `type: ignore` on `orig.__cause__` is brittle; `compare_metadata` may not fully cover the functional index `lower(email)` (unverified).
- T5: the db-down test doesn't prove the 2s bound (port 1 refuses instantly); duplicated unreachable `Settings` in tests; `version()` is looked up per request.
- T6: error-propagation test uses `pytest.raises(type(err))` (accepts subclasses); no tests for structured-payload cycling or the no-structured error path; `StructuredResult.value: T` may warn on dump.
- T7: stray blank line in `index.html`; no unmount test; `typescript ~5.9` in package.json (lockfile pins exact).
- T8: `push: phase-*` plus `pull_request` double-runs for a PR from a `phase-*` branch (per brief); redundant `uv python install`; implicit `npm ci` dependency for `gen-types` in the web job.

## 3. Repository state

- **Path:** `~/code/feynman-flashcard`. **Branch:** `phase-1-foundation`, pushed to `origin`. `main` is unchanged at `e7bd5b9`.
- **Draft PR:** https://github.com/ryanalmasi/feynman-flashcard/pull/1 (draft; not merged; owner merges after orchestrator review)
- **Working tree:** clean after the Task 9 commit. `.superpowers/` (agent scratch) is gitignored. `.env` files exist locally only and are gitignored.
- **Machine:** all prerequisites in `docs/setup-prerequisites.md` are installed and verified. The stale `/mnt/c/...` copy should still be renamed or deleted by the owner.

## 4. Open questions and next steps

1. **Owner:** resolve the GitHub account billing lock, then re-run CI (`gh run rerun 42543763849`, or push a commit) and confirm all three jobs (api, web, secrets) go green. Until then CI is unverified.
2. **Orchestrator:** review the draft PR against `docs/implementation-plan.md`, the spec, and the ADRs; triage the deferred minors above; report to the owner.
3. **Owner:** merge the PR (only the owner merges).
4. **Then:** Phase 2 planning (decisions listed in the plan's Phase 2 outline: LLM provider, embedding model, privacy/age policy, scoring parameters, UI styling, job queue, file storage, MVP scope).

**Caveats**
- Library versions are not pinned in the plan by design; the lockfiles (`api/uv.lock`, `web/package-lock.json`) record what was installed.
- Third-party prices in `docs/planning-handoff.md` §3-4 are still unverified (see session 1).
- Postgres 18's volume layout (mount `/var/lib/postgresql`) was verified working in Task 2.

## 5. Handoff automation (set up in session 1)

- **Skill `/handoff`** (`.claude/skills/handoff/SKILL.md`): update `memory.md` → update docs → write `handoff-prompts/orchestrator-handoff-N.md` **last** → tell the owner to start a new session.
- **Hook** (`.claude/settings.json` → `.claude/hooks/handoff-check.py`) on `UserPromptSubmit` and `PostToolUse`: a heads-up at ≥ 250k tokens, run the handoff at ≥ 300k, and a reminder when the owner's prompt mentions a handoff. Thresholds: `HANDOFF_WARN_TOKENS` / `HANDOFF_URGENT_TOKENS`.
- Claude Code keys sessions and private memory by folder path. After the move to `~/code`, the hook config loads from the new folder's `.claude/` automatically.
