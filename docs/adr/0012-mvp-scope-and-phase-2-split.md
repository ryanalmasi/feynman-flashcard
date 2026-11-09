# 0012. MVP scope and Phase 2 split into three branches

- **Status:** Accepted (owner, 2026-11-09)

## Context
Phase 1 (architecture foundation) merged on 2026-11-09. The MVP scope in `docs/planning-handoff.md` §0 was a proposal awaiting owner confirmation (§5 #8). The Phase 2 outline in `docs/implementation-plan.md` has nine milestones (M1 auth → M9 usage logging), roughly nine times Phase 1's size; one PR at the end would be too large to review well.

## Options
1. Confirm the §0 scope as written; one phase branch and one PR.
2. **Confirm the §0 scope as written; split into three phase branches, each with its own draft PR and owner merge.**
3. Trim the scope (e.g. drop generated flashcards, M5) to reach a usable loop sooner.

## Decision
Option 2.
- **Scope (unchanged from §0):** accounts; study sets and manual flashcards; PDF upload → editable Knowledge Map → generated flashcards; text Feynman session with the "curious novice" tutor; scoring v1 (baseline + single-sample judge with quote verification + asymmetric band + divergence flag); feedback; basic usage logging; one LLM provider. Generated flashcards stay in.
- **Out of MVP (unchanged):** voice, billing/trials, multi-sample judge and tie-break, gold-set calibration and provider bake-off, mastery/spaced repetition, prompted/unprompted claim credit, OAuth/social login (Google is the first post-MVP auth feature, ADR 0005), mobile apps, the polished landing page.
- **Split:**
  - **2a, foundations (no LLM):** M1 auth, M2 study sets + flashcards, M3 PDF upload + job queue. Also absorbs Phase 1 leftovers (CORS headers on 500s, CSRF header in CORS `allow_headers`, small test cleanups).
  - **2b, AI content:** M4 Knowledge Map, M5 generated flashcards. Needs the LLM provider decision.
  - **2c, core loop:** M6 text Feynman session, M7 scoring v1, M8 feedback, M9 usage logging. Needs the embedding model and scoring parameters.
- Each sub-phase follows ADR 0011 (its own `phase-2x-*` branch, one commit per task, draft PR, owner merges) and gets its own plan and implementer prompt. Decisions are taken just before the sub-phase that needs them.

## Consequences
Three smaller reviews instead of one large one. 2a can start before the LLM provider is chosen. The Phase 2 exit criteria (planning doc §0) are judged after 2c.
