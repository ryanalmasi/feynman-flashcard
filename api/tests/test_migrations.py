import asyncio
import os

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from feynman_api.models import Base


async def _tables(url: str) -> set[str]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
    finally:
        await engine.dispose()
    return names - {"alembic_version"}


async def _diff(url: str) -> list[object]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(
                lambda c: compare_metadata(MigrationContext.configure(c), Base.metadata)
            )
    finally:
        await engine.dispose()


def test_upgrade_downgrade_upgrade(
    migrated_db: None, migration_url: str, alembic_cfg: Config
) -> None:
    cfg = alembic_cfg
    os.environ["MIGRATION_DATABASE_URL"] = migration_url
    assert asyncio.run(_tables(migration_url)) == {"users", "auth_identities"}
    command.downgrade(cfg, "base")
    assert asyncio.run(_tables(migration_url)) == set()
    command.upgrade(cfg, "head")
    assert asyncio.run(_tables(migration_url)) == {"users", "auth_identities"}


def test_no_model_drift(migrated_db: None, migration_url: str) -> None:
    assert asyncio.run(_diff(migration_url)) == []
