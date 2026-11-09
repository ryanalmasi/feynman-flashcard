# Implementer Kickoff: Phase 2a (foundations)

> Paste this as the opening prompt of a new **Sonnet** Claude Code session started in `~/code/feynman-flashcard`.
> Written 2026-11-09 by orchestrator session 4. The owner has approved this run.

---

You are the **implementer** for Phase 2a of the Feynman Flashcard project: accounts, study sets and flashcards, and PDF upload with a job queue and worker. There is no LLM work in this phase. Your job is to execute an already-approved plan exactly, using **superpowers:subagent-driven-development**:
- a fresh subagent implements each task
- a fresh reviewer checks it against the plan's task, Global Constraints and Review Focus before the next task starts
- the whole branch gets a final review at the end

## Read these first, in order
1. `CLAUDE.md`: the current structure and the owner's rules.
2. `memory.md`: the project state (Session 3 and the Phase 1 implementation entries).
3. **`docs/implementation-plan-phase-2a.md`: your instructions.** Its Global Constraints and Review Focus apply to every task. Items marked *(orch.)* are approved choices: follow them as written.
4. `docs/superpowers/specs/2026-11-09-phase-2a-foundations-design.md`: the approved design the plan argues from. If the plan and the design disagree, stop and ask.
5. `docs/adr/0012`–`0018`, plus `0004`, `0005`, `0011` from Phase 1. Don't edit any ADR or the design.
6. `docs/implementation-plan.md` (Phase 1) only for the Global Constraints it inherits.

## Rules for this run
- **The owner has approved this run.** That gives you standing permission, *for this run only*, to commit once per task and push branch **`phase-2a-foundations`** (ADR 0011, 0012).
  - Never push to or merge into `main`, force-push, rewrite pushed commits, tag, or change global git config.
  - Every commit uses `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com commit ...`, with Conventional Commits, ending with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (adjust to the model actually running).
- **Before every push:** `make check` passes, then `gitleaks git --redact -v .` reports no leaks. Never commit a `.env` file or a real secret. No `sudo`.
- **The owner pre-approves `make db-reset`** in this run (the local dev DB holds nothing worth keeping).
- **Dependencies:** only those in the plan's Global Constraints allowlist.
  - Any other package, including one a CLI (shadcn) pulls in that the plan doesn't name → remove it, or if it's needed, **stop and ask the owner**.
  - The same applies to any architectural or structural choice the plan doesn't make, and anything touching security posture: auth, cookies, CSRF, roles, file paths, what gets logged.
- Minor details the plan leaves open are yours. Record notable ones as **deviations** for the PR body.
- **TDD:** each task's tests are written first and seen failing for the right reason.
- **Evidence before claims.** Don't report a task, test run, or CI as passing without the command output.
  - **CI:** prove it with `gh run watch --exit-status <id>`.
  - If runs fail with zero steps executed (for example "account is locked due to a billing issue"), it's an account problem: stop and tell the owner. Don't loop.
- **Known traps:** the plan's Global Constraints list them (pre-commit stashes unstaged files; trust auth on container loopback, so use `-h db`; pin Actions by SHA; the owner's browser is the Windows one).
- Work in order, Task 0 → Task 15.
  - **Task 14 step 5 needs the owner's manual browser check:** ask them, wait, and record their answer verbatim.
  - Task 10 step 5 is a curl check you do yourself.
- **Out of scope:** everything 2b/2c (LLM provider, Knowledge Map, generated cards, tutor, scoring, feedback, usage logging) and everything the design lists in §3. If you notice an idea, note it in the PR body; don't build it.

## Finish
Task 15 updates the docs and `memory.md`, then opens a **draft** PR (`gh pr create --draft`). Report the following to the owner, then **stop**:
- the PR URL
- the commits per task
- the test counts
- the CI run link
- the owner's browser-check result
- the deviations

Don't merge and don't mark the PR ready. The orchestrator reviews it, and the owner merges.

If context gets large, the handoff hook may fire. For this run, a handoff means:
1. Update `memory.md` with progress (completed tasks with commit ids, the current task and step, any failures or open questions).
2. Write `handoff-prompts/implementer/phase-plan/implementer-phase-2a-resume-N.md` telling the next implementer session where to resume.
3. Stop.
