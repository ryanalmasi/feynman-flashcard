# memory.md: running project context

> **Purpose:** the repo's own record of what has happened so far, so a fresh agent session can pick up without the old conversation.
> **Rule:** update this file **first** during any handoff. The handoff prompt (`handoff-prompts/orchestrator-handoff-N.md`) is written **last**, after this file and the docs are current. See "Handoffs" in `CLAUDE.md`.
> **Not the same as** Claude Code's private auto-memory (`~/.claude/projects/.../memory/MEMORY.md`). That one is outside the repo. This file is versioned with the project and is the source of truth for project state.

**Last updated:** 2026-11-09 (end of session 2, orchestrator / planning)
**Latest handoff written:** #2 (`handoff-prompts/orchestrator-handoff-2.md`), plus the implementer kickoff `handoff-prompts/implementer-phase-1.md`

---

## 1. Project snapshot

- **What it is:** a study tool built around the Feynman technique: the student teaches a topic to an AI, gets a multi-stage score and feedback, and reviews AI-generated flashcards built from their PDF or topic.
- **What exists in code today:** still only the old Jan-2025 prototype (Flask + MySQL + Redis + Create React App). **No new code has been written yet.** Details are in `CLAUDE.md`, which Phase 1 Task 9 will rewrite.
- **Current phase:** **Phase 1 is planned and approved, and not yet started.** Phase order: 1. refactor/restructure → 2. MVP → 3. improvements (`docs/planning-handoff.md` §0).
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

**Calls made by the orchestrator (flagged to the owner, not explicitly vetoed):** the LLM interface signatures (spec §7.4); planning docs reach git via the implementer's Task 0 commit on the phase branch; `make env` generates random dev passwords; browser-facing dev URLs use `localhost`; `asgi-lifespan` is pre-approved as a test-only dependency; the app role has no `TEMPORARY` privilege.

**Still open (Phase 2 decisions, see the plan's Phase 2 outline):** LLM provider, embedding model, privacy/age policy, scoring parameters, UI styling approach, job-queue library, file storage, MVP scope confirmation. Phase 3: voice, pricing/billing.

## 3. Repository state

- **Path:** `~/code/feynman-flashcard`. **Branch:** `main` at `e7bd5b9`, which equals `origin/main` (pushed).
- **Uncommitted (by design; the implementer's Task 0 commits them on `phase-1-foundation`):**
  - new: `docs/adr/` (12 files), `docs/superpowers/specs/2026-11-08-phase-1-foundation-design.md`, `docs/implementation-plan.md`, `docs/setup-prerequisites.md`, `handoff-prompts/orchestrator-handoff-2.md`, `handoff-prompts/implementer-phase-1.md`
  - modified: `memory.md`, `CLAUDE.md` (handoff number, repo path), `docs/planning-handoff.md` (§1, §5)
- **Junk still tracked:** `.DS_Store`, `__pycache__/`, `flask_session/`. Removed by plan Task 1.
- **Machine (checked 2026-11-09):** git, curl, and GitHub SSH (`ryanalmasi`) work. **Missing:** make, Docker, gh, uv/Python 3.13, Node 26, pre-commit, gitleaks. See `docs/setup-prerequisites.md` steps 1–6. `sudo` needs the owner's password, so steps 1–3 must be run by the owner.

## 4. Open questions and next steps

1. **Owner:** finish `docs/setup-prerequisites.md` steps 1–6. Step 7 must print `ALL PREREQUISITES OK`. Rename or delete the stale `/mnt/c/...` copy.
2. **Owner:** start a **Sonnet implementer** session in `~/code/feynman-flashcard` with `handoff-prompts/implementer-phase-1.md`. It runs `docs/implementation-plan.md` with subagent-driven development and ends by opening a draft PR.
3. **Next orchestrator session** (`handoff-prompts/orchestrator-handoff-2.md`): review the draft PR against the plan, spec, and ADRs; report findings to the owner; the owner merges. Then plan Phase 2.

**Caveats**
- Library versions in the plan aren't pinned by number on purpose (the latest stable at install time, locked by lockfiles). The pinned numbers (Python 3.13, Node 26, Postgres 18, gitleaks 8.30.1, nvm 0.41.0) were checked on 2026-11-09.
- WSL → Windows-browser access to `localhost:5173` and `:8000` wasn't tested. Plan Task 7 step 5 asks the owner to check it.
- The Postgres 18 image's volume layout (mount `/var/lib/postgresql`) comes from memory of the image change, so verify it during Task 2.
- Third-party prices in `docs/planning-handoff.md` §3–4 are still unverified (see session 1).

## 5. Handoff automation (set up in session 1)

- **Skill `/handoff`** (`.claude/skills/handoff/SKILL.md`): update `memory.md` → update docs → write `handoff-prompts/orchestrator-handoff-N.md` **last** → tell the owner to start a new session.
- **Hook** (`.claude/settings.json` → `.claude/hooks/handoff-check.py`) on `UserPromptSubmit` and `PostToolUse`: a heads-up at ≥ 250k tokens, run the handoff at ≥ 300k, and a reminder when the owner's prompt mentions a handoff. Thresholds: `HANDOFF_WARN_TOKENS` / `HANDOFF_URGENT_TOKENS`.
- Claude Code keys sessions and private memory by folder path. After the move to `~/code`, the hook config loads from the new folder's `.claude/` automatically.
