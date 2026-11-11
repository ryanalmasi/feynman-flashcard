# Implementer Kickoff: Phase 2b (Knowledge Map + generated flashcards)

> Paste this as the opening prompt of a new **Sonnet** Claude Code session started in `~/code/feynman-flashcard`.
> Written 2026-11-10 by orchestrator session 6. The owner has approved this run.

---

You are the **implementer** for Phase 2b of the Feynman Flashcard project. This phase adds the first AI:
- an Anthropic adapter behind the project's own LLM Protocols
- an editable, reorderable Knowledge Map, built from an uploaded PDF by a chunked, resumable job
- flashcards (Q/A and cloze) generated from that map into a draft tray

Your job is to execute an already-approved plan exactly, using **superpowers:subagent-driven-development**:
- a fresh subagent implements each task
- a fresh reviewer checks it against the plan's task, Global Constraints and Review Focus before the next task starts
- the whole branch gets a final review at the end

You start cold: everything you need is in the files below.

## Read these first, in order
1. `CLAUDE.md`: the current structure, commands, gotchas and the owner's rules.
2. `memory.md`: these entries, in this order:
   - **"Session 5 (2026-11-10): 2b decision round and the 2b design"**: what was decided and the open caveats
   - **"Implementation run: Phase 2a"**: the 2a deviations and the deferred minors, so you know what the code already does and what was left alone
   - **"Implementation run: Phase 2a fix-ups"**
   - **"Session 4"**: only for the CI and environment lessons
3. **`docs/implementation-plan-phase-2b.md`: your instructions.**
   - Its **Global Constraints** and **Review Focus** apply to every task.
   - Its **"Context for a fresh implementer"** section lists the existing code to reuse; give each task's subagent that section plus its task.
   - Items marked *(orch.)* are approved choices: follow them as written.
4. `docs/superpowers/specs/2026-11-10-phase-2b-ai-content-design.md`: the approved design the plan argues from (cited as "design §N"). If the plan and the design disagree, **stop and ask**.
5. The ADRs, by number:
   - **0019** (Anthropic provider; `temperature` removed)
   - **0020** (Knowledge Map)
   - **0021** (generated flashcards)
   - **0007** (LLM Protocols, amended by 0019)
   - **0012** (phase split)
   - **0013** (age 13+)
   - **0015** (job queue)
   - **0018** (content model)
   Don't edit any ADR or the design.
6. `docs/implementation-plan-phase-2a.md` and `docs/implementation-plan.md`: **only** for the Global Constraints that 2b inherits.

## Preflight (Task 0 does this; stop at the first mismatch)
1. `cd ~/code/feynman-flashcard && git switch main && git pull --ff-only`.
2. `git log --oneline -1` → `1a584b6 Phase 2a: accounts, study sets, PDF upload and job queue (#2)`. A later commit means the owner added something: ask before continuing.
3. `git status --porcelain` must show **exactly** these lines (order may differ):
   ```
    M CLAUDE.md
    M docs/adr/0007-llm-provider-abstraction.md
    M docs/adr/README.md
    M docs/planning-handoff.md
    M memory.md
   ?? docs/adr/0019-llm-provider-anthropic.md
   ?? docs/adr/0020-knowledge-map.md
   ?? docs/adr/0021-generated-flashcards.md
   ?? docs/implementation-plan-phase-2b.md
   ?? docs/superpowers/specs/2026-11-10-phase-2b-ai-content-design.md
   ?? handoff-prompts/implementer/phase-plan/implementer-phase-2b.md
   ?? handoff-prompts/orchestrator/orchestrator-handoff-5.md
   ?? handoff-prompts/orchestrator/orchestrator-handoff-6.md
   ```
   Anything else (any `.env`, a `mode change`, another file) → stop and ask the owner.
4. `git switch -c phase-2b-ai-content`, then commit exactly those files (plan Task 0, Step 4).
5. `make db && make migrate && make check` → passes. The baseline is **238 pytest / 99 vitest** (2a's final counts). Record the actual numbers. Then `gitleaks git --redact -v .` → no leaks, and `git push -u origin phase-2b-ai-content`.

## Rules for this run
- **The owner has approved this run.** That gives you standing permission, *for this run only*, to commit once per task (plus review fix-ups) and push branch **`phase-2b-ai-content`** (ADR 0011).
  - Never push to or merge into `main`, force-push, rewrite pushed commits, tag, or change global git config.
  - Every commit uses `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com commit ...`, with Conventional Commits, ending with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (adjust to the model actually running).
- **Before every push:** `make check` passes, then `gitleaks git --redact -v .` reports no leaks. Never commit a `.env` file or a real secret. No `sudo`.
- **The owner pre-approves `make db-reset`** in this run (the local dev DB holds nothing worth keeping).
- **Dependencies:** only the plan's allowlist: `anthropic`, `httpx2` (dev), the shadcn `tabs` component, and `@dnd-kit/core` + `@dnd-kit/sortable` (+ `@dnd-kit/utilities` only if needed).
  - Any other package, including one a CLI pulls in → remove it, or if it's needed, **stop and ask the owner**.
  - The same applies to any architectural or structural choice the plan doesn't make, anything touching security posture (auth, CSRF, roles, what gets logged, what reaches the LLM), and any change to a quoted user-facing message.
- **Anthropic specifics:** use the `claude-api` skill and the installed SDK for every SDK name and call. Never write them from memory.
  - Plan **Task 2, Step 1** confirms the mocked transport, the structured-output call, `effort` on both models and the API version before any adapter code. Record what you found.
  - If no mocked-transport route exists, stop and ask.
- **No network in tests, ever.** The guard from Task 1 must stay on. Only `tests/llm/test_anthropic_live.py` may use `@pytest.mark.allow_network`, and it is skipped unless `RUN_LIVE_LLM=1` and a key are set. Don't run it yourself.
- **The API key is the owner's.**
  - Never ask for it, read `api/.env`'s key line, print it, log it or put it anywhere.
  - The manual check (plan Task 16, Step 3) needs the owner to put their key in `api/.env` with `LLM_ENABLED=true`; they do that themselves.
  - Development and every test use fakes and the mocked transport.
- Minor details the plan leaves open are yours. Record notable ones as **deviations** for the PR body.
- **TDD:** each task's tests are written first and seen failing for the right reason. For each task's Review Focus pin, the reviewer mutation-checks it (break the behaviour, watch the named test fail, restore).
- **Evidence before claims.** Don't report a task, test run, or CI as passing without the command output.
  - **CI:** prove it with `gh run watch --exit-status <id>`.
  - If runs fail with zero steps executed (an account or billing lock), stop and tell the owner. Don't loop.
- **Known traps:** the plan's Global Constraints list them:
  - pre-commit stashes unstaged files, so stage config first
  - container loopback is trust-auth, so password probes use `-h db`
  - pin Actions by SHA
  - the owner's browser is the Windows one
  - FastAPI hides included routers, so use `walk_routes`
- Work in order, Task 0 → Task 16.
  - **Task 16, Step 3 needs the owner's manual browser check:** ask them, wait, and record their answer verbatim.
  - Task 6's `make worker` start/stop check is yours.
- **Out of scope:** everything 2c (tutor, scoring, feedback, embeddings, usage logging M9, per-session snapshots) and everything the design lists in §3. If you notice an idea, note it in the PR body; don't build it.

## Finish
Task 16 updates the docs and `memory.md`, then opens a **draft** PR (`gh pr create --draft`). Report the following to the owner, then **stop**:
- the PR URL
- the commits per task
- the test counts
- the CI run link
- the owner's browser-check result
- the SDK confirmations from Task 2
- the deviations

Don't merge and don't mark the PR ready. The orchestrator reviews it, and the owner merges.

If context gets large, the handoff hook may fire. For this run, a handoff means:
1. Update `memory.md` with progress (completed tasks with commit ids, the current task and step, any failures or open questions).
2. Write `handoff-prompts/implementer/phase-plan/implementer-phase-2b-resume-N.md` (N = the highest existing + 1). It tells the next implementer session where to resume and repeats this file's "Read these first" list and rules by reference.
3. Stop.
