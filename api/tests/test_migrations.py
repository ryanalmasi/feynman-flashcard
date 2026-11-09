import asyncio
import os
from typing import Any

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
    expected = set(Base.metadata.tables)
    assert asyncio.run(_tables(migration_url)) == expected
    try:
        command.downgrade(cfg, "base")
        assert asyncio.run(_tables(migration_url)) == set()
    finally:
        command.upgrade(cfg, "head")
    assert asyncio.run(_tables(migration_url)) == expected


def test_users_email_lower_index_is_unique(migrated_db: None, migration_url: str) -> None:
    async def indexes() -> dict[str, Any]:
        engine = create_async_engine(migration_url)
        try:
            async with engine.connect() as conn:
                return await conn.run_sync(
                    lambda c: {str(i["name"]): dict(i) for i in inspect(c).get_indexes("users")}
                )
        finally:
            await engine.dispose()

    by_name = asyncio.run(indexes())
    assert "uq_users_email_lower" in by_name
    assert by_name["uq_users_email_lower"]["unique"]


def test_no_model_drift(migrated_db: None, migration_url: str) -> None:
    assert asyncio.run(_diff(migration_url)) == []
