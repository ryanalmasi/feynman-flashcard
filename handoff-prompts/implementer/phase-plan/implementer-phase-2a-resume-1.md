# Implementer resume: Phase 2a (resume 1)

> Paste as the opening prompt of a new **Sonnet** Claude Code session in `~/code/feynman-flashcard`. Written 2026-11-09 by implementer session 1 because its context filled up. The owner's approval and every rule in `handoff-prompts/implementer/phase-plan/implementer-phase-2a.md` still apply (read it first; it is the kickoff for this run).

## Where things stand
- Branch `phase-2a-foundations` (pushed). **Tasks 0-13 complete and reviewed. Task 14 implemented in `a04be21` (98 vitest, 233 pytest, `make check` green) but its review has NOT been done.** Remaining: review Task 14, Task 14 step 5 (the owner's manual browser check), then Task 15.
- The run uses **superpowers:subagent-driven-development**: the controller (you) dispatches a fresh implementer subagent per task (model `sonnet`), then a reviewer (sonnet; opus for security-critical), runs a fix loop for Critical/Important findings, and finishes with a whole-branch review. Resume the loop; do not redo finished tasks.

## Read first, in order
1. `handoff-prompts/implementer/phase-plan/implementer-phase-2a.md` (rules), `CLAUDE.md`, `memory.md` (the "Implementation run: Phase 2a, IN PROGRESS" entry: commit table, owner decisions, deviations, deferred minors).
2. `docs/implementation-plan-phase-2a.md` (Global Constraints lines 15-58; Review Focus; Tasks 14 and 15).
3. The ledger `.superpowers/sdd/implementation-plan-phase-2a/progress.md` (gitignored; on this machine; per-task `task-N-brief.md`, `task-N-report.md`, review diffs are beside it). Per the skill, read `references/resuming.md` of the SDD skill first. If the ledger is missing, recover from `git log` and `memory.md`.

## Next steps
1. **Review Task 14** (`git diff c978f67..a04be21`): generate the package with the SDD skill's `scripts/review-package <plan> c978f67 a04be21`, dispatch a task reviewer (sonnet) with `task-14-brief.md`, `task-14-report.md`, the package. Probe: polling interval/stop/10-minute limit/unmount cleanup, overlapping polls, FormData upload with CSRF header and no manual Content-Type, 20 MiB client boundary, the `key={document.id}` remount, errors keep polling, tokens test. Fix loop per the skill for Critical/Important only.
2. **Task 14 step 5: the owner's manual check.** Run `make db`, `make migrate`, `make api`, `make worker`, `make web` (stop servers by PID, never `pkill -f`); confirm `curl -s localhost:5173` works from WSL; then ask the owner to run the 9-step checklist from the plan in the **Windows** browser at `http://localhost:5173` (register, log out/in, create set, add/edit/delete cards, review, upload `api/tests/fixtures/text.pdf` -> `Ready · 3 pages`, upload `image_only.pdf` -> scanned message, delete set, delete account) and confirm in DevTools that `feynman_session` is HttpOnly. **Wait** and record their answer verbatim. Fix what they report (new commits).
3. **Task 15** (docs, CI, memory, draft PR): follow the plan exactly. The PR body must include the owner decisions, deviations and deferred minors listed in `memory.md`. Before the PR, run the SDD whole-branch final review (`references/final-review.md` in the skill; the most capable model, e.g. opus) and triage the deferred minors. CI: `gh run watch --exit-status <id>`; zero-step failures (billing lock) mean stop and tell the owner; do not loop.
4. Final report to the owner, then stop: PR URL, commits per task, test counts, CI run link, the owner's browser-check result, the deviations. Don't merge or mark ready.

## Reminders
- Commits: `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com commit ...`, Conventional Commits, trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Before every push: `make check`, then `gitleaks git --redact -v .`. Never push to/merge into `main`, force-push, or tag.
- Only the plan's approved dependencies. Never edit `.gitleaks.toml` (change test strings instead). Do not edit ADRs or the design.
- pre-commit stashes unstaged files: `git add` first. The types-drift check compares against the git index: stage `web/src/api/schema.gen.ts` before `make check`.
- If context fills again: update `memory.md`, write `handoff-prompts/implementer/phase-plan/implementer-phase-2a-resume-2.md`, stop.
