# 0015. Job queue: own `jobs` table and worker (implements ADR 0008)

- **Status:** Accepted (owner, 2026-11-09)

## Context
ADR 0008 chose a Postgres-backed queue with a separate worker process and left "procrastinate vs hand-rolled" to Phase 2. MVP job kinds are few (PDF text extraction in 2a; Knowledge Map, flashcard generation, scoring later) and volume is tiny. Versions and dependencies checked 2026-11-09.

## Options
1. **Own `jobs` table + worker loop.** Claim with `SELECT … FOR UPDATE SKIP LOCKED`, retries with backoff, lease expiry for crashed workers.
2. procrastinate 3.10: mature, retries, cron, admin CLI. Requires `psycopg[pool]` (a second Postgres driver next to asyncpg) and ships its own schema and SQL functions that would need fitting into Alembic and the `feynman_app` grants.
3. pgqueuer 1.6: asyncpg-capable, newer, smaller community, pulls in typer/tabulate/uvloop and more.

## Decision
Option 1.
- Table `jobs` (created by an Alembic migration, owned by the migrator; `feynman_app` gets DML through the existing default privileges): at least `id`, `user_id` (FK, cascade), `kind`, `payload jsonb`, `status` (`queued|running|succeeded|failed`), `attempts`, `max_attempts`, `run_after`, `locked_until`, `last_error` (a short, sanitised message; never a stack trace or secret), `result jsonb`, timestamps. Exact columns are fixed in the Phase 2a plan.
- Worker: a separate process (`make worker`, `python -m feynman_api.worker`) that connects as `feynman_app`, claims one job at a time with `FOR UPDATE SKIP LOCKED`, takes a lease (`locked_until`), and on failure retries with exponential backoff up to `max_attempts`. A job whose lease expires is claimable again (crash recovery). Handlers are registered per `kind` and must be idempotent.
- Waking: polling with a short interval is enough for the MVP; `LISTEN/NOTIFY` is an optional optimisation, not required.
- The UI reads job status from the API (polling) for the user's own jobs only.

## Consequences
About 200 lines plus tests that we own; no new dependency or driver. If cron-style scheduling or high volume is ever needed, revisit procrastinate in a new ADR.
