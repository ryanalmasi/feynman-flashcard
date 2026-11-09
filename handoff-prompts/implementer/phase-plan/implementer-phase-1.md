# Implementer Kickoff: Phase 1

> Paste this as the opening prompt of a new **Sonnet** Claude Code session started in `~/code/feynman-flashcard`.
> Written 2026-11-09 by orchestrator session 2. The owner has approved this run.

---

You are the **implementer** for Phase 1 (architecture foundation) of the Feynman Flashcard project. Your job is to execute an already-approved plan exactly, using **superpowers:subagent-driven-development**: a fresh subagent implements each task, a fresh reviewer checks it before the next task starts, and the whole branch is reviewed at the end.

## Read these first, in order
1. `CLAUDE.md`: owner rules. Its prototype sections describe the code you are about to delete.
2. `memory.md`: project state.
3. `docs/implementation-plan.md`: **your instructions.** Global Constraints and Review Focus apply to every task.
4. `docs/superpowers/specs/2026-11-08-phase-1-foundation-design.md`: the approved design the plan argues from.
5. `docs/adr/0001`–`0011`: the decisions. Don't edit them.
6. `docs/setup-prerequisites.md`: the machine setup. Task 0 runs its verification block.

## Rules for this run
- **The owner has approved this run.** That gives you standing permission, *for this run only*, to commit once per task and push branch `phase-1-foundation` (ADR 0011). Never push to or merge into `main`, force-push, tag, or change global git config. Every commit uses `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com commit ...`.
- **Never commit a `.env` file or a real secret.** Run gitleaks before every push.
- **No `sudo`.** If a prerequisite is missing, stop and tell the owner which setup step to run.
- **Don't make unplanned architectural choices.** A new dependency the plan doesn't name, a structural change, or anything touching security posture means you stop and ask the owner. Minor implementation details the plan leaves open are yours to decide; record notable ones as "deviations" for the PR body.
- **Evidence before claims.** Don't report a task, test run, or CI as passing without the command output that shows it.
- Work in order, Task 0 → Task 9. Task 7 step 5 needs the owner to check the page in their Windows browser, so ask them and wait.

## Finish
Task 9 ends by opening a **draft** PR (`gh pr create --draft`) and updating `memory.md`. Report the PR URL to the owner, then **stop**. Don't merge and don't mark the PR ready. The owner merges after an orchestrator review. Phase 2 is **out of scope**, including everything in the plan's "Phase 2 outline: NOT FOR EXECUTION" section.

If context gets large, the handoff hook may fire. For this run, a handoff means: update `memory.md` with progress (completed tasks, the current task and step, any failures), then write `handoff-prompts/implementer/phase-plan/implementer-phase-1-resume-N.md` telling the next implementer session where to resume.
