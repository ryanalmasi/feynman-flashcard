import uuid

import pytest
from asyncpg.exceptions import InsufficientPrivilegeError  # type: ignore[import-untyped]
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from feynman_api.config import Settings
from feynman_api.models import AuthIdentity, User


async def test_app_can_insert_and_select_user(db_session: AsyncSession) -> None:
    db_session.add(User(email="a@example.com", password_hash="h"))  # noqa: S106
    await db_session.flush()
    row = (await db_session.execute(text("SELECT email FROM users"))).scalar_one()
    assert row == "a@example.com"


@pytest.mark.parametrize(
    "statement",
    ["CREATE TABLE x(i int)", "CREATE SCHEMA s"],
)
async def test_app_cannot_create_objects(app_connection: AsyncConnection, statement: str) -> None:
    with pytest.raises(ProgrammingError) as exc:
        await app_connection.execute(text(statement))
    assert isinstance(exc.value.orig.__cause__, InsufficientPrivilegeError)  # type: ignore[union-attr]


@pytest.mark.parametrize("statement", ["ALTER TABLE users ADD COLUMN z int", "DROP TABLE users"])
async def test_app_cannot_alter_or_drop_users(
    app_connection: AsyncConnection, statement: str
) -> None:
    with pytest.raises(ProgrammingError) as exc:
        await app_connection.execute(text(statement))
    assert isinstance(exc.value.orig.__cause__, InsufficientPrivilegeError)  # type: ignore[union-attr]


async def test_email_unique_case_insensitive(db_session: AsyncSession) -> None:
    db_session.add(User(email="A@x.com"))
    await db_session.flush()
    db_session.add(User(email="a@X.com"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_password_hash_nullable(db_session: AsyncSession) -> None:
    user = User(email="nopw@example.com", password_hash=None)
    db_session.add(user)
    await db_session.flush()
    assert user.password_hash is None


async def test_identity_unique_provider_subject(db_session: AsyncSession) -> None:
    u1 = User(email="u1@example.com")
    u2 = User(email="u2@example.com")
    db_session.add_all([u1, u2])
    await db_session.flush()
    db_session.add(AuthIdentity(user_id=u1.id, provider="google", provider_subject="123"))
    await db_session.flush()
    db_session.add(AuthIdentity(user_id=u2.id, provider="google", provider_subject="123"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_identity_cascade_on_user_delete(db_session: AsyncSession) -> None:
    user = User(email="c@example.com")
    db_session.add(user)
    await db_session.flush()
    user_id: uuid.UUID = user.id
    db_session.add(AuthIdentity(user_id=user_id, provider="google", provider_subject="9"))
    await db_session.flush()
    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    count = (
        await db_session.execute(
            text("SELECT count(*) FROM auth_identities WHERE user_id = :id"), {"id": user_id}
        )
    ).scalar_one()
    assert count == 0


async def test_app_cannot_connect_to_postgres_database(
    migrated_db: None, test_settings: Settings
) -> None:
    url = make_url(test_settings.database_url.get_secret_value()).set(database="postgres")
    engine = create_async_engine(url)
    try:
        with pytest.raises(Exception) as exc:
            async with engine.connect():
                pass
    finally:
        await engine.dispose()
    causes: list[BaseException] = []
    current: BaseException | None = exc.value
    while current is not None and current not in causes:
        causes.append(current)
        current = current.__cause__ or current.__context__
    assert any(isinstance(c, InsufficientPrivilegeError) for c in causes)
