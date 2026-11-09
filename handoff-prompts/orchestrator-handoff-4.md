# Orchestrator Handoff #4

> Paste this as the opening prompt of a new **orchestrator** Claude Code session (Opus) started in `~/code/feynman-flashcard`.
> Written 2026-11-09 by orchestrator session 4 (Phase 2a plan → implementation review → fix-up → CI fix).

---

You are the **orchestrator / planning lead** for the Feynman Flashcard project. Phase 2a is built, reviewed, fixed up and CI green on draft PR #2. **The owner merges it; you never do.** Your job this session: **run the Phase 2b decision round**, then write the 2b design, plan and implementer prompt, the same way 2a was done.

## Read these first, in order
1. `CLAUDE.md`: the current structure, conventions and owner rules (now including 2a: auth, sets/cards, upload, jobs).
2. `memory.md`: start with **Session 4**, then "Implementation run: Phase 2a" (deviations, deferred minors, owner decision items) and its fix-ups entry.
3. `docs/planning-handoff.md`:
   - §0: the roadmap and the MVP loop
   - §2: the scoring design. Knowledge Map is §2.2, the proposed tables §2.11.
   - §3.1: LLM provider research (prices **unverified**)
   - §4: cost per session
   - §5: open decisions
4. `docs/adr/0012` (the split: 2b = M4 Knowledge Map + M5 generated flashcards), `0007` (the LLM layer: Protocols, `Usage`, contract tests), `0013` (age policy: users may be 13+), `0015` (jobs), `0018` (content model; `concept_id` arrives in 2b).
5. The 2a artefacts as templates:
   - `docs/superpowers/specs/2026-11-09-phase-2a-foundations-design.md` (design format)
   - `docs/implementation-plan-phase-2a.md` (plan format: Global Constraints, Review Focus pinned to named tests, File Structure, tasks with Interfaces, failing tests first, one commit)
   - `handoff-prompts/implementer-phase-2a.md` and `implementer-phase-2a-fixups.md` (kickoff formats)
6. The code the 2b work builds on:
   - `api/src/feynman_api/llm/` (`base.py`, `fake.py`) and `api/tests/llm/test_contract.py`: a real adapter must pass these
   - `jobs/` (queue, worker, `registry.py`, `handlers/extract_pdf.py`): 2b adds job kinds
   - the `document_pages` table: the page text the Knowledge Map reads from

## What happened since handoff #3
- **2a plan** written (`docs/implementation-plan-phase-2a.md`) and builder-checked; the owner approved it with six *(orch.)* calls.
- **2a implemented** by a Sonnet implementer (subagent-driven): 16 tasks plus per-task fix rounds, and a final Opus whole-branch review.
- **Orchestrator review of PR #2:** conformant; four Review Focus pins mutation-checked.
- **One fix-up:** `5d0e027`, a per-user limit on failed passwords for `DELETE /auth/account`.
- **CI fix by the orchestrator** (owner-approved): `cd2883b`. The secrets job now downloads gitleaks with an authenticated, retried `gh release download`, after anonymous downloads returned 504 during a GitHub incident.
- **CI green:** run 42581239361. Local: 238 pytest, 99 vitest.
- **Owner's browser checks closed:** the full flow works; the session cookie is HttpOnly, Lax, no Secure in dev. The "password found online" report was most likely Chrome's own password-manager warning.

## Where things stand
- Phase 1: merged. **Phase 2a: PR #2 open (draft), CI green, awaiting the owner's merge.** Phase 2b/2c: not decided.
- **Uncommitted** (left by session 4's handoff): `memory.md`, `CLAUDE.md`, `docs/planning-handoff.md`, and this file.
  - Session 4 recommended committing them onto `phase-2a-foundations` before the merge.
  - If they are still uncommitted when you start, **ask the owner** whether to commit them on `main` (after the merge) or on the new 2b branch. Commit only when asked.

## What to do, in order
1. **Check the state:** `git status`, `git log --oneline -3 origin/main`, `gh pr view 2 --json state`, `gh run list --branch main --limit 2`.
   - **If PR #2 is not merged yet,** tell the owner and wait. 2b branches from `main` after the merge, though decisions can be discussed in the meantime.
   - After the merge, `git switch main && git pull`.
   - If anything differs from the above, tell the owner before going further.
2. **The 2b decision round**, one or a few decisions at a time, each with options, trade-offs and a recommendation. Record each accepted decision as an ADR (next number: **0019**).
   1. **LLM provider and models** for Knowledge Map extraction and card generation (and, looking ahead, the 2c tutor and judge).
      - **Re-verify every price and model ID today**; §3.1's numbers are unverified.
      - Check the **data-retention and training settings** (zero-retention options, no training on API data), because students may be 13–17.
      - Check structured-output support (the `generate_structured` Protocol), prompt caching (`PromptBlock.cache`), and rate limits.
      - The adapter must pass `api/tests/llm/test_contract.py`. CI must never call a real provider: fakes only, and the API key comes from env, so gitleaks must stay clean.
      - If an Anthropic model is a candidate, use the `claude-api` skill for current model IDs and pricing.
   2. **Knowledge Map details:**
      - the schema (start from §2.11: concepts with importance, key terms, misconceptions, source page refs)
      - how the student edits the map (add, edit, delete, reorder?)
      - versioning (is a map edit a new version?)
      - the job kind and its limits (tokens per document, cost cap, chunking for long PDFs up to 200 pages)
   3. **Generated flashcards:** cards per concept, style (Q/A vs. cloze), the `concept_id` link, regeneration rules, and the UI for accepting or editing.
   4. **Anything else 2b forces,** e.g. a per-user LLM cost or usage guard (full usage logging is 2c, M9; decide whether 2b needs a minimal version).
   - Use AskUserQuestion where it helps. The owner likes mockups for visual choices. The visual companion works under WSL only when started with `--host 0.0.0.0 --url-host localhost`.
3. **Write the 2b design** `docs/superpowers/specs/<date>-phase-2b-ai-content-design.md`, in the 2a design's structure (intent, goals and exit criteria, non-goals, anti-goals, constraints and approved dependencies, design, left to the builder).
   - Run a builder check (a fresh subagent reading only the design).
   - Bring the owner only the questions that change what gets built, then get approval.
4. **Write `docs/implementation-plan-phase-2b.md`** in the 2a plan format. **The implementer is a brand-new session with none of your context** (owner's rule, `CLAUDE.md` "Implementer sessions start cold"). The plan's subagents each see only one task. So:
   - Add a **"Context for a fresh implementer"** section before Task 0. It lists the existing 2a and Phase 1 code 2b builds on, as paths plus the names to reuse and what each is for. At minimum:
     - `api/tests/conftest.py`: `clean_db`, `db`, `clock`/`FrozenClock`, `user_client`/`other_user_client`, `register`, `auth_headers`, `ORIGIN`, `walk_routes`, `file_store`
     - `auth/dependencies.py`: `current_user`, `CurrentUser`
     - `auth/ownership.py`: the `get_owned_*` helpers (new owned resources add one here and an entry in `tests/test_ownership.py` `OWNED_ENDPOINTS`)
     - `errors.py`: `AppError` and the error table
     - `jobs/`: `enqueue`, `registry.register`, `JobHandler`, `PermanentJobError`, `GENERIC_FAILURE`, `WorkerContext`, and `handlers/extract_pdf.py` as the handler pattern. Handlers are imported only by the worker.
     - `llm/base.py` and `llm/fake.py`, plus `tests/llm/test_contract.py`
     - `models/document.py`: `DocumentPage`
     - `web/src/api/client.ts`: `api`, `errorMessage`
     - `web/src/auth/useAuth.ts`
     - `web/src/components/ui/` and `web/src/index.css`: the tokens
     - `web/src/components/DocumentStatus.tsx`: the polling pattern
     - `web/src/test/tokens.test.ts`
     Verify each name still exists before listing it.
   - Every task's **Interfaces → Consumes** names the exact earlier symbols it uses (module path + name). Never rely on "as in 2a".
   - Branch: `phase-2b-ai-content`.
   - Carry over 2a's Global Constraints and its CI/environment lessons:
     - prove CI with `gh run watch --exit-status`
     - zero-step failures mean an account problem
     - stage config before testing pre-commit hooks
     - `-h db` for password probes
     - pin Actions by SHA
     - the owner's browser check runs in the Windows browser
   - Builder-check the plan (in 2a this caught three would-fail issues).
5. **Write `handoff-prompts/implementer-phase-2b.md`** (Sonnet, subagent-driven development; standing permission to commit and push only the 2b branch; draft PR; never merges; stops on any unplanned dependency or architectural choice). Because the session starts cold, the prompt must open with a numbered **"Read these first, in order"** list:
   - `CLAUDE.md`
   - **named** `memory.md` entries (Session 5 and the "Implementation run: Phase 2a" and fix-up entries, for the deviations and deferred minors that affect 2b)
   - the 2b plan, including its context section
   - the 2b design
   - the ADRs by number (0019+ and 0007, 0012, 0013, 0015, 0018)
   - the 2a plan, only for its inherited Global Constraints
   It also needs a **preflight**: switch to `main` and pull; `git status` matches an exact expected list; create `phase-2b-ai-content`; then `make db && make migrate && make check`, with the expected baseline (238 pytest / 99 vitest after 2a, or whatever `main` has after the merge; record the actual counts). Before handing over, re-read the prompt as if you knew nothing but the repo, and check that every file it relies on is named. Present the plan and prompt for approval. **The owner starts the implementer session.**
6. **After the implementer's draft PR:** review it as session 4 reviewed PR #2:
   - task by task
   - Review Focus with mutation checks on the key pins
   - anti-goals, exit criteria, CI link
   Report findings ranked by severity, and write a fix-up prompt if the owner wants one. **The owner merges.**

## Owner's rules (non-negotiable)
- Explain every design decision first (options, trade-offs, a recommendation). **The owner has the final say.** Don't write code that depends on an unapproved decision.
- Present decisions one or a few at a time.
- **Commit or push only when the owner asks.** ADR 0011's standing permission covers approved implementer runs only. **The owner merges; you never do.**
- Re-verify any price, model ID or version you rely on.

## Out of scope
- **2c:** the Feynman tutor session, scoring (baseline, judge, reconciliation), feedback, full usage logging (M9), the embedding model.
- **Phase 3+:** voice, billing and trials, the multi-sample judge and calibration bake-off, spaced repetition, OAuth (Google first), OCR, S3, deployment, branding, dark mode.
- **Optional 2a backlog** (in `memory.md`: the session-4 L findings, the deferred minors, owner decision items 1 and 3): only if the owner asks, e.g. folded into a 2b task.

Note ideas in the docs, but don't build them.

## Handoff
When the owner asks for a handoff, or the hook says so, use the `/handoff` skill:
1. Update `memory.md` first.
2. Then update the stale docs.
3. Write `handoff-prompts/orchestrator-handoff-5.md` **last**. Never overwrite an earlier handoff.
