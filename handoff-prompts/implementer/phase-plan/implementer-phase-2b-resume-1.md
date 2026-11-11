# Implementer Resume 1: Phase 2b (continue at Task 15)

> Paste this as the opening prompt of a new Claude Code session started in `~/code/feynman-flashcard`. Written 2026-11-11 by the implementer session that ran Tasks 0-14. The owner approved this run (see the kickoff).

You are continuing the Phase 2b implementer run. Tasks 0-14 are done, reviewed, committed and pushed on branch `phase-2b-ai-content` (head `7da5b1b`). **Resume at Task 15**, then Task 16, then the final whole-branch review. Use **superpowers:subagent-driven-development** exactly as before: a fresh implementer subagent per task, a task reviewer (spec + quality) after each, fix rounds resume the implementer (max 5), scoped re-reviews, mutation checks of each Review Focus pin.

## Read these first, in order
1. `handoff-prompts/implementer/phase-plan/implementer-phase-2b.md`: the original kickoff. **Its "Rules for this run" all still apply** (standing permission to commit per task and push only `phase-2b-ai-content`; never main/force/tag; commit identity and `Co-Authored-By: Claude Sonnet 5.5` trailer; `make check` then `gitleaks git --redact -v .` before every push; dependency allowlist; never touch the owner's API key; no network in tests; stop and ask for unplanned architecture/security/quoted-copy changes).
2. `CLAUDE.md`, then `memory.md`: the entry **"Implementation run: Phase 2b"** (commits per task, SDK confirmations, deviations, open owner questions, deferred minors) and the earlier entries the kickoff names.
3. `docs/implementation-plan-phase-2b.md`: **Tasks 15 and 16**, plus Global Constraints and Review Focus (apply to every task) and "Context for a fresh implementer". Design: `docs/superpowers/specs/2026-11-10-phase-2b-ai-content-design.md` (§7.8 for the web). ADRs 0019-0021. Don't edit ADRs or the design.
4. The SDD ledger: `.superpowers/sdd/implementation-plan-phase-2b/progress.md` (gitignored; also holds `constraints.md`, `context.md`, briefs, reports, review diffs, which you can reuse for dispatches). Read `references/resuming.md` of the skill first (it says whose ledger it is). If the folder is gone, rebuild the context from `git log e784fb6..HEAD` and `memory.md`.

## Preflight
1. `git switch phase-2b-ai-content && git pull --ff-only`; `git status --porcelain` must be empty; `git log --oneline -1` is `7da5b1b` (or a later commit of this run: check the ledger).
2. `make db && make migrate && make check` → **470 pytest (1 skipped) / 200 vitest** expected.

## What is left
- **Task 15** (web: cloze editor, `ClozeText` rendering, ReviewPage flip accessibility). Carried notes: show `details[0].msg` for card errors regardless of `loc` (create errors have `loc ["body"]`, PATCH `["body", field]`); accepted cloze cards currently show raw `{{answer}}` on the review page until this task; suggested cards must never reach the review page (its test "requests only accepted cards" is Review Focus #5); use token classes only; model text is plain text; narrow ReviewPage's button-ignore rule as the plan says.
- **Task 16**: CI proof (`gh run watch --exit-status <id>`; zero-step failures → stop and tell the owner), then the **owner's manual browser check** (ask the owner to put their key in `api/.env` themselves; never ask for/read/print it; record their answer verbatim; include the keyboard reorder focus check, a 2a-set "Build Knowledge Map" if one exists, and the `LLM_ENABLED=false` case), then docs (README, CLAUDE.md, `docs/planning-handoff.md`), `memory.md`, and the **draft PR** (`gh pr create --draft`). Don't merge or mark it ready.
- **Final whole-branch review** on the most capable model (skill `references/final-review.md`), pointed at the deferred minors in the ledger.

## Put in the PR body and the final report (owner must see these)
- Deviations/rulings and open copy questions: see `memory.md` entry "Implementation run: Phase 2b" (the T2, T4-T14 items). Highlight: **`@dnd-kit/accessibility` transitive dependency needs the owner's confirmation**; the "Map: building" vs "Map: processing" copy conflict; the "1 AI-generated cards" singular; builder-written copy ("Q/A cards need an answer on the back.", "Replace AI-generated cards?", "Other").
- Test counts, the CI run link, commits per task, the owner's browser-check result verbatim, the SDK confirmations.

## If context gets large again
Update `memory.md` (progress, commit ids, failures), write `handoff-prompts/implementer/phase-plan/implementer-phase-2b-resume-2.md` (N = highest existing + 1), and stop.
