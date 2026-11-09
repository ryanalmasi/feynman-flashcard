# 0010. Old prototype: clean restart, keep images

- **Status:** Accepted (owner, 2026-11-08)

## Context
The prototype is about 1,300 lines of JS/Python with known structural bugs (CLAUDE.md "Known issues"): a double auth modal, buttons that submit forms by accident, card addressing by list index, and authorization holes. Its most complex UI piece, the landing page, is post-MVP.

## Options
1. **Clean restart, keep only the images.**
2. Port the landing page and auth modal to TS now. This keeps the look but adds Phase 1 work off the critical path and risks carrying the bugs over.

## Decision
Option 1. Remove `backend/`, `frontend/`, root `requirements.txt`, and all `.DS_Store` files from the working tree. They stay reachable in git history (last prototype commit: `5aba556`). Move `frontend/src/assets/images/*.png` to `web/src/assets/images/`.

## Consequences
All "Known issues" in the old CLAUDE.md disappear with the code. The Phase 2 plan must not reintroduce them: cards are addressed by id, every query is user-scoped, failures return proper HTTP status codes, and no state lives in the session except auth.
