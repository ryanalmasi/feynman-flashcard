# Orchestrator Handoff #1

> Paste this as the opening prompt of a new Claude Code session in the `feynman-flashcard` repo.
> Written 2026-11-08 by the previous session (repo mapping + research + scoring design).

---

You are the **orchestrator / planning lead** for the Feynman Flashcard project. Your job in this session is to turn the existing research and design into an **approved, phased implementation plan**, starting with **Phase 1 (architecture refactor and restructure)**. Phase 2 (MVP) comes after that.

## Read these first, in order

1. **`CLAUDE.md`** (repo root): what the repo currently is. It covers the old Flask + MySQL + React prototype, a map of every file, the API and data model, known bugs, the owner's working rules, and the handoff procedure.
2. **`memory.md`** (repo root): the running record of what has been completed so far, what the owner decided, the git state (everything from session 1 is uncommitted), and the next steps. Treat it as the source of truth for project state.
3. **`docs/planning-handoff.md`**: the main design document. Focus on:
   - **§0 Roadmap and phase order.** This is your scope: Phase 1, then Phase 2. Do not start Phase 3 work.
   - §1 Decisions so far
   - §5 Open decisions, tagged P1/P2/P3
   - §3 Research (stack, LLM providers, voice, embeddings, Postgres). Use it to inform Phase 1 decisions.
   - §2 Scoring design and §2.11 data model. This is the target the architecture must accommodate; the MVP builds a subset of it.
   - §4 / §4b Costs and pricing (context only; billing is Phase 3, but MVP usage logging is in scope)

## Owner's rules (non-negotiable)

- **Explain every design decision before implementing it:** the options, trade-offs, and your recommendation with reasoning. **The owner has the final say.** Do not write code that depends on an unapproved decision.
- Present decisions **one or a few at a time**, not as a wall of choices. Use the AskUserQuestion tool where it helps.
- Pricing in the docs was checked on 2026-11-08. Re-verify anything you rely on.
- Only commit or push when the owner asks.

## What to do in this session

1. **Get oriented.** Skim the current code briefly to confirm `CLAUDE.md` is accurate. Check `git status`: the session 1 docs, handoff prompt, `memory.md` and `.claude/` are already committed, so the tree should be clean. Note that no git user is configured on this machine, so commits need `-c user.name=... -c user.email=...` or a configured identity; ask the owner which to use. Then ask whether to do the repo-hygiene cleanup (root `.gitignore`; remove the committed `.DS_Store`, `__pycache__/`, `flask_session/`).
2. **Run the Phase 1 decision round.** Walk the owner through the P1 decisions (§0 Phase 1 list + §5 P1 items): backend stack, frontend tooling, repo layout, DB + migrations + role model, auth approach, config/secrets, the LLM provider abstraction interface, background jobs, testing/lint/CI, and salvage vs. restart of the old UI. For each one: options → trade-offs → recommendation → owner decision. Record each approved decision as an ADR in `docs/adr/NNNN-title.md`.
3. **Write the implementation plan** to `docs/implementation-plan.md`:
   - **Phase 1:** concrete, ordered tasks to reach the Phase 1 exit criteria in §0 (skeleton, Docker Compose Postgres, first migration, `/health`, API client, tests + CI, README/CLAUDE.md rewrite)
   - **Phase 2:** the MVP broken into milestones (auth → study sets/flashcards → PDF → Knowledge Map → generated cards → text Feynman session → scoring v1 → feedback → usage logging), each with acceptance criteria and tests
   - Dependencies, risks, and which P2 decisions must be made before each milestone
   - Get the owner's approval on the plan.
4. **Only after the plan is approved**, begin Phase 1 implementation if the owner wants to. If the owner asks for parallel work, you may delegate well-scoped tasks to subagents, each pointed at the relevant ADR and plan section, and review their output before reporting back.
5. **Keep docs current.** Update `docs/planning-handoff.md` §1 "Decisions so far" as decisions are made, and update `CLAUDE.md` once the structure changes.

## Out of scope for this session

Voice mode, billing/trials, the multi-sample judge and calibration bake-off, spaced repetition, deployment. These are all Phase 3+. Note ideas for them in the docs, but don't build them.

## When the owner asks for a handoff (or the handoff hook tells you to)

Use the `/handoff` skill (`.claude/skills/handoff/SKILL.md`). The order matters:
1. **Update `memory.md` first**, adding a Session log entry, the repo state, and the next steps.
2. Update any other docs that are now stale (`docs/planning-handoff.md` §1/§5, ADRs, `docs/implementation-plan.md`, `CLAUDE.md`).
3. **Write `handoff-prompts/orchestrator/orchestrator-handoff-2.md` last** (highest existing number + 1). Say what was decided, what was built, where things stand against the plan, and exactly what the next session should do.

A hook (`.claude/hooks/handoff-check.py`) will remind you at about 250k tokens (heads-up) and 300k tokens (run the handoff). If you don't see it fire, ask the owner to open `/hooks` once or restart so the project settings load.
