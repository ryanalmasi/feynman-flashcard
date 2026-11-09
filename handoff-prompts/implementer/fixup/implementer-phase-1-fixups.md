# Implementer Kickoff: Phase 1 fix-up round

> Paste this as the opening prompt of a new **Sonnet** Claude Code session started in `~/code/feynman-flashcard`.
> Written 2026-11-09 by orchestrator session 3, after reviewing draft PR #1. The owner has approved this run and every fix below.

---

You are the **implementer** for a small fix-up round on draft PR #1 (https://github.com/ryanalmasi/feynman-flashcard/pull/1, branch `phase-1-foundation`). The orchestrator reviewed the PR against `docs/implementation-plan.md` and found it conformant. This run makes **exactly the fixes listed below**, nothing more.

## Read these first, in order
1. `CLAUDE.md`: owner rules and current structure.
2. `memory.md`: the "Implementation run: Phase 1" entry, especially "Open items" and "Deferred minors".
3. `docs/implementation-plan.md`: Global Constraints and Review Focus still apply.
4. `docs/adr/0004` (DB roles), `0006` (secrets), `0009` (CI), `0011` (git rules). Don't edit any ADR.

## Rules for this run
- **The owner has approved this run.** That gives you standing permission, *for this run only*, to commit and push branch `phase-1-foundation`. Never push to or merge into `main`, force-push, rewrite pushed commits, tag, or change global git config. Don't mark the PR ready and don't merge it.
- Every commit: `git -c user.name=ryanalmasii -c user.email=ryanalmasii@gmail.com commit ...`, Conventional Commits, ending with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (adjust to the model actually running).
- **One commit per fix (F2–F8 below)**, pushed after `gitleaks git --redact -v .` reports no leaks. Commit this prompt file first, on its own: `docs: add phase 1 fix-up implementer prompt`.
- **Never commit a `.env` file or a real secret.** No `sudo`.
- **The owner pre-approves `make db-reset` in this run.** It deletes local dev DB data, which holds nothing worth keeping.
- **TDD:** for every fix with a test, write the test first, watch it fail for the right reason, then fix.
- **Scope is closed.** Anything not listed here (a new dependency other than `python-dotenv`, a structural change, a security-posture change beyond these fixes) → stop and ask the owner. Minor details are yours; record notable ones as deviations.
- **Evidence before claims.** Don't report anything as passing without the command output.

## Preflight
1. `git switch phase-1-foundation && git pull --ff-only`. `git status` must be clean apart from this prompt file. Anything else → stop and ask.
2. `make db && make check` → passes (the baseline: 36 pytest, 7 vitest).

## Fixes

Numbering follows the orchestrator's review (F1 is the CI billing lock, which only the owner can fix; F7 is deferred to Phase 2).

### F2. gitleaks must scan `*.env.example` files (`.gitleaks.toml`)
Right now `paths = ['''\.env\.example$''']` exempts those files entirely. The repo is public.
- Remove the `paths` allowlist. Keep the `ci-(postgres|migrator|app)` regex.
- Run `gitleaks git --redact -v .` and `gitleaks dir --redact -v .`. If the `change-me` placeholders are now flagged, allowlist **only that placeholder value** (e.g. add `'''change-me'''` to `regexes`). Don't allowlist by path, rule, or file.
- **Canary:** create `canary.env.example` containing `aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"` and `ghp_` followed by 36 alphanumeric chars. `git add` it, then run `pre-commit run gitleaks-system`. Expected: **Failed**. Then `git rm --cached` it and delete it. Never commit it.
- Commit: `fix(security): scan env example files with gitleaks; allowlist only the placeholder`.

### F3. `feynman_app` must not connect to the `postgres` database (`infra/postgres/init/01-roles.sh`)
It can currently log in there and create temp tables (`PUBLIC` keeps the default `CONNECT, TEMPORARY`).
- **Test first** in `api/tests/test_db_roles.py`: build a URL from `TEST_DATABASE_URL` with the database name swapped to `postgres` (use `sqlalchemy.engine.make_url(...).set(database="postgres")`), try to connect as `feynman_app`, and expect it to fail with a permission error. Assert on the asyncpg exception type (`InsufficientPrivilegeError` or the specific class Postgres raises; check which and pin it). The message must not leak into anything printed.
- Fix: in the first heredoc of `01-roles.sh`, add `REVOKE CONNECT, TEMPORARY ON DATABASE postgres FROM PUBLIC;`.
- The init script only runs on a fresh volume, so run `make db-reset && make migrate`, then the tests.
- Confirm the healthcheck, `make db` probe, and `make db-psql` all still work.
- Commit: `fix(infra): revoke public connect and temp on the postgres database`.

### F4. `feynman_app` must not read or write `alembic_version`
Default privileges currently give it `SELECT, INSERT, UPDATE, DELETE` on that table, so the app role could corrupt migration state.
- **Test first:** with the `app_connection` fixture, `SELECT * FROM alembic_version` and `UPDATE alembic_version SET version_num = 'x'` each raise `ProgrammingError` caused by `InsufficientPrivilegeError`.
- Fix: in `api/alembic/versions/0001_users.py` `upgrade()`, add `op.execute("REVOKE ALL ON TABLE alembic_version FROM feynman_app")`. This edits an unreleased migration, which is fine because nothing outside dev and CI has applied it. `downgrade()` needs no change (Alembic keeps the table). Add a short comment explaining why.
- Check that `test_upgrade_downgrade_upgrade` and `test_no_model_drift` still pass, and that the CI round trip (`upgrade head && downgrade base && upgrade head`) works locally against `feynman`.
- Commit: `fix(api): revoke app role access to alembic_version`.

### F5. Pin the health-check timeout path (Review Focus 2)
The existing DB-down test uses port 1, which refuses connections instantly. Nothing proves that a **hanging** DB returns 503 within the timeout.
- Add `test_health_db_timeout_returns_503` to `api/tests/test_health.py`: monkeypatch `feynman_api.routes.health._probe` with an async function that does `await asyncio.sleep(5)`. Use settings with `health_db_timeout_seconds=0.1`. Expect `503`, the body `{"status": "degraded", "db": "error", "version": "0.1.0"}`, and an elapsed time `< 1.0`.
- It should pass without code changes. If it doesn't, that's a real bug: fix it and record it.
- Commit: `test(api): pin health check timeout path`.

### F6. The status page must not treat every error response as a health body (`web/src/pages/StatusPage.tsx`)
Today any non-2xx body becomes "API: ok / Database: error"; a 500 error body even shows an empty version.
- **Tests first** in `StatusPage.test.tsx`:
  - `500` with body `{"error":{"code":"internal_error","message":"Internal server error","details":null}}` → shows `API error (HTTP 500)`, and **not** `API: ok`.
  - The existing 200, 503, and network-failure tests stay unchanged and green.
- Fix:
  - 2xx with `data` → as today.
  - `response.status === 503` and the error body has a `db` field → `API: ok` / `Database: error` (as today).
  - Any other non-2xx → `API error (HTTP <status>)`.
  - Network failure → `API unreachable` (as today).
  - `API error (HTTP <status>)` is new, orchestrator-approved UI copy. Use it exactly.
- `npm run lint && npm run format:check && npm run typecheck && npm test` → green.
- Commit: `fix(web): distinguish non-503 API errors on the status page`.

### F8. Hygiene (one commit)
- **python-dotenv:** `api/tests/conftest.py` imports it, but it's only a transitive dependency. Run `cd api && uv add --dev python-dotenv` (pre-approved), and commit the updated `pyproject.toml` and `uv.lock`.
- **CI double-runs:** in `.github/workflows/ci.yml`, change `push.branches` to `[main]` only and keep `pull_request`. PR branches are then covered by the `pull_request` event. The Task 8 verification command (`gh run list --branch phase-1-foundation`) still finds those runs.
- **Pin actions by commit SHA:** replace each `uses: owner/repo@tag` with `uses: owner/repo@<40-char sha> # <tag>`. Resolve each SHA with `gh api repos/<owner>/<repo>/commits/<tag> -q .sha` (this handles annotated tags), for `actions/checkout@v7`, `actions/setup-node@v7`, and `astral-sh/setup-uv@v10.3.3`. Show the resolved SHAs in your report.
- **Verify the gitleaks tarball in CI:** also download `gitleaks_8.30.1_checksums.txt` from the same release, and check the tarball with `sha256sum -c --ignore-missing` before extracting it. Fail the job if the check fails. Run the same commands locally in a scratch directory to prove they work.
- Commit: `chore: declare python-dotenv, run CI once per PR, pin actions by sha, verify gitleaks checksum`.

## Finish
1. `make check` → passes. Report the new test counts (expected: 36 + 4 pytest from F3/F4/F5, 7 + 1 vitest; give the actual numbers). Run `gitleaks git --redact -v .` → no leaks. `git log --all --name-only --format= | grep -E '(^|/)\.env($|\.)' | grep -v example` → no output.
2. **CI:** after the last push, run `gh run list --branch phase-1-foundation --limit 3`.
   - If runs still fail with "account is locked due to a billing issue", **don't** retry in a loop and **don't** claim green. Report it; the owner has to fix billing first.
   - If the runs actually execute, use `gh run watch --exit-status <id>`. Fix any genuine workflow failure in a follow-up commit (`ci: ...`), and repeat until green. Report the run URL.
3. **Update the PR body** (`gh pr edit 1 --body-file <tmpfile>`): add a "Fix-up round (orchestrator review)" section listing F2–F6 and F8 with their commits, tests, and evidence. Update the CI section with the current status. Remove the two "Decisions needed from the owner" items (both now resolved by F2/F3). Keep the closing `🤖 Generated with [Claude Code](https://claude.com/claude-code)` line.
4. **Update `memory.md`:** add a Session log entry "Implementation run: Phase 1 fix-ups" (what changed, test counts, CI status, deviations). In the Phase 1 entry, mark the resolved open items and deferred minors as resolved, with commit ids. Update §3 Repository state. Commit `docs: record phase 1 fix-up round`, run gitleaks, push.
5. Report to the owner:
   - the PR URL
   - the commits
   - the test counts
   - the CI status, with a link, or the billing-lock note
   - any deviations

   Then **stop**. The orchestrator re-reviews, and the owner merges.

If context gets large and the handoff hook fires, update `memory.md` with progress (fixes done, the current fix and step), then write `handoff-prompts/implementer/fixup/implementer-phase-1-fixups-resume-1.md` telling the next session where to resume.
