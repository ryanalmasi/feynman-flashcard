# Orchestrator Handoff #5

> Paste this as the opening prompt of a new **orchestrator** Claude Code session (Opus) started in `~/code/feynman-flashcard`.
> Written 2026-11-10 by orchestrator session 5 (2b decision round → 2b design, builder-checked and approved).

---

You are the **orchestrator / planning lead** for the Feynman Flashcard project. Phase 2a is merged. The **Phase 2b decisions are made** (ADRs 0019–0021) and the **2b design is approved by the owner**. Your job this session:
1. write the 2b implementation plan and the implementer kickoff prompt, the same way 2a was done
2. get them approved
3. later, review the implementer's draft PR

**The owner starts the implementer and merges PRs; you never do either.**

## Read these first, in order
1. `CLAUDE.md`: structure, conventions, owner rules (including "Implementer sessions start cold").
2. `memory.md`: **Session 5** first (what was decided and the open caveats), then "Implementation run: Phase 2a" (deviations, deferred minors) and its fix-ups entry, then Session 4.
3. **The approved design:** `docs/superpowers/specs/2026-11-10-phase-2b-ai-content-design.md`. It is the spec, including §5 (approved dependencies), §7 (the design, with the builder-check *(orch.)* calls folded in), §8 (left to the builder) and §9 (owner answers).
4. ADRs **0019** (Anthropic provider; `temperature` removed), **0020** (Knowledge Map), **0021** (generated flashcards). Also 0007 (LLM Protocols; amended by 0019), 0012 (phase split), 0013 (age 13+), 0015 (jobs), 0018 (content model).
5. **The 2a artefacts as templates:**
   - `docs/implementation-plan-phase-2a.md` (plan format: Global Constraints, Review Focus pinned to named tests, File Structure, tasks with Interfaces, failing tests first, one commit per task)
   - `handoff-prompts/implementer/phase-plan/implementer-phase-2a.md` (kickoff format)
6. **The code 2b builds on.** Verify every name before citing it.
   - `api/src/feynman_api/llm/` (`base.py`, `fake.py`, `errors.py`) and `api/tests/llm/test_contract.py`
   - `jobs/` (`queue.py`, `registry.py`, `worker.py`, `handlers/extract_pdf.py`)
   - `auth/rate_limit.py` (`hit` **commits**), `auth/ownership.py`, `errors.py`
   - `models/` (`flashcard.py`, `document.py`), `routes/flashcards.py`, `routes/schemas.py`, `config.py`, `clock.py`
   - `tests/conftest.py`, `tests/test_ownership.py`, `tests/test_worker.py` (it pins `GENERIC_FAILURE`)
   - `web/src/pages/SetDetailPage.tsx`, `ReviewPage.tsx`, `web/src/components/DocumentStatus.tsx`, `CardFormDialog.tsx`, `web/src/api/client.ts`

## What happened since handoff #4
- **PR #2 (Phase 2a) merged** by the owner (squash `1a584b6`, 2026-11-09). Main CI green (run 42583469134).
- **Prices and policies re-verified on 2026-11-10** (sources in ADR 0019). One API change matters: version `2026-10-21` rejects `temperature`, `top_p` and `top_k`.
- **Decision round:** ADRs 0019–0021 written. Summary in `memory.md` Session 5. Several choices went against the orchestrator's recommendation:
  - chunk + merge
  - resume from saved chunks
  - concept reordering, via drag with `@dnd-kit`
  - cloze cards
  - a draft tray
  - a warning popup on regeneration
- **Design written and builder-checked:** 7 would-fail issues and 11 gaps, all folded in. **The owner approved it.**

## Where things stand
- Phase 1 and 2a are merged. **2b is designed, not planned.** 2c is not decided.
- **Uncommitted on `main`'s working tree:**
  - `docs/adr/0019…`, `0020…`, `0021…` (new), `docs/adr/0007…` (status line), `docs/adr/README.md`
  - the 2b design
  - `memory.md`, `docs/planning-handoff.md`, `CLAUDE.md`
  - this file
  **Ask the owner** whether to commit them on `main` or as Task 0 of `phase-2b-ai-content` (2a's Task 0 committed its ADRs, design and plan). Commit only when asked. Never push to `main` without the owner's explicit instruction.

## What to do, in order
1. **Check the state:** `git status`, `git log --oneline -3 origin/main`, `gh pr list`, `gh run list --branch main --limit 1`. If anything differs from the above, tell the owner before going further.
2. **Write `docs/implementation-plan-phase-2b.md`** from the approved design, in the 2a plan format.
   - **Global Constraints:** carry over 2a's, plus 2b's:
     - no network in tests (the network guard)
     - no `temperature`
     - only `llm/anthropic.py` imports the SDK
     - the approved dependencies only: `anthropic`, `httpx2` (dev), the shadcn `tabs` component, and `@dnd-kit/core` + `@dnd-kit/sortable` (+ `@dnd-kit/utilities` if needed)
     - CI and environment lessons: prove CI with `gh run watch --exit-status`; zero-step failures mean an account problem; stage config before testing pre-commit hooks; `-h db` for password probes; pin Actions by SHA; the owner's browser check runs in the Windows browser
   - **Branch:** `phase-2b-ai-content`.
   - **A "Context for a fresh implementer" section before Task 0.** It lists, as paths plus names plus what each is for, the existing code 2b reuses. At minimum:
     - `tests/conftest.py`: `clean_db`, `db`, `clock`/`FrozenClock`, `user_client`/`other_user_client`, `register`, `auth_headers`, `ORIGIN`, `walk_routes`, `file_store`
     - `auth/dependencies.py`: `current_user`, `CurrentUser`
     - `auth/ownership.py`: the `get_owned_*` helpers, and `tests/test_ownership.py` `OWNED_ENDPOINTS` with its exact-coverage meta-test
     - `errors.py`: `AppError` and the error table
     - `auth/rate_limit.py`: `hit`, `peek`, `clear`; `hit` commits
     - `jobs/`: `enqueue`, `claim`, `mark_*`, `registry.register`, `JobHandler`, `PermanentJobError`, `GENERIC_FAILURE`, `WorkerContext`, and `handlers/extract_pdf.py` as the handler pattern. Handlers are imported only by the worker.
     - `llm/base.py`, `llm/fake.py`, `llm/errors.py`, `tests/llm/test_contract.py`
     - `models/document.py`: `Document`, `DocumentPage`; `models/flashcard.py`
     - `web/src/api/client.ts`: `api`, `errorMessage`; `web/src/auth/useAuth.ts`; `web/src/components/ui/` and `web/src/index.css` (tokens); `DocumentStatus.tsx` (the polling pattern); `web/src/test/tokens.test.ts`
     Verify each name still exists.
   - **Every task's Interfaces → Consumes** names the exact earlier symbols it uses (module path + name).
   - **Suggested task order** (adjust as needed):
     - Task 0: docs commit
     - the Protocol change and contract-test refactor, plus the network guard
     - **the Anthropic adapter, whose first step confirms the SDK names** (`DefaultAsyncHttpxClient`, `httpx2.MockTransport`, the structured-output call, Haiku `effort`; design §7.4)
     - migrations and models
     - the pure `knowledge/` modules (chunking, clean, merge, cloze)
     - worker changes (`LeaseLost`, `renew_lease`, per-kind generic message, `WorkerContext` fields, the `on_failed` hardening)
     - `extract_pdf` changes
     - the `build_knowledge_map` handler
     - map and concept routes
     - flashcard route changes and accept/reject
     - the `generate_flashcards` handler
     - web: tabs and the map tab (with @dnd-kit), suggested tab and regenerate dialogs, the cloze editor and review
     - docs
   - **Review Focus:** pin each risk to a named test. At minimum:
     - resume doesn't re-send done chunks
     - parallel-sibling results are stored on a transient failure
     - a stale lease writes nothing
     - regeneration keeps manual and edited cards
     - suggested cards are excluded from review and counts
     - cross-user 404 on every new endpoint
     - no network in tests
     - no `temperature` in request bodies
     - the Usage mapping
     - a 404 or 409 doesn't consume the limit
     - the `on_failed` pin
   - **Builder-check the plan** with a fresh subagent that reads only the plan (in 2a this caught three would-fail issues). Fix what it finds, and bring the owner only questions that change what gets built.
3. **Write `handoff-prompts/implementer/phase-plan/implementer-phase-2b.md`**, following the 2a kickoff:
   - Sonnet, subagent-driven development.
   - Standing permission to commit and push **only** the 2b branch. Draft PR at the end; never merges.
   - Stops on any unplanned dependency or architectural choice.
   - It opens with a numbered **"Read these first, in order"** list:
     - `CLAUDE.md`
     - the named `memory.md` entries (Session 5; "Implementation run: Phase 2a" and its fix-ups)
     - the 2b plan, including its context section
     - the 2b design
     - ADRs 0019, 0020, 0021, 0007, 0012, 0013, 0015, 0018
     - the 2a plan, only for its inherited Global Constraints
   - **Preflight:**
     1. `git switch main && git pull`
     2. `git status` matches an exact expected list
     3. create `phase-2b-ai-content`
     4. `make db && make migrate && make check`, against the baseline **238 pytest / 99 vitest** (2a's final counts; record the actual numbers)
   - **The manual check needs the owner's Anthropic API key** in `api/.env` with `LLM_ENABLED=true`. The implementer never asks for the key or handles it.
   - Before handing over, re-read the prompt as if you knew nothing but the repo, and check that every file it relies on is named.
   - Present the plan and the prompt for approval.
4. **After the implementer's draft PR:** review it as session 4 reviewed PR #2:
   - task by task
   - Review Focus with mutation checks on the key pins
   - anti-goals, exit criteria, the CI link
   Report findings ranked by severity, and write a fix-up prompt (`handoff-prompts/implementer/fixup/implementer-phase-2b-fixups.md`) if the owner wants one. **The owner merges.**

## Owner's rules (non-negotiable)
- Explain every design decision first (options, trade-offs, a recommendation). **The owner has the final say.** Don't write code or plan steps that depend on an unapproved decision. Raise new ones in small batches (the owner likes AskUserQuestion with previews for visual choices).
- **Commit or push only when the owner asks.** ADR 0011's standing permission covers approved implementer runs only. **The owner merges; you never do.**
- Re-verify any price, model ID or version you rely on. Use the `claude-api` skill for Anthropic specifics, never memory.

## Out of scope
- **2c:** the Feynman tutor, scoring (baseline, judge, reconciliation), feedback, full usage logging (M9), the embedding model, per-session concept snapshots, the minors safeguards for the tutor.
- **Phase 3+:** voice, billing, the bake-off and calibration, spaced repetition, OAuth, OCR, S3, deployment, the public AI/minors policy page, dark mode.
- **2a backlog** not folded into 2b (see `memory.md` §4): only if the owner asks.

Note ideas in the docs, but don't build them.

## Handoff
When the owner asks for a handoff, or the hook says so, use the `/handoff` skill:
1. Update `memory.md` first.
2. Then update the stale docs.
3. Write `handoff-prompts/orchestrator/orchestrator-handoff-6.md` **last**. Never overwrite an earlier handoff.
