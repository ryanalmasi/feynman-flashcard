# 0011. Git workflow: phase branches, pushed, draft PR, owner merges

- **Status:** Accepted (owner, 2026-11-08)

## Context
The owner's standing rule is "commit only when asked". Subagent-driven implementation and per-task review both need per-task commits. The owner wants phases properly versioned on GitHub, and "CI green" (a Phase 1 exit criterion) can only be shown on GitHub.

## Decision
For an implementation run the owner has approved:
- Work on a branch named for the phase (Phase 1: `phase-1-foundation`), created from `main`.
- **One commit per completed plan task**, using `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com commit ...`. Global git config is never changed.
- **Push the phase branch** to `origin` after each task (or group of tasks), only after gitleaks passes.
- **Never** push to `main`, force-push, rewrite pushed history, create tags, or merge.
- When the phase is complete, open a **draft PR** to `main` with `gh pr create --draft`.
- **The owner is the final reviewer and the only one who merges.** The orchestrator session reviews the PR against the plan before the owner merges.

## Consequences
The owner installs and authenticates `gh` before the run (`gh auth login`). This permission covers approved implementation runs only. Planning sessions still commit only when asked.
