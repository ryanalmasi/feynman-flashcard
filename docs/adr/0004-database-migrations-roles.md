# 0004. Postgres 18, SQLAlchemy 2 async + Alembic, least-privilege roles

- **Status:** Accepted (owner, 2026-11-08)

## Context
The owner wants Postgres with the most secure, minimal setup (planning doc §3.4). The prototype used `db.create_all()`, had no migrations, and enforced uniqueness only in code.

## Options (data access)
1. **SQLAlchemy 2.0 async (asyncpg) + Alembic.** Mature, gives full control over constraints and indexes, and async suits the streaming and LLM paths.
2. SQLModel + Alembic. Less boilerplate, but it lags SQLAlchemy and gets awkward with complex queries.
3. Raw SQL + psycopg. Maximum control, but migrations are hand-written and there is no ORM safety net.

## Decision
- **Postgres 18** in Docker Compose for dev and CI. The port binds to `127.0.0.1` only. Hosting is decided at deployment (Phase 3); nothing may tie us to one vendor.
- **SQLAlchemy 2.0 async + asyncpg; Alembic** for every schema change. No `create_all()` in app code.
- **Roles, created by an init script:**
  - `feynman_migrator` owns the schema and runs Alembic.
  - `feynman_app` gets only `SELECT, INSERT, UPDATE, DELETE` on tables and `USAGE, SELECT` on sequences, via `ALTER DEFAULT PRIVILEGES FOR ROLE feynman_migrator`. It has no DDL rights, isn't a superuser, and doesn't own anything.
  - The API connects **only** as `feynman_app`. The superuser (`postgres`) is used only by the init script.
- No extensions in Phase 1. `pgvector` is considered only if embeddings are stored in the DB.
- Conventions: `uuid` primary keys generated in Python (`uuid4`), `timestamptz` for all timestamps, and real DB constraints (unique, FK, not-null) for every invariant.
- Row ownership: every user-owned query filters by `user_id`. This is enforced from Phase 2 and tested.

## Consequences
A test verifies that `feynman_app` **cannot** run DDL (e.g. `CREATE TABLE`) and **can** read and write app tables. Alembic migrations must be reversible (an up/down check runs in CI).
