# 0008. Background jobs: Postgres-backed queue + worker

- **Status:** Accepted (owner, 2026-11-08)

## Context
PDF ingest, Knowledge Map extraction, and grading take from seconds to a minute. They must survive restarts and retry on failure.

## Options
1. **Postgres-backed queue + a separate worker process.** Jobs are rows claimed with `FOR UPDATE SKIP LOCKED`, with retries. No new infrastructure.
2. Redis + arq/Celery. Battle-tested, but it brings back Redis, which was removed (0005).
3. FastAPI in-process `BackgroundTasks`. Jobs are lost on restart and there are no retries.

## Decision
Option 1. **It is built in the Phase 2 PDF milestone, not in Phase 1** (nothing in Phase 1 needs it). The Phase 2 plan will choose between the `procrastinate` library and a small hand-rolled `jobs` table. Either way the job's status is visible to the UI by polling or streaming.
