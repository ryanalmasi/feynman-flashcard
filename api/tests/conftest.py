import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from dotenv import dotenv_values
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from alembic import command
from feynman_api.config import Settings
from feynman_api.main import create_app

API_DIR = Path(__file__).resolve().parent.parent
DB_HINT = "Test database is unreachable or not migrated. Run `make db` from the repo root first."


def _env(name: str) -> str | None:
    return os.environ.get(name) or dotenv_values(API_DIR / ".env").get(name)


def _test_database_url() -> str:
    return _env("TEST_DATABASE_URL") or "postgresql+asyncpg://x:x@127.0.0.1:1/x"


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
def app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


@pytest.fixture
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
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
    os.environ["MIGRATION_DATABASE_URL"] = migration_url
    try:
        command.upgrade(alembic_cfg, "head")
    except OSError as exc:
        pytest.fail(f"{DB_HINT} ({type(exc).__name__})")
    yield


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
