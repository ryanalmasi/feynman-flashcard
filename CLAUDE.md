# CLAUDE.md

Guidance for Claude Code sessions in this repository. It describes what the repo **currently is**, not what it is meant to become. The product vision is covered separately below so the two don't get mixed up.

> **Status (2026-11-10):** **Phase 1 and Phase 2a are merged to `main` (PRs #1 and #2, CI green).** 2a has accounts (register with a 13+ age screen, login/logout, account deletion), study sets and flashcards, a review screen, PDF upload, a Postgres job queue with a worker, and PDF text extraction, with a Tailwind + shadcn web UI. There is **no LLM use in code yet**. **Phase 2b (Knowledge Map + generated flashcards) is decided and designed:** ADRs 0019-0021 and `docs/superpowers/specs/2026-11-10-phase-2b-ai-content-design.md` (approved, not yet committed); its plan (`docs/implementation-plan-phase-2b.md`) and implementer prompt are **approved by the owner (2026-11-11)**; the implementer run is next. Phase 2 is split into 2a/2b/2c (ADR 0012). Read `memory.md` next.
>
> The Jan-2025 prototype is in git history at `5aba556`.

---

## Product vision (intended, mostly NOT implemented)

A study tool built around the **Feynman technique**: after studying, the student "teaches" the topic to someone else to find gaps in their understanding.

1. **Feynman tutor agent (the core product):** the student explains a topic to an AI agent, either by typing or in **voice mode**. The agent acts as the learner and asks follow-up questions.
2. **Scoring:** at the end of the session, the student's explanation is scored by semantic/topical similarity to the source material.
3. **Feedback:** the agent reviews the conversation and reports what was missing, wrong, or unclear, and what to work on.
4. **Auto-generated flashcards (supplementary):** agents parse an uploaded lesson PDF or a discussion topic and generate a full set of flashcards for review.


**What exists today toward that vision:** the 2a foundations in the status banner above (accounts, manually authored flashcards and review, PDF upload and text extraction). The tutor, scoring, feedback, and AI flashcard generation are still to be built (2b/2c and later).

---

## Tech stack

| Layer | Tech | ADR |
|---|---|---|
| Backend | FastAPI, Python 3.13, uv, Uvicorn, pydantic-settings | 0001, 0006 |
| Database | PostgreSQL 18 (Docker Compose), SQLAlchemy 2 async (asyncpg), Alembic; roles `feynman_migrator` (DDL) and `feynman_app` (DML only) | 0004 |
| Frontend | Vite, React 19, TypeScript (~5.9), React Router 8, openapi-fetch with generated types | 0002, 0009 |
| Styling | Tailwind CSS 4 + shadcn/ui (radix-ui, sonner, tw-animate-css); tokens only in `web/src/index.css` | 0014 |
| LLM layer | Own Protocols (`stream_chat`, `generate_structured`, `Embedder`) with `Usage` on every call; fakes only in code so far. **Decided for 2b, not built yet:** Anthropic adapter, Sonnet 5.5 for the map, Haiku 5.5 for cards, `temperature` removed from the Protocol | 0007, 0019 |
| Tooling | ruff, mypy strict, pytest (real Postgres), ESLint (flat config) + Prettier, Vitest, pre-commit, gitleaks, GitHub Actions | 0006, 0009 |
| Auth | **Built (2a):** own Postgres sessions (SHA-256-hashed tokens, HttpOnly cookie, per-session CSRF token + Origin check), argon2id, HIBP range check (fail-open), Postgres rate limits | 0005, 0013, 0017 |
| Jobs / files / PDF | **Built (2a):** own `jobs` table + worker (`FOR UPDATE SKIP LOCKED`, leases, backoff); local-disk `FileStore`; pypdfium2 (worker only) | 0015, 0016, 0018 |

Decisions live in `docs/adr/` (index: `docs/adr/README.md`). Do not edit an ADR without the owner.

---

## Repository map

```
feynman-flashcard/
├── CLAUDE.md / memory.md / README.md / LICENSE
├── Makefile                      Developer entry points (see Commands)
├── docs/
│   ├── adr/                      ADRs 0001-0021 + README index
│   ├── superpowers/specs/        Phase 1, 2a and 2b design specs
│   ├── implementation-plan.md    Phase 1 plan (Tasks 0-9) + Phase 2 outline (NOT FOR EXECUTION)
│   ├── implementation-plan-phase-2a.md   Phase 2a plan (Tasks 0-15)
│   ├── implementation-plan-phase-2b.md   Phase 2b plan (Tasks 0-16; approved)
│   ├── planning-handoff.md       Roadmap (§0), decisions (§1), scoring design (§2), research, costs, open decisions (§5)
│   └── setup-prerequisites.md    Machine setup (WSL, Docker, uv, Node, gh, gitleaks)
├── handoff-prompts/
│   ├── orchestrator/             Numbered orchestrator handoffs (latest: #6)
│   └── implementer/
│       ├── phase-plan/           Implementer kickoffs per phase (+ resume prompts for a phase run)
│       └── fixup/                Implementer kickoffs for fix-up rounds after a PR review
├── .claude/                      settings.json (handoff hooks), hooks/handoff-check.py, skills/handoff/SKILL.md
├── .github/workflows/ci.yml      Jobs: api, web, secrets
├── .gitignore / .gitattributes / .gitleaks.toml / .pre-commit-config.yaml
├── scripts/dev-env.sh            `make env`: generates gitignored .env files with random dev passwords
├── infra/                        docker-compose.yml (Postgres 18) + postgres/init/01-roles.sh
├── api/                          FastAPI project (uv)
│   ├── pyproject.toml / uv.lock / .env.example
│   ├── alembic/versions/         0001_users, 0002_auth_sessions_rate_limits, 0003_study_content, 0004_jobs
│   ├── src/feynman_api/
│   │   ├── main.py               `create_app()` factory (lifespan, CORS, body-size limit, error handlers)
│   │   ├── config.py / db.py / clock.py / errors.py   Settings; async engine/session; injectable clock; JSON error shape, `AppError` factories
│   │   ├── upload_limit.py       Pure-ASGI body-size cap for `/documents`
│   │   ├── storage.py            `FileStore` protocol + local-disk store (UUID keys, cancellation-safe put)
│   │   ├── worker.py             Entry point for `make worker`
│   │   ├── auth/                 passwords (argon2id), breach (HIBP), sessions, rate_limit, csrf (+Origin check), dependencies (`current_user`), ownership (owner-scoped lookups), schemas
│   │   ├── jobs/                 queue (enqueue/claim/lease/retry), registry, worker loop, handlers/extract_pdf.py
│   │   ├── models/               Base, User, AuthIdentity, AuthSession, RateLimitBucket, StudySet, Flashcard, Document, DocumentPage, Job
│   │   ├── routes/               health, auth, study_sets, flashcards, documents, schemas
│   │   └── llm/                  `base.py` (Protocols, types), `errors.py`, `fake.py` (fakes)
│   └── tests/                    pytest on real Postgres; `llm/` holds the provider contract tests
└── web/                          Vite React TS app (npm); Tailwind 4 + shadcn/ui
    └── src/
        ├── main.tsx / App.tsx    Routes: /login, /register, /status, /sets, /sets/:setId, /sets/:setId/review, /account (guarded by RequireAuth), 404
        ├── api/client.ts         Single openapi-fetch client (`VITE_API_BASE_URL`), CSRF header middleware, 401 handling
        ├── api/schema.gen.ts     Generated types, committed and drift-checked (do not hand-edit; `make gen-types`)
        ├── auth/                 AuthProvider, useAuth, safeNext (redirect sanitising)
        ├── components/           AppShell, RequireAuth, dialogs, UploadPdfButton, DocumentStatus (polling); `ui/` = shadcn components (ours to edit)
        ├── pages/                Login, Register, Sets, SetDetail, Review, Account, Status, NotFound (+ tests)
        ├── index.css             Tailwind import and ALL design tokens (no hard-coded colors elsewhere)
        └── assets/images/        The 7 images kept from the prototype
```

---

## Data model (`api/alembic/versions/`, `api/src/feynman_api/models/`)

```
users                id UUID PK; email (unique on lower(email)); password_hash NULLABLE;
                     email_verified_at; age_verified_at (set at registration; birth date is never stored); created_at/updated_at
auth_identities      user_id FK CASCADE; provider + provider_subject unique together (unused until social login)
auth_sessions        id; user_id FK CASCADE; token_hash bytea UNIQUE (SHA-256 of the cookie token); csrf_token;
                     created_at, last_seen_at, expires_at (7-day idle / 30-day max)
rate_limit_buckets   (key, window_start) PK; count   (login/register limits, pruned on use)
study_sets           id; user_id FK CASCADE; title (1-120); description (<=1000, nullable); timestamps
flashcards           id; study_set_id FK CASCADE; front (1-500); back (1-2000); origin 'manual'|'generated'; timestamps
documents            id; study_set_id FK CASCADE, UNIQUE (one PDF per set); storage_key UNIQUE; original_filename; size_bytes;
                     page_count; status 'processing'|'ready'|'failed'; error_message; timestamps
document_pages       (document_id FK CASCADE, page_number) PK; text
jobs                 id; user_id FK CASCADE; kind; payload JSONB; status 'queued'|'running'|'succeeded'|'failed';
                     attempts/max_attempts (3); run_after; locked_until (lease); last_error; result JSONB; timestamps
```

Constraint names follow an explicit naming convention (check constraints are named, with exact-name tests). The app role has DML only; stored files live under `UPLOAD_DIR` (default `var/uploads`) and are deleted with their set or account.

---

## HTTP API

All errors share one JSON shape: `{"error": {"code": str, "message": str, "details": [...] | null}}`. Codes: `not_authenticated` (401), `invalid_credentials` (401), `csrf_failed` (403), `registration_not_allowed` (403, under-13 or bad birth data), `not_found` (404; also used for other users' resources), `method_not_allowed` (405), `email_taken` (409), `file_too_large` (413), `unsupported_file_type` (415), `validation_error` (422, `details` = `[{loc, msg}]`), `password_breached` (422, register only), `rate_limited` (429, with `Retry-After`), `http_error`, `internal_error` (500; carries CORS headers).

All routes except `/health`, `/auth/register` and `/auth/login` need the session cookie. State-changing requests also need the `X-CSRF-Token` header (value from the register/login/session response) and an allowed `Origin`.

| Method | Path | Behavior |
|---|---|---|
| GET | `/health` | `200 {status:"ok", db:"ok", version}`; `503 {status:"degraded", ...}` when the DB probe fails or exceeds `HEALTH_DB_TIMEOUT_SECONDS` |
| POST | `/auth/register` | 201 `{user, csrf_token}` + session cookie; body has email, password (12+ chars), birth_month, birth_year (13+ check, never stored); 403/409/422/429 |
| POST | `/auth/login` | 200 `{user, csrf_token}`; 401 `invalid_credentials`, 429 (per-email lockout and per-IP limit). No breach check on login |
| POST | `/auth/logout` | 204, clears the session |
| GET | `/auth/session` | 200 `{user, csrf_token}` or 401 |
| DELETE | `/auth/account` | 204; body `{password}`; deletes the user, sets, cards, documents, jobs, sessions and files. Wrong password: 401 `invalid_credentials`; after 5 failures in 15 min (per user): 429 `rate_limited` + `Retry-After`, checked before the password |
| GET / POST | `/study-sets` | List own sets (with card count and document summary) / create (201) |
| GET / PATCH / DELETE | `/study-sets/{set_id}` | Owner-scoped; DELETE is 204 and removes the stored PDF |
| GET / POST | `/study-sets/{set_id}/flashcards` | List / create a card (201) |
| PATCH / DELETE | `/flashcards/{card_id}` | Edit / delete (204) |
| POST | `/documents` | Multipart `file` (+ optional `title`); creates a NEW study set holding the PDF and returns 202 `{study_set, document}`; PDF magic check, 20 MB streaming cap; enqueues `extract_pdf`. One PDF per set |
| GET | `/documents/{document_id}` | Status (`processing`/`ready`/`failed`, `page_count`, `error_message`) |

Content fields reject NUL characters. The web app talks to all of this through the generated client; `http://localhost:5173` redirects to `/sets` or `/login`.

---

## Commands

Prerequisites: `docs/setup-prerequisites.md` (Docker Engine in WSL, uv, Node 26, make, gh, gitleaks, pre-commit).

```bash
make env                        # once: generate infra/.env, api/.env, web/.env (never overwrites)
make db                         # start Postgres 18 and verify the app-role login
make migrate                    # alembic upgrade head (as feynman_migrator)
(cd api && uv sync)             # Python deps
(cd web && npm ci)              # JS deps
make api                        # uvicorn --reload on http://127.0.0.1:8000 (http://localhost:8000/health)
make worker                     # background worker (PDF extraction); uploads stay 'processing' without it
make web                        # Vite dev server on http://localhost:5173
make test | lint | check        # check = lint + test + web build + types drift check
make gen-types                  # regenerate web/openapi.json and web/src/api/schema.gen.ts
make db-down                    # stop Postgres (data kept)
make db-reset                   # DELETES the local DB volume and re-creates it
make db-psql                    # psql as feynman_migrator
```

Local results at the end of Phase 2a (after the fix-up, `5d0e027`): **238 pytest and 99 vitest tests pass; `make check` passes; gitleaks clean.** CI on the 2a branch: green (run 42581239361 at `cd2883b`).

### Gotchas
- **The worker must be running** (`make worker`) or uploaded PDFs stay `processing` until the UI's 10-minute polling gives up. It processes one job at a time with a lease (`JOB_LEASE_SECONDS`); handlers must be idempotent on reclaim.
- **`SESSION_COOKIE_SECURE=false`** is required for plain-http local dev (`make env` writes it; the code default is `true`). Never ship it as `false`.
- **Tests that commit** (those using the app/HTTP client or real commits) must use the `clean_db` fixture (it truncates all tables); the `db` fixture builds on it. Rate-limit and clock behaviour use the injectable `clock` fixture.
- **shadcn components** in `web/src/components/ui/` are copied code that we own and may edit. **Design tokens live only in `web/src/index.css`**; screens use semantic token classes, never raw colors. Dark mode is class-based (`@custom-variant dark`), with no `.dark` block yet.
- **FastAPI 0.162 hides included routers from `app.routes`**; route-walking tests (CSRF matrix, ownership meta-test) use the shared `walk_routes` helper over `app.openapi()`.
- **DB tests need Postgres running** (`make db`, and `make migrate` is not required for tests; they migrate `feynman_test` themselves). If the DB is unreachable or the volume was created with other credentials, the conftest prints a hint to run `make db` / `make db-reset`.
- `make env` creates the gitignored `.env` files. Never commit a `.env`; only `*.env.example` is tracked. If `infra/.env` is created after the DB volume exists, run `make db-reset`.
- Compose project name is `infra` (derived from the folder holding the compose file), so the volume is `infra_feynman_pgdata`.
- Inside the Postgres container, loopback (`127.0.0.1`/socket) is **trust-auth**; it proves nothing about passwords. Credential probes must use `-h db` (the Makefile does).
- Use `localhost`, not `127.0.0.1`, for browser-facing URLs (CORS origin is `http://localhost:5173`). Unhandled-exception 500s used to lack CORS headers (Starlette's `ServerErrorMiddleware` sits outside `CORSMiddleware`); fixed in 2a (`5f42968`), so the browser now sees the JSON body.
- Postgres 18 images keep data under `/var/lib/postgresql/18/docker`; the volume mounts the parent `/var/lib/postgresql`.
- TypeScript is pinned `~5.9` because `openapi-typescript` peers on it. `npm audit` reports 10 moderate dev-only advisories (minimatch via eslint); the only fix forces an ESLint downgrade and was not applied.
- `.superpowers/` is gitignored agent scratch space: never commit or link to it.
- CI (`.github/workflows/ci.yml`) has jobs api, web, secrets, with actions pinned by SHA. The secrets job downloads gitleaks with an **authenticated** `gh release download` (workflow token, 3 retries) plus a sha256 check. Anonymous `curl` downloads were throttled (504) during a GitHub incident. If a run fails with zero steps, it's an account/billing problem, not the code.

---

## Conventions

- **Git:** work on the phase branch (`phase-1-foundation`, `phase-2a-foundations`, ...); one commit per task, Conventional Commits, authored as `ryanalmasii <ryanalmasii@gmail.com>` via `git -c user.name=... -c user.email=... commit`, pushed after each task; a draft PR at the end. Never push to or merge into `main`, never force-push or tag; the **owner is the only one who merges**. Commit only when asked.
- **Secrets:** nothing secret in git. Config comes from env via pydantic-settings; only `.env.example` files are tracked; gitleaks runs in pre-commit and CI (run `gitleaks git --redact -v .` before pushing).
- **Quality gates:** ruff (check + format) and mypy strict for the API; ESLint + Prettier + `tsc` for the web; `make check` before every push. Tests run against real Postgres, not mocks. Write tests first (TDD).
- **API:** every error uses the shared JSON error shape; web code calls the API only through `web/src/api/client.ts` with generated types, and the committed `schema.gen.ts` must match `make gen-types`.
- **LLM code:** go through the Protocols in `llm/base.py`; every call returns `Usage`; new adapters must pass the contract tests in `api/tests/llm/`.
- **DB:** the app runs as `feynman_app` (no DDL); only Alembic runs as `feynman_migrator`. Schema changes are migrations.
- **Decisions:** explain first, owner approves (see "Decision process" below). No silent architectural choices or unplanned dependencies.

---

## Notes for future sessions

- Phase 1 and 2a are merged; 2b is decided (ADRs 0019-0021: Anthropic, Knowledge Map, generated cards) and its design approved. Next: the 2b plan and implementer prompt, the implementer run, the PR review, then the 2c decision round (tutor, scoring, feedback, usage logging). Known deferred review items are listed in `memory.md`.
- **Start with [`docs/planning-handoff.md`](docs/planning-handoff.md).** It holds the detailed multi-stage scoring design, the provider, voice, embedding, and Postgres research with pricing, per-session cost estimates, and the list of open decisions for the owner.

### Phase order (decided)
1. **Refactor and restructure the architecture.** 2. **Build an MVP of the backend and app.** 3. **Then improvements.** The scope and exit criteria for each phase are in `docs/planning-handoff.md` §0. Don't start Phase 3 features (voice, billing, calibration, and so on) before the MVP exists.

### Handoffs and memory.md (owner's rule)
`memory.md` (repo root) is the project's running record of context and completed work. It is **versioned with the repo** and is separate from Claude Code's private auto-memory. Every new session reads it right after this file.

**Every time the owner asks for a handoff, do these steps in this order. The handoff prompt is always the LAST step.**
1. **Update `memory.md` first:** bump the dates and handoff number, add a Session log entry (what was completed, what the owner decided, what is still open), refresh the repo state (git status, files added or changed, anything uncommitted) and the next steps and caveats. Be factual about anything incomplete or failed.
2. **Update the other docs that are now stale:** `docs/planning-handoff.md` §1/§5, the ADRs and `docs/implementation-plan.md` if they exist, and this file if the structure, commands, or rules changed.
3. **Write the handoff prompt last:** a new file `handoff-prompts/orchestrator/orchestrator-handoff-N.md`, where N is the highest existing number + 1. Never overwrite earlier handoffs. It is a self-contained prompt for the next agent session and should include:
   - which files to read first, in order (`CLAUDE.md`, `memory.md`, then the planning doc, ADRs, the implementation plan, and so on)
   - what has been decided and built since the previous handoff, and what is still open
   - where things stand against the phase plan, and exactly what the next session should do
   - the owner's rules (explain decisions first, the owner has final say, commit only when asked)
4. Tell the owner the path of the new file, and stop. Don't start new work after the handoff is written.

**This is automated.** The project skill `/handoff` (`.claude/skills/handoff/SKILL.md`) holds this procedure and also matches automatically when the owner says it's time to hand off or start a new agent session. A hook (`.claude/hooks/handoff-check.py`, registered in `.claude/settings.json` on `UserPromptSubmit` and `PostToolUse`) injects reminders:
- at about **250k tokens (~25% of a 1M context window)**: a heads-up. Offer the handoff to the owner, and don't start it unless they agree.
- at about **300k tokens (~30%)**: run the `handoff` skill at the next natural stopping point (not mid-edit), then tell the owner to start a new session.
- whenever the owner's prompt mentions a handoff or a new agent session: if they're asking for one, run the skill.

If you see a `[handoff-hook]` note in your context, follow it as described here. Token counts are an estimate taken from the last assistant turn's usage record. The thresholds can be changed with the `HANDOFF_WARN_TOKENS` and `HANDOFF_URGENT_TOKENS` environment variables.

### Implementer sessions start cold (owner's rule)
**Every phase, and every fix-up round, runs in a brand-new implementer session** that has none of the orchestrator's context. Its plan and kickoff prompt must therefore carry everything it needs to catch up:
- **The kickoff prompt** (`handoff-prompts/implementer/phase-plan/implementer-phase-*.md` for a phase, `handoff-prompts/implementer/fixup/implementer-phase-*-fixups.md` for a fix-up round) opens with a numbered **"Read these first, in order"** list:
  - `CLAUDE.md`
  - the relevant `memory.md` entries, **named**
  - the plan
  - the design
  - the ADRs the phase depends on, **by number**
  - earlier phases' plans only for the constraints they carry over
  It also has a **preflight**: the branch to check out, the expected `git status`, and the `make check` baseline with its expected test counts.
- **The plan** (`docs/implementation-plan-phase-*.md`) has a **"Context for a fresh implementer"** section before Task 0. It lists the **existing code** the phase builds on, as file paths with the names to reuse: fixtures, helpers, dependencies, protocols, and patterns to copy. It also says what each one is for. A task's **Interfaces → Consumes** block names the exact earlier-phase symbols it uses (module path + name), so a per-task subagent seeing only its own task can find them.
- If a previous phase's run left resume prompts or deferred items that matter, the kickoff points to them by path.

### Decision process (owner's rule)
**Every design decision must be explained before implementation, and the owner has the final say.** For each choice (stack, provider, schema, auth, hosting), present the options, the trade-offs, and a recommendation with reasoning. Then wait for approval before writing code that depends on it. Don't make silent architectural choices.

### Direction agreed so far
Infrastructure decisions are now recorded as ADRs in `docs/adr/` (stack, database, auth, config, LLM layer, jobs, tooling, git); those supersede the earlier leanings below. Scoring and product direction remain proposals in `docs/planning-handoff.md`.
- **Stack:** decided in ADRs 0001-0003: FastAPI (Python 3.13) + Vite React TS, layout `api/ web/ infra/ docs/`.
- **Database:** decided in ADR 0004: PostgreSQL 18 with least-privilege migrator/app roles, secrets in env vars. Redis is not used (sessions will live in Postgres, ADR 0005). Add `pgvector` only if embeddings are stored.
- **Scoring is multi-stage:**
  1. **Baseline score:** a cheap, deterministic, objective measure of how closely the explanation matches the source material (e.g. embedding similarity or key-concept coverage).
  2. **AI-graded score(s):** an LLM judges the explanation against the source on things like accuracy, completeness, clarity, and misconceptions.
  3. **Final result:** combine both, so the AI's subjective judgement is anchored to the objective baseline. Then generate actionable feedback from the conversation.
  - The full proposal is in `docs/planning-handoff.md` §2: a Knowledge Map, claim extraction, a baseline, an evidence-quoted rubric judge, asymmetric-band reconciliation, and calibration. It is a proposal awaiting owner approval (scoring parameters are Phase 2 decisions).
- **"Illumina"** was just the name of the old MySQL database. It is not a product, dependency, or external system and can be dropped.

### Research status
The first round of research on the LLM provider, voice, embeddings, and Postgres hosting is done (2026-11-08); see `docs/planning-handoff.md` §3–4. A draft pricing model (free trial, Plus and Pro tiers, margins) is in §4b. **The owner has not decided on any of it yet.** The handoff doc recommends choosing the LLM through a gold-set bake-off rather than on price, because cheap-tier models cost about $0.01–0.02 per session.
