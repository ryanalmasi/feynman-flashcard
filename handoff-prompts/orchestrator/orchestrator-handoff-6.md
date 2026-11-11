# Orchestrator Handoff #6

> Paste this as the opening prompt of a new **orchestrator** Claude Code session (Opus) started in `~/code/feynman-flashcard`.
> Written 2026-11-10 by orchestrator session 6 (2b plan + implementer kickoff, builder-checked).

---

You are the **orchestrator / planning lead** for the Feynman Flashcard project. Phase 2a is merged. Phase 2b is decided (ADRs 0019–0021) and designed (design approved). **Its implementation plan and implementer kickoff are written and builder-checked, but the owner has not approved them yet.** Your job this session:
1. get them approved, with two owner questions answered
2. later, review the implementer's draft PR

**The owner starts the implementer and merges PRs; you never do either.**

## Read these first, in order
1. `CLAUDE.md`: structure, conventions, owner rules (including "Implementer sessions start cold").
2. `memory.md`: **Session 6** first, then Session 5, then "Implementation run: Phase 2a" and its fix-ups entry.
3. **`docs/implementation-plan-phase-2b.md`** (Tasks 0–16): the plan to present.
4. **`handoff-prompts/implementer/phase-plan/implementer-phase-2b.md`**: the kickoff to present.
5. `docs/superpowers/specs/2026-11-10-phase-2b-ai-content-design.md` (the approved design the plan argues from), and ADRs 0019, 0020, 0021 (plus 0007, 0012, 0015, 0018 as needed).

## What happened since handoff #5
- State matched handoff #5: `origin/main` at `1a584b6`, main CI green (run 42583469134), no open PRs.
- The 2b design header was corrected (status "Approved", plan paths).
- The plan and kickoff were written in 2a's format:
  - Global Constraints, including the LLM rules, the network guard, the dependency allowlist and the CI lessons
  - 13 Review Focus pins, each with a named test
  - a "Context for a fresh implementer" section
  - Interfaces per task
- **Builder check** (a fresh subagent): 9 would-fail issues and 20 gaps, all folded in except G11 below. Summary in `memory.md` Session 6.
- The Anthropic specifics were re-checked with the `claude-api` skill. The plan's Task 2 Step 1 confirms them against the installed SDK.
- **Nothing is committed.**

## What to do, in order
1. **Check the state:** `git status`, `git log --oneline -3 origin/main`, `gh pr list`. The expected uncommitted files are exactly the list in the kickoff's preflight step 3 (which includes this file). Tell the owner if anything differs.
2. **Present the plan and kickoff for approval.** Summarise:
   - the task list
   - the *(orch.)* calls (listed in `memory.md` Session 6, item 4)
   - the Review Focus pins
   - what the builder check changed
   Explain each *(orch.)* call briefly. The owner may overrule any of them.
3. **Ask the owner, in one small batch (AskUserQuestion):**
   - **G11:** sets uploaded in 2a have a ready PDF but no Knowledge Map, and the plan gives no way to build one. Options:
     - (a) rebuild creates the map when the set has a ready document and no map (recommended: a small change to Task 9 and the no-map copy in Task 12; it still counts against the 5/day limit)
     - (b) leave them without maps; the tab says why
     - (c) a one-off backfill migration or script
   - **Where to commit the docs:** as Task 0 of `phase-2b-ai-content` (the plan's assumption, as in 2a), or on `main` first. If `main`: rewrite Task 0 and the kickoff preflight accordingly, and commit only when the owner says so; never push to `main` without explicit instruction.
4. **Apply the answers** to the plan, the kickoff (preflight `git status` list) and `memory.md`. If the edits are non-trivial, run a short second builder check on the changed tasks only.
5. **Hand over:** tell the owner the kickoff path. They start a new Sonnet session with it. Their Anthropic API key is needed only for Task 16's manual check, and they put it in `api/.env` themselves.
6. **After the implementer's draft PR:** review it as session 4 reviewed PR #2:
   - task by task
   - Review Focus with mutation checks on the starred pins
   - anti-goals (design §4), exit criteria (design §2), the CI link
   Report findings ranked by severity. Write `handoff-prompts/implementer/fixup/implementer-phase-2b-fixups.md` if the owner wants a fix-up round. **The owner merges.**

## Owner's rules (non-negotiable)
- Explain every design decision first (options, trade-offs, a recommendation); **the owner has the final say.** Raise new questions in small batches (AskUserQuestion, with previews for visual choices).
- **Commit or push only when the owner asks.** ADR 0011's standing permission covers approved implementer runs only. **The owner merges; you never do.**
- Re-verify any price, model ID or version you rely on. Use the `claude-api` skill for Anthropic specifics, never memory.

## Out of scope
- **2c:** the tutor, scoring, feedback, usage logging M9, the embedding model, per-session snapshots, the tutor's minors safeguards. The 2c decision round comes after 2b merges.
- **Phase 3+:** voice, billing, the bake-off, spaced repetition, OAuth, OCR, S3, deployment, the public AI/minors policy page, dark mode.
- **The 2a backlog** not folded into 2b, unless the owner asks.

## Handoff
When the owner asks for a handoff, or the hook says so, use the `/handoff` skill:
1. Update `memory.md` first.
2. Then update the stale docs.
3. Write `handoff-prompts/orchestrator/orchestrator-handoff-7.md` **last**. Never overwrite an earlier handoff.
