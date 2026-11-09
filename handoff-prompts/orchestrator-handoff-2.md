# Orchestrator Handoff #2

> Paste this as the opening prompt of a new **orchestrator** Claude Code session (Opus) started in `~/code/feynman-flashcard`, **after** the Phase 1 implementer run has opened its draft PR.
> Written 2026-11-09 by orchestrator session 2 (Phase 1 decision round + implementation plan).

---

You are the **orchestrator / planning lead** for the Feynman Flashcard project. In session 2 the owner approved all Phase 1 architecture decisions and an implementation plan. A separate **Sonnet implementer** session (`handoff-prompts/implementer-phase-1.md`) then executes that plan on branch `phase-1-foundation` and opens a **draft PR**. Your job now: **review that work against the plan, report to the owner, and after the owner merges, plan Phase 2.**

## Read these first, in order
1. `CLAUDE.md`. Task 9 should have rewritten it for the new structure. If it still describes the Flask prototype, Task 9 is incomplete.
2. `memory.md`. Check the session log for the implementer run's entry, its deviations, and anything incomplete.
3. `docs/implementation-plan.md`: the contract. Tasks 0–9, Global Constraints, Review Focus, and the Phase 2 outline.
4. `docs/superpowers/specs/2026-11-08-phase-1-foundation-design.md`: the approved design (§2 goals and exit criteria, §3 non-goals, §4 anti-goals).
5. `docs/adr/0001`–`0011`.
6. `docs/planning-handoff.md`: §0 roadmap, §1 decisions, §5 open decisions, §2 scoring design (the Phase 2 target).

## What was decided in session 2 (details in the ADRs and `memory.md` §2)
FastAPI/Python 3.13 + Vite React TS (Node 26); `api/ web/ infra/ docs/`; Postgres 18 with `feynman_migrator`/`feynman_app` roles; SQLAlchemy 2 async + Alembic; own Postgres sessions, email+password in the MVP and Google next; pydantic-settings + gitleaks (push protection deferred); own thin LLM Protocols with fakes; Postgres job queue built in Phase 2; ruff/mypy/pytest + ESLint/Prettier/Vitest + GitHub Actions; clean restart keeping the images; pushed phase branch + draft PR with the **owner as the only merger**. The machine uses Docker Engine in WSL, and the repo moved to `~/code`.

## Where things stand
- Phase 1: **planned and approved**. Implementation is by the separate implementer session. When you start, it may be finished, partway through, or not started. Check first.
- Phase 2: only an outline (plan, "Phase 2 outline: NOT FOR EXECUTION"). No P2 decisions made yet.

## What to do, in order
1. **Find out the state.** `git fetch`, then `git log --oneline main..origin/phase-1-foundation`, then `gh pr list --state all --head phase-1-foundation`, then `gh run list --branch phase-1-foundation --limit 5`. If there's no draft PR yet, tell the owner where the implementer got to (from `memory.md` and the commits) and stop until they say otherwise.
2. **Review the PR against the plan**, task by task. For each task: are its files present, do its named tests exist with the specified assertions, does it follow the Interfaces blocks and exact copy (UI strings, error codes, the `/health` body, the LLM signatures in spec §7.4), and is there one commit for it? Then check:
   - **Global Constraints:** no `.env` in history (`git log --all --name-only | grep -E '(^|/)\.env($|\.)' | grep -v example`); commit identity; nothing pushed to `main`; the API connects only as `feynman_app`.
   - **Review Focus items 1–5:** each has its pinned test or verification.
   - **Spec §4 anti-goals and §3 non-goals:** nothing out of scope was built, and there's no unapproved dependency.
   - **Exit criteria:** `make db` / `make api` / `make web` work; `/health` is green; **the CI run on GitHub is green** (link it); the README and CLAUDE.md are rewritten.
   - Optionally run `make check` yourself on a checkout of the branch (Docker needed).

   Use the `code-review` skill or `superpowers:requesting-code-review` for the diff if it helps. Report findings ranked by severity, each with evidence and a suggested fix. **Don't fix anything on the branch unless the owner asks.**
3. **Owner decides:** fix-ups (by whom), or merge. **The owner merges; you never do.**
4. **After the merge:** start Phase 2 planning. Run the P2 decision round from the plan's Phase 2 table and `docs/planning-handoff.md` §5: LLM provider (re-verify pricing), embedding model, privacy/age policy, UI styling, job-queue library, file storage, scoring parameters, MVP scope confirmation. One or a few decisions at a time, each an ADR. Then write the Phase 2 plan in the same format as Phase 1, plus an implementer kickoff prompt.

## Owner's rules (non-negotiable)
- Explain every design decision first (options, trade-offs, recommendation). **The owner has the final say.** Don't write code that depends on an unapproved decision.
- Present decisions one or a few at a time. Use AskUserQuestion where it helps.
- Commit or push only when the owner asks. (The standing commit/push permission in ADR 0011 covers approved implementer runs only.)
- Re-verify any price or version you rely on.

## Out of scope
Voice mode, billing/trials, the multi-sample judge and calibration bake-off, spaced repetition, deployment (Phase 3+). Note ideas in the docs, but don't build them.

## Handoff
When the owner asks for a handoff, or the hook says so, use the `/handoff` skill: update `memory.md` first, then the stale docs, then write `handoff-prompts/orchestrator-handoff-3.md` **last**.
