# Implementer Kickoff: Phase 2a fix-up round

> Paste this as the opening prompt of a new **Sonnet** Claude Code session started in `~/code/feynman-flashcard`.
> Written 2026-11-09 by orchestrator session 4, after reviewing draft PR #2. The owner has approved this run and the fix below.

---

You are the **implementer** for a one-fix round on draft PR #2 (https://github.com/ryanalmasi/feynman-flashcard/pull/2, branch `phase-2a-foundations`). The orchestrator reviewed the PR against `docs/implementation-plan-phase-2a.md` and found it conformant. This run makes **exactly the fix below**, nothing more. Work in this session directly; no subagents are needed.

## Read these first, in order
1. `CLAUDE.md`: the owner's rules and current structure.
2. `memory.md`: the "Implementation run: Phase 2a" entry.
3. `docs/implementation-plan-phase-2a.md`: Global Constraints (Task 5 for the rate limiter, Task 6 for the auth routes).
4. `docs/adr/0017-auth-security-details.md`. Don't edit any ADR or the design.

## Rules for this run
- **The owner has approved this run.** That gives you standing permission, *for this run only*, to commit and push branch `phase-2a-foundations`.
  - Never push to or merge into `main`, force-push, rewrite pushed commits, tag, or change global git config.
  - Don't mark the PR ready and don't merge it.
- **Commits:** `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com commit ...`, Conventional Commits, ending with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (adjust to the model actually running). Commit this prompt file first, on its own: `docs: add phase 2a fix-up implementer prompt`.
- **Before each push:** `make check` passes, then `gitleaks git --redact -v .` reports no leaks. Never commit a `.env` file. No `sudo`. No new dependencies.
- **TDD:** write the tests first and watch them fail for the right reason.
- **Scope is closed.** Anything else you notice → note it in the PR body; don't change it.
- **Evidence before claims.** CI is proven with `gh run watch --exit-status <id>`. Zero-step failures are an account problem: stop and tell the owner.

## Preflight
1. `git switch phase-2a-foundations && git pull --ff-only`. `git status` must be clean apart from this prompt file. Anything else → stop and ask.
2. `make db && make check` → passes (baseline: 235 pytest, 98 vitest; record the actual counts).

## Fix

### R3. Limit failed password attempts on `DELETE /auth/account`
Today a caller holding a valid session can try passwords there without limit, which also burns argon2 CPU. This fix reuses the existing Postgres rate limiter (`feynman_api.auth.rate_limit`), with the same semantics as the per-email login lockout (design §7.8).

- **Settings** (`config.py`, plus commented entries in `api/.env.example`):
  - `account_delete_failure_limit: int = 5`
  - `account_delete_window_seconds: int = 900`
- **Key:** `"account_delete:user:" + str(user.id)`. Add a helper `def account_delete_key(user_id: uuid.UUID) -> str` in `rate_limit.py`. It holds no email, so no hashing is needed.
- **Order in `delete_account`** (`routes/auth.py`):
  1. `current_user` (unchanged: 401, then 403 for CSRF/Origin).
  2. `peek(key, limit, window, now)` with `now` from the injected clock (add the `Now` dependency). If not allowed → `rate_limited(retry_after)` (429 + `Retry-After`). This happens **before** any password verification, so a full window blocks even the correct password, as with login.
  3. Wrong password → `hit(key, …)`, then 401 `invalid_credentials` (unchanged code and message; the SPA must not log out).
  4. Correct password → `clear(key)`, then the existing deletion flow unchanged.
  - `hit`/`clear` commit the session (see the note in `rate_limit.py`). Call them before any pending writes, as above.
- **Tests first** in `api/tests/test_auth_routes.py` (use `clean_db`, the `clock` fixture and the existing helpers):
  - `test_delete_account_lockout_blocks_correct_password(clock)`:
    - 5 wrong passwords → each 401 `invalid_credentials`
    - the 6th, with the **correct** password → 429 `rate_limited` with an integer `Retry-After` ≥ 1; the user row still exists; `GET /auth/session` still returns 200
    - `clock.advance(minutes=15)`, then the correct password → 204
  - `test_delete_account_limit_is_per_user`: user A locked out (5 wrong) → user B's wrong attempt still gets 401, not 429.
  - `test_delete_account_success_after_failures_under_limit`: 4 wrong, then the correct one → 204.
  - The CSRF matrix and the no-secrets-in-logs test stay green unchanged.
- **Web:** no code change expected. `AccountPage` already shows the server message inline. Add one test to `web/src/pages/AccountPage.test.tsx`:
  - "429 shows the rate-limit message and keeps the user signed in": a stubbed 429 `{"error":{"code":"rate_limited","message":"Too many attempts. Try again later.","details":null}}` → that text is shown in the dialog, and the AppShell nav is still rendered.
  - If the test fails because the page needs a change, make the minimal change and record it as a deviation.
- `make gen-types`. The 429 response must be documented on the route (`responses={…, 429: {"model": ErrorResponse}}`); commit the regenerated `schema.gen.ts`.
- **Docs:** add the 429 to the `DELETE /auth/account` row of the HTTP API table in `CLAUDE.md`.
- Commit: `fix(api): rate-limit failed password attempts on account deletion`.

## Finish
1. `make check` → passes; report the new counts (expected +3 pytest, +1 vitest; give the actual numbers). `gitleaks git --redact -v .` → no leaks.
2. Push, then `gh run watch --exit-status $(gh run list --branch phase-2a-foundations --limit 1 --json databaseId -q '.[0].databaseId')` → green. Report the run URL.
3. **Update the PR body** (`gh pr edit 2 --body-file <tmpfile>`):
   - Add a "Fix-up round (orchestrator review)" section: R3, its commit, its tests, the CI link.
   - In "Owner decisions needed", mark item 2 (`DELETE /auth/account` attempt limit) as resolved.
   - Update the test counts and the CI link.
   - Keep the closing `🤖 Generated with [Claude Code](https://claude.com/claude-code)` line.
4. **Update `memory.md`:** add a short entry "Implementation run: Phase 2a fix-ups" (the change, test counts, CI run, deviations), and mark owner-decision item 2 resolved in the Phase 2a entry. Commit `docs: record phase 2a fix-up round`, gitleaks, push, and confirm CI green again.
5. Report to the owner, then **stop**. The report covers:
   - the PR URL
   - the commits
   - the test counts
   - the CI link
   - any deviations
   The orchestrator re-reviews, and the owner merges.
