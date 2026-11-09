import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import asyncpg  # type: ignore[import-untyped]
import httpx
import pytest
from alembic.config import Config
from asgi_lifespan import LifespanManager
from dotenv import dotenv_values
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from alembic import command
from feynman_api.config import Settings
from feynman_api.main import create_app
from feynman_api.storage import LocalFileStore

API_DIR = Path(__file__).resolve().parent.parent
DB_HINT = "Test database is unreachable or not migrated. Run `make db` from the repo root first."


def _env(name: str) -> str | None:
    return os.environ.get(name) or dotenv_values(API_DIR / ".env").get(name)


def _test_database_url() -> str:
    return _env("TEST_DATABASE_URL") or "postgresql+asyncpg://x:x@127.0.0.1:1/x"


def _exception_chain(exc: BaseException) -> list[BaseException]:
    """The exception plus its __cause__/__context__ ancestors (cycle-safe)."""
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def alembic_config() -> Config:
    return Config(str(API_DIR / "alembic.ini"))


@pytest.fixture(scope="session")
def alembic_cfg() -> Config:
    return alembic_config()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        database_url=_test_database_url(),
        environment="test",
        _env_file=None,
    )


@pytest.fixture
def file_store(tmp_path: Path) -> LocalFileStore:
    root = tmp_path / "uploads"
    root.mkdir()
    return LocalFileStore(root)


@pytest.fixture
def app(migrated_db: None, test_settings: Settings, file_store: LocalFileStore) -> FastAPI:
    return create_app(test_settings, file_store=file_store)


@pytest.fixture
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture(scope="session")
def migration_url() -> str:
    url = _env("TEST_MIGRATION_DATABASE_URL")
    if not url:
        pytest.fail("TEST_MIGRATION_DATABASE_URL is not set. Run `make env` and `make db`.")
    return url


@pytest.fixture(scope="session")
def migrated_db(migration_url: str, alembic_cfg: Config) -> Iterator[None]:
    """Run `alembic upgrade head` on feynman_test as the migrator role."""
    previous = os.environ.get("MIGRATION_DATABASE_URL")
    os.environ["MIGRATION_DATABASE_URL"] = migration_url
    try:
        try:
            command.upgrade(alembic_cfg, "head")
        except Exception as exc:
            # Never include str(exc) or the URL: they may carry credentials.
            chain = _exception_chain(exc)
            hint = DB_HINT
            if any(isinstance(e, asyncpg.InvalidPasswordError) for e in chain):
                hint += " Credentials rejected: run `make db-reset` (DELETES local DB data)."
            pytest.fail(f"{hint} ({type(chain[-1]).__name__})", pytrace=False)
        yield
    finally:
        if previous is None:
            os.environ.pop("MIGRATION_DATABASE_URL", None)
        else:
            os.environ["MIGRATION_DATABASE_URL"] = previous


@pytest.fixture
async def db_session(migrated_db: None, test_settings: Settings) -> AsyncIterator[AsyncSession]:
    """feynman_app session inside a transaction that is rolled back at teardown."""
    engine = create_async_engine(test_settings.database_url.get_secret_value())
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
async def app_connection(
    migrated_db: None, test_settings: Settings
) -> AsyncIterator[AsyncConnection]:
    """A fresh feynman_app connection, for privilege checks."""
    engine = create_async_engine(test_settings.database_url.get_secret_value())
    try:
        async with engine.connect() as conn:
            yield conn
    finally:
        await engine.dispose()


async def _truncate(migration_url: str) -> None:
    # Test-only use of the migrator: the app role has no TRUNCATE privilege.
    engine = create_async_engine(migration_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("TRUNCATE users, jobs, rate_limit_buckets RESTART IDENTITY CASCADE")
            )
    finally:
        await engine.dispose()


@pytest.fixture
async def clean_db(migrated_db: None, migration_url: str) -> AsyncIterator[None]:
    """Empty the data tables before and after a test that commits data."""
    await _truncate(migration_url)
    try:
        yield
    finally:
        await _truncate(migration_url)


@pytest.fixture
async def db(clean_db: None, test_settings: Settings) -> AsyncIterator[AsyncSession]:
    """Plain feynman_app session (not rolled back), for setup rows and committed-state asserts."""
    engine = create_async_engine(test_settings.database_url.get_secret_value())
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
    finally:
        await engine.dispose()
