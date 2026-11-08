# memory.md: running project context

> **Purpose:** the repo's own record of what has happened so far, so a fresh agent session can pick up without the old conversation.
> **Rule:** update this file **first** during any handoff. The handoff prompt (`handoff-prompts/orchestrator-handoff-N.md`) is written **last**, after this file and the docs are current. See "Handoffs" in `CLAUDE.md`.
> **Not the same as** Claude Code's private auto-memory (`~/.claude/projects/.../memory/MEMORY.md`). That one is outside the repo. This file is versioned with the project and is the source of truth for project state.

**Last updated:** 2026-11-08 (end of session 1)
**Latest handoff written:** #1 (`handoff-prompts/orchestrator-handoff-1.md`)

---

## 1. Project snapshot

- **What it is:** a study tool built around the Feynman technique: the student teaches a topic to an AI, gets a multi-stage score and feedback, and reviews AI-generated flashcards built from their PDF or topic.
- **What exists in code today:** only the old hand-written (ChatGPT-pasted) prototype from Jan 2025: Flask + MySQL + Redis backend and a Create React App frontend, with manual flashcard CRUD and a single-card embedding-similarity score. No tutor agent, voice, PDF ingestion, tests or CI. Full detail and known bugs are in `CLAUDE.md`.
- **Current phase:** Planning, before **Phase 1** (architecture refactor and restructure). Phase order, decided by the owner: **1. Refactor/restructure → 2. MVP of backend and app → 3. Improvements.** Scope and exit criteria are in `docs/planning-handoff.md` §0.

## 2. Session log

### Session 1 (2026-11-08): mapping, research, planning docs
Models: Opus 5.5, then Sonnet 5.5. Nothing was implemented; no application code was changed.

**Completed**
1. Read the whole repo and wrote `CLAUDE.md`: the file map, stack, data model, API routes, how to run it, and a list of known bugs (the prototype is described as it *currently is*).
2. Captured the owner's answers: the stack is open for a full change, the DB leans to Postgres (secure and minimal), scoring must be multi-stage, and "Illumina" was only the old DB name.
3. Designed the multi-stage scoring system → `docs/planning-handoff.md` §2: a Knowledge Map instead of the raw PDF; Stage 0 normalize and extract claims; Stage 1 deterministic baseline; Stage 2 evidence-quoted AI rubric judge; Stage 3 asymmetric-band reconciliation; Stage 4 feedback; calibration with a gold set; the data model additions.
4. Researched pricing and options (checked 2026-11-08) → §3: LLM providers (official Claude/OpenAI/Gemini pricing), voice architectures, embeddings, Postgres hosting, and stack candidates. Per-session cost estimates in §4 (≈ $0.015 per 20 min text on cheap tier; ≈ $0.04 per 1 h text; voice is the largest cost).
5. Drafted a pricing model → §4b (14-day trial, Plus $5.99/mo, Pro $9.99/mo with a 15 h voice cap, margins).
6. Added the phased roadmap (§0) and tagged the open decisions by phase (§5).
7. Wrote `handoff-prompts/orchestrator-handoff-1.md`.
8. Added the owner's rules to `CLAUDE.md`: explain decisions first; phase order; handoffs.
9. Added this `memory.md` workflow, the `handoff` skill, and the context-usage hook (see §5 below).

**Decisions the owner has made**
- Phase order (refactor → MVP → improvements).
- Every design decision must be explained first, with the owner having the final say.
- Postgres is the preferred direction; scoring is multi-stage (baseline + AI-graded, reconciled).
- Handoff workflow: `memory.md` updated first, then `handoff-prompts/orchestrator-handoff-N.md` last (N = highest existing + 1).

**Decisions NOT yet made (all of `docs/planning-handoff.md` §5)**
Stack, LLM provider(s), voice v1, embeddings, Postgres host and auth approach, scoring parameters, privacy and age policy, the MVP scope cut, the fate of the old UI code, and pricing/billing.

## 3. Repository state

- **Git:** branch `main`. All session 1 files are **committed** in one commit ("Add project docs, handoff workflow, and handoff hook") on top of the 5 old prototype commits. Not pushed. The machine has no git user configured, so the commit was made with `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com` (the author of the earlier commits), chosen by the owner for this one commit only. Global git config was not changed.
- **Junk still tracked in git** (cleanup not yet approved): `.DS_Store` files, `__pycache__/`, `backend/feynman_card/flask_session/`. There is no root `.gitignore`.
- **Files added this session**

| Path | What it is |
|---|---|
| `CLAUDE.md` | Repo guide, owner rules, phase order, handoff rule |
| `docs/planning-handoff.md` | Design + research + roadmap + open decisions |
| `handoff-prompts/orchestrator-handoff-1.md` | Prompt for the next session |
| `memory.md` | This file |
| `.claude/settings.json` | Project hooks config (context-usage and handoff-keyword hook) |
| `.claude/hooks/handoff-check.py` | The hook script |
| `.claude/skills/handoff/SKILL.md` | The `/handoff` skill: the procedure |

## 4. Open questions and next steps

**Next session should:** follow `handoff-prompts/orchestrator-handoff-1.md`: confirm the repo state, run the Phase 1 decision round (one or a few decisions at a time, each explained and approved, recorded as ADRs in `docs/adr/`), write `docs/implementation-plan.md`, get it approved, and only then start building.

**Open for the owner:** do the repo-hygiene cleanup (root `.gitignore`; untrack `.DS_Store`, `__pycache__/`, `flask_session/`)? Set a git user on this machine (commits currently fail without one)? Voice-mode notes in the docs should be checked against the owner's priorities when the MVP scope is confirmed.

**Caveats to remember**
- Third-party prices (Deepgram, AssemblyAI, ElevenLabs, Neon/Supabase free tiers, competitor prices) are lower-confidence and marked in the doc. Re-verify before relying on them.
- Conversion rates and usage figures in §4b are assumptions, not data.
- The hook only injects reminders; it does not count tokens exactly (see §5).

## 5. Handoff automation (set up in session 1)

- **Skill `/handoff`** (`.claude/skills/handoff/SKILL.md`): the procedure: update `memory.md` → update docs → write `handoff-prompts/orchestrator-handoff-N.md` **last** → tell the owner to start a new session. It also auto-matches when the owner says it's time to hand off.
- **Hook** (`.claude/settings.json` → `.claude/hooks/handoff-check.py`), on `UserPromptSubmit` and `PostToolUse`:
  - estimates context size from the latest usage record in the session transcript;
  - at **≥ 250,000 tokens** (~25% of a 1M window) injects a heads-up: offer a handoff;
  - at **≥ 300,000 tokens** (~30%) tells the model to run the `handoff` skill at the next natural stopping point;
  - when the owner's prompt mentions a handoff or a new agent session, injects a reminder to run the skill;
  - each level fires once per session (it re-arms if context shrinks after `/compact`). Thresholds can be changed with the `HANDOFF_WARN_TOKENS` and `HANDOFF_URGENT_TOKENS` env vars.
- If the hook doesn't seem to fire, open `/hooks` once or restart the session so the settings are reloaded.
