# Orchestrator Handoff #3

> Paste this as the opening prompt of a new **orchestrator** Claude Code session (Opus) started in `~/code/feynman-flashcard`.
> Written 2026-11-09 by orchestrator session 3 (Phase 1 review, fix-ups and merge; the Phase 2a decision round and design).

---

You are the **orchestrator / planning lead** for the Feynman Flashcard project. Phase 1 is merged. The owner has made every decision Phase 2a needs and **approved the 2a design**. Your job: **write the Phase 2a implementation plan and the implementer kickoff prompt**, get the owner's approval, and then (after the implementer run) review its draft PR.

## Read these first, in order
1. `CLAUDE.md`: the current structure, conventions and owner rules.
2. `memory.md`: start with the Session 3 entry (Phase 1 review → fix-ups → CI green → merge; the Phase 2 decisions).
3. **`docs/superpowers/specs/2026-11-09-phase-2a-foundations-design.md`: the approved design and your source of truth.** §2 has the goals and exit criteria, §3 the non-goals, §4 the anti-goals, §5 the constraints and approved dependencies, §7 the design, §8 what's left to the builder. Items marked "orchestrator's call" are approved as part of the design.
4. `docs/adr/0012`–`0018` (the Phase 2 decisions) and, as needed, `0001`–`0011`.
5. `docs/implementation-plan.md`: **the Phase 1 plan. Use it as the format template** (Global Constraints, Review Focus, File Structure, then per task: Files, Interfaces, failing tests first, steps, one commit). Its "Phase 2 outline" section is superseded by ADR 0012 and the 2a design.
6. `handoff-prompts/implementer/phase-plan/implementer-phase-1.md` and `implementer-phase-1-fixups.md`: templates for the kickoff prompt.
7. `docs/planning-handoff.md` §0, §2, §5: the roadmap, the scoring design (needed in 2c), and the decisions still open.

## What happened since handoff #2
- **Phase 1** was reviewed task by task: conformant. A fix-up round (F2–F6, F8: gitleaks scope, the `postgres` DB connect revoke, the `alembic_version` revoke, the health-timeout test, status-page errors, hygiene) was done by a Sonnet implementer and re-reviewed clean.
- CI had never run because of a GitHub account billing lock. The owner fixed it, and run 42547339617 went green. **PR #1 was squash-merged on 2026-11-09 (`3185eb1`).** Post-merge CI on `main` is green.
- **Phase 2 decisions (ADRs 0012–0018, all accepted):**
  - The MVP scope is as in §0, split into **2a** (auth, sets/cards, PDF upload + job queue; no LLM), **2b** (Knowledge Map, generated cards) and **2c** (tutor, scoring, feedback, usage logging), each with its own branch and PR.
  - 13+ neutral age screen, with no birth date stored.
  - Tailwind + shadcn/ui with central theme tokens.
  - Our own `jobs` table and worker.
  - Local-disk `FileStore` (20 MB, 200 pages, text PDFs only).
  - Auth details: 12-character minimum, HIBP fail-open, Postgres rate limits, CSRF token + Origin check, hashed session tokens.
  - One PDF per set, and pypdfium2 for reading PDFs (worker only).
- **2a design written, builder-checked, and approved by the owner.** The owner also approved the extra dependencies listed in design §5 and the upload size-cap mechanism (§7.3).

## Where things stand
- Phase 1: done and merged.
- Phase 2a: decided and designed. **No plan yet. Nothing is built.**
- Phase 2b/2c: not decided (see "Still open" in `memory.md`).
- **Uncommitted on `main`:**
  - the ADRs 0012–0018 and the ADR index
  - the 2a design
  - updates to `memory.md`, `CLAUDE.md` and `docs/planning-handoff.md`
  - this handoff file

  As in Phase 1, plan for the **implementer's Task 0 to commit them** on the new branch `phase-2a-foundations` (list the exact paths in Task 0 and require `git status` to match). The alternative is the owner asking you to commit them first.

## What to do, in order
1. **Check the state:** `git status`, `git log --oneline -3`, `gh run list --branch main --limit 2`. If anything differs from the above, tell the owner before going further.
2. **Write the plan** with the `superpowers:writing-plans` skill, as **`docs/implementation-plan-phase-2a.md`**. Leave `docs/implementation-plan.md` as the Phase 1 record.
   - Follow the Phase 1 format exactly: Global Constraints (carry over Phase 1's, plus the 2a dependency allowlist and the branch name), Review Focus (numbered, each pinned to a test), File Structure, Tasks 0…N.
   - Every task: Files, an Interfaces block (exact signatures, endpoint shapes, error codes, UI copy quoted from the design), failing tests first, then steps, then one commit (`ryanalmasii` identity via `-c` flags, pushed after gitleaks).
   - A sensible task order: Task 0 preflight/branch/commit docs → Phase 1 leftovers (§7.9) → migrations and models → passwords/HIBP/rate-limit/sessions/CSRF → auth routes → study sets and cards → `FileStore` and upload with the size cap → jobs queue and worker → `extract_pdf` → web: Tailwind/shadcn setup and tokens → auth pages and guard → sets, detail and review pages → upload and status polling → account page → `make check`, CI and docs → draft PR. Adjust if you have a reason, and say why.
   - **Suggested Review Focus items:**
     1. The ownership 404 matrix covers every endpoint.
     2. Cookie flags and hashed session tokens.
     3. CSRF and Origin enforcement on every unsafe route.
     4. No password, birth data or tokens in logs.
     5. An oversized upload leaves no temp or stored file.
     6. A worker lease is reclaimed and two claimers never get the same job.
     7. Raw palette colours appear nowhere in screens.
     8. Only 401 `not_authenticated` triggers logout.
   - **Lessons from Phase 1 to write into the plan:**
     - The implementer must prove CI green with `gh run watch --exit-status` and must not claim it otherwise. If runs fail with zero steps, it's an account or billing problem: stop and tell the owner.
     - pre-commit stashes unstaged files, so stage config changes before testing hooks.
     - Inside the Postgres container, `127.0.0.1` uses trust auth. Use `-h db` to test passwords.
     - Pin GitHub Actions by commit SHA.
     - The owner's manual browser check runs in the Windows browser under WSL.
   - **Don't put any 2b/2c work in the plan.**
3. Run a builder check on the plan if it helps (a fresh subagent reading only the plan). Settle minor questions yourself and mark them; bring the owner only questions that change what gets built.
4. **Write `handoff-prompts/implementer/phase-plan/implementer-phase-2a.md`:** a Sonnet implementer using subagent-driven development. It has standing permission for this run only to commit and push `phase-2a-foundations`, opens a draft PR, never merges, and stops and asks on any unplanned dependency or architectural choice.
5. Present the plan and prompt to the owner for approval. **The owner starts the implementer session.**
6. **After the implementer's draft PR:** review it against the plan the way session 3 reviewed PR #1 (task by task, Review Focus, anti-goals, exit criteria, CI link). Report findings ranked by severity. Write a fix-up prompt if the owner wants one. **The owner merges.**
7. After 2a merges: the **2b decision round**. The LLM provider and models come first (re-verify prices; check data-retention and training settings; students may be minors), then the Knowledge Map details and the card count and style. Then the 2b design, plan and prompt, the same way.

## Owner's rules (non-negotiable)
- Explain every design decision first (options, trade-offs, a recommendation). **The owner has the final say.** Don't write code that depends on an unapproved decision.
- Present decisions one or a few at a time; use AskUserQuestion where it helps. The owner likes seeing mockups for visual choices: the visual companion works under WSL only when started with `--host 0.0.0.0 --url-host localhost`.
- **Commit or push only when the owner asks.** The standing permission in ADR 0011 covers approved implementer runs only. **The owner merges; you never do.**
- Re-verify any price or version you rely on.

## Out of scope
- 2b/2c features: the LLM provider, Knowledge Map, generated cards, tutor, scoring, feedback, usage logging.
- Phase 3+: voice, billing and trials, the multi-sample judge and calibration bake-off, spaced repetition, OAuth (Google is first after the MVP), OCR, S3, deployment, branding and dark mode.

Note ideas in the docs, but don't build them.

## Handoff
When the owner asks for a handoff, or the hook says so, use the `/handoff` skill: update `memory.md` first, then the stale docs, then write `handoff-prompts/orchestrator/orchestrator-handoff-4.md` **last**.
