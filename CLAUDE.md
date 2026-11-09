# CLAUDE.md

Guidance for Claude Code sessions in this repository. It describes what the repo **currently is**, not what it is meant to become. The product vision is covered separately below so the two don't get mixed up.

> **Status (2026-11-09):** **Phase 1 (architecture foundation) is complete on branch `phase-1-foundation`, pending the owner's review and merge.** It is a skeleton only: a FastAPI app with `GET /health`, a Postgres schema (`users`, `auth_identities`), a Vite React TS status page, the LLM/embedder interfaces with fakes, and tooling/CI. There are **no product features yet** (no auth endpoints, flashcards, PDF upload, or scoring). Phase 2 (MVP) has not been planned in detail; see the outline at the end of `docs/implementation-plan.md` (marked NOT FOR EXECUTION). Read `memory.md` next. CI has been written but is **unverified** (see `memory.md`).
>
> The Jan-2025 prototype is in git history at `5aba556`.

---

## Product vision (intended, mostly NOT implemented)

A study tool built around the **Feynman technique**: after studying, the student "teaches" the topic to someone else to find gaps in their understanding.

1. **Feynman tutor agent (the core product):** the student explains a topic to an AI agent, either by typing or in **voice mode**. The agent acts as the learner and asks follow-up questions.
2. **Scoring:** at the end of the session, the student's explanation is scored by semantic/topical similarity to the source material.
3. **Feedback:** the agent reviews the conversation and reports what was missing, wrong, or unclear, and what to work on.
4. **Auto-generated flashcards (supplementary):** agents parse an uploaded lesson PDF or a discussion topic and generate a full set of flashcards for review.


**What exists today toward that vision:** only the Phase 1 skeleton described in the status banner above. The tutor, scoring, feedback, and flashcard generation are all still to be built (Phase 2 and later).

---

## Tech stack

| Layer | Tech | ADR |
|---|---|---|
| Backend | FastAPI, Python 3.13, uv, Uvicorn, pydantic-settings | 0001, 0006 |
| Database | PostgreSQL 18 (Docker Compose), SQLAlchemy 2 async (asyncpg), Alembic; roles `feynman_migrator` (DDL) and `feynman_app` (DML only) | 0004 |
| Frontend | Vite, React 19, TypeScript (~5.9), React Router 8, openapi-fetch with generated types | 0002, 0009 |
| LLM layer | Own Protocols (`stream_chat`, `generate_structured`, `Embedder`) with `Usage` on every call; fakes only, no real provider yet | 0007 |
| Tooling | ruff, mypy strict, pytest (real Postgres), ESLint (flat config) + Prettier, Vitest, pre-commit, gitleaks, GitHub Actions | 0006, 0009 |
| Auth / jobs | Decided but **not built** (own Postgres sessions; Postgres-backed job queue) | 0005, 0008 |

Decisions live in `docs/adr/` (index: `docs/adr/README.md`). Do not edit an ADR without the owner.

---

## Repository map

```
feynman-flashcard/
├── CLAUDE.md / memory.md / README.md / LICENSE
├── Makefile                      Developer entry points (see Commands)
├── docs/
│   ├── adr/                      ADRs 0001-0011 + README index
│   ├── superpowers/specs/        Phase 1 design spec
│   ├── implementation-plan.md    Phase 1 plan (Tasks 0-9) + Phase 2 outline (NOT FOR EXECUTION)
│   ├── planning-handoff.md       Roadmap (§0), decisions (§1), scoring design (§2), research, costs, open decisions (§5)
│   └── setup-prerequisites.md    Machine setup (WSL, Docker, uv, Node, gh, gitleaks)
├── handoff-prompts/              Numbered orchestrator handoffs + implementer-phase-1.md
├── .claude/                      settings.json (handoff hooks), hooks/handoff-check.py, skills/handoff/SKILL.md
├── .github/workflows/ci.yml      Jobs: api, web, secrets
├── .gitignore / .gitattributes   Ignore rules (.env, .superpowers/, generated files); line-ending rules
├── .gitleaks.toml                gitleaks config (allowlist)
├── .pre-commit-config.yaml       Hooks: check-added-large-files, check-merge-conflict, end-of-file-fixer, trailing-whitespace, detect-private-key, check-yaml, ruff, ruff-format, gitleaks
├── scripts/dev-env.sh            `make env`: generates gitignored .env files with random dev passwords
├── infra/
│   ├── docker-compose.yml        Postgres 18 (127.0.0.1:5432), volume `feynman_pgdata`
│   └── postgres/init/            01-roles.sh creates the migrator/app roles and databases
├── api/                          FastAPI project (uv)
│   ├── pyproject.toml / uv.lock / .env.example
│   ├── alembic/ + alembic.ini    Migrations; `versions/0001_users.py`
│   ├── src/feynman_api/
│   │   ├── main.py               `create_app()` factory (lifespan, CORS, error handlers)
│   │   ├── config.py             `Settings`, `MigrationSettings` (pydantic-settings)
│   │   ├── db.py                 Async engine/session helpers, `get_engine`
│   │   ├── errors.py             JSON error shape + handlers
│   │   ├── openapi_dump.py       Dumps the OpenAPI schema for type generation
│   │   ├── models/               SQLAlchemy `Base`, `User`, `AuthIdentity`
│   │   ├── routes/health.py      `GET /health`
│   │   └── llm/                  `base.py` (Protocols, types), `errors.py`, `fake.py` (fakes)
│   └── tests/                    pytest; `llm/` holds the provider contract tests
└── web/                          Vite React TS app (npm); `.env.example` (also `infra/.env.example`)
    ├── openapi.json              Generated by `make gen-types` (gitignored, not committed)
    └── src/
        ├── main.tsx / App.tsx    Router: `/` status page, 404 fallback
        ├── api/client.ts         Single configured openapi-fetch client (`VITE_API_BASE_URL`)
        ├── api/schema.gen.ts     Generated types, committed and drift-checked (do not hand-edit; `make gen-types`)
        ├── pages/                `StatusPage`, `NotFoundPage` (+ tests)
        └── assets/images/        The 7 images kept from the prototype
```

---

## Data model (`api/alembic/versions/0001_users.py`, `api/src/feynman_api/models/`)

```
users
  id                UUID PK
  email             String (unbounded VARCHAR; spec §7.2 said text), not null; unique on lower(email) (index uq_users_email_lower)
  password_hash     String, NULLABLE (so social-login users need no password)
  email_verified_at timestamptz, nullable
  created_at / updated_at   timestamptz, server default now()
      │ 1
      │ N   (ON DELETE CASCADE)
auth_identities
  id                UUID PK
  user_id           FK → users.id
  provider          String      ┐ unique together
  provider_subject  String      ┘ (uq_auth_identities_provider_subject)
  created_at        timestamptz
```

No date of birth (deferred until the privacy/age-policy decision, ADR 0005). Constraint names follow an explicit naming convention. Nothing else exists yet: no sessions table, no study sets, no flashcards.

---

## HTTP API

All errors share one JSON shape: `{"error": {"code": str, "message": str, "details": [...] | null}}` (codes: `not_found`, `method_not_allowed`, `http_error`, `validation_error` (422, `details` = `[{loc, msg}]`), `internal_error` (500)).

| Method | Path | Behavior |
|---|---|---|
| GET | `/health` | `200 {status:"ok", db:"ok", version}`; `503 {status:"degraded", db:"error", version}` when the DB probe fails or exceeds `HEALTH_DB_TIMEOUT_SECONDS` (default 2s) |

The web app calls it through the generated client and shows "API: ok / Database: ok" at `http://localhost:5173`.

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
make web                        # Vite dev server on http://localhost:5173
make test | lint | check        # check = lint + test + web build + types drift check
make gen-types                  # regenerate web/openapi.json and web/src/api/schema.gen.ts
make db-down                    # stop Postgres (data kept)
make db-reset                   # DELETES the local DB volume and re-creates it
make db-psql                    # psql as feynman_migrator
```

Local results at the end of Phase 1: 36 pytest tests and 7 vitest tests pass; `make check` passes.

### Gotchas
- **DB tests need Postgres running** (`make db`, and `make migrate` is not required for tests; they migrate `feynman_test` themselves). If the DB is unreachable or the volume was created with other credentials, the conftest prints a hint to run `make db` / `make db-reset`.
- `make env` creates the gitignored `.env` files. Never commit a `.env`; only `*.env.example` is tracked. If `infra/.env` is created after the DB volume exists, run `make db-reset`.
- Compose project name is `infra` (derived from the folder holding the compose file), so the volume is `infra_feynman_pgdata`.
- Inside the Postgres container, loopback (`127.0.0.1`/socket) is **trust-auth**; it proves nothing about passwords. Credential probes must use `-h db` (the Makefile does).
- Use `localhost`, not `127.0.0.1`, for browser-facing URLs (CORS origin is `http://localhost:5173`). **Every** unhandled-exception 500 (including the JSON one our own handler builds) lacks CORS headers, because Starlette's `ServerErrorMiddleware` sits outside `CORSMiddleware`; the browser reports an opaque network error rather than the JSON body. A fix is tracked for Phase 2 (M1).
- Postgres 18 images keep data under `/var/lib/postgresql/18/docker`; the volume mounts the parent `/var/lib/postgresql`.
- TypeScript is pinned `~5.9` because `openapi-typescript` peers on it. `npm audit` reports 10 moderate dev-only advisories (minimatch via eslint); the only fix forces an ESLint downgrade and was not applied.
- `.superpowers/` is gitignored agent scratch space: never commit or link to it.
- CI (`.github/workflows/ci.yml`) is unverified: runs failed before any step because of a GitHub account billing lock. Re-run it once billing is resolved.

---

## Conventions

- **Git:** work on the phase branch (`phase-1-foundation`); one commit per task, Conventional Commits, authored as `ryanalmasii <ryanalmasii@gmail.com>` via `git -c user.name=... -c user.email=... commit`, pushed after each task; a draft PR at the end. Never push to or merge into `main`, never force-push or tag; the **owner is the only one who merges**. Commit only when asked.
- **Secrets:** nothing secret in git. Config comes from env via pydantic-settings; only `.env.example` files are tracked; gitleaks runs in pre-commit and CI (run `gitleaks git --redact -v .` before pushing).
- **Quality gates:** ruff (check + format) and mypy strict for the API; ESLint + Prettier + `tsc` for the web; `make check` before every push. Tests run against real Postgres, not mocks. Write tests first (TDD).
- **API:** every error uses the shared JSON error shape; web code calls the API only through `web/src/api/client.ts` with generated types, and the committed `schema.gen.ts` must match `make gen-types`.
- **LLM code:** go through the Protocols in `llm/base.py`; every call returns `Usage`; new adapters must pass the contract tests in `api/tests/llm/`.
- **DB:** the app runs as `feynman_app` (no DDL); only Alembic runs as `feynman_migrator`. Schema changes are migrations.
- **Decisions:** explain first, owner approves (see "Decision process" below). No silent architectural choices or unplanned dependencies.

---

## Notes for future sessions

- The Phase 1 code is the approved foundation, pending the owner's review and merge. Next: orchestrator review of the draft PR → owner merges → Phase 2 (MVP) planning toward the vision above (tutor agent, scoring, feedback, PDF-to-flashcards).
- **Start with [`docs/planning-handoff.md`](docs/planning-handoff.md).** It holds the detailed multi-stage scoring design, the provider, voice, embedding, and Postgres research with pricing, per-session cost estimates, and the list of open decisions for the owner.

### Phase order (decided)
1. **Refactor and restructure the architecture.** 2. **Build an MVP of the backend and app.** 3. **Then improvements.** The scope and exit criteria for each phase are in `docs/planning-handoff.md` §0. Don't start Phase 3 features (voice, billing, calibration, and so on) before the MVP exists.

### Handoffs and memory.md (owner's rule)
`memory.md` (repo root) is the project's running record of context and completed work. It is **versioned with the repo** and is separate from Claude Code's private auto-memory. Every new session reads it right after this file.

**Every time the owner asks for a handoff, do these steps in this order. The handoff prompt is always the LAST step.**
1. **Update `memory.md` first:** bump the dates and handoff number, add a Session log entry (what was completed, what the owner decided, what is still open), refresh the repo state (git status, files added or changed, anything uncommitted) and the next steps and caveats. Be factual about anything incomplete or failed.
2. **Update the other docs that are now stale:** `docs/planning-handoff.md` §1/§5, the ADRs and `docs/implementation-plan.md` if they exist, and this file if the structure, commands, or rules changed.
3. **Write the handoff prompt last:** a new file `handoff-prompts/orchestrator-handoff-N.md`, where N is the highest existing number + 1. Never overwrite earlier handoffs. It is a self-contained prompt for the next agent session and should include:
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
