import uuid

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

NEW_TABLES = {
    "auth_sessions",
    "rate_limit_buckets",
    "study_sets",
    "flashcards",
    "documents",
    "document_pages",
    "jobs",
}


async def _user(s: AsyncSession) -> uuid.UUID:
    uid = uuid.uuid4()
    await s.execute(
        text("INSERT INTO users (id, email) VALUES (:id, :e)"),
        {"id": uid, "e": f"{uid}@example.com"},
    )
    return uid


async def _set(
    s: AsyncSession, uid: uuid.UUID, title: str = "t", desc: str | None = None
) -> uuid.UUID:
    sid = uuid.uuid4()
    await s.execute(
        text("INSERT INTO study_sets (id, user_id, title, description) VALUES (:i, :u, :t, :d)"),
        {"i": sid, "u": uid, "t": title, "d": desc},
    )
    return sid


async def _card(
    s: AsyncSession, sid: uuid.UUID, front: str = "f", back: str = "b", origin: str | None = None
) -> None:
    if origin is None:
        await s.execute(
            text("INSERT INTO flashcards (id, study_set_id, front, back) VALUES (:i, :s, :f, :b)"),
            {"i": uuid.uuid4(), "s": sid, "f": front, "b": back},
        )
    else:
        await s.execute(
            text(
                "INSERT INTO flashcards (id, study_set_id, front, back, origin) "
                "VALUES (:i, :s, :f, :b, :o)"
            ),
            {"i": uuid.uuid4(), "s": sid, "f": front, "b": back, "o": origin},
        )


async def _doc(s: AsyncSession, sid: uuid.UUID, status: str = "processing") -> uuid.UUID:
    did = uuid.uuid4()
    await s.execute(
        text(
            "INSERT INTO documents (id, study_set_id, storage_key, original_filename, "
            "size_bytes, status) VALUES (:i, :s, :k, 'a.pdf', 10, :st)"
        ),
        {"i": did, "s": sid, "k": uuid.uuid4().hex, "st": status},
    )
    return did


async def test_all_tables_exist(app_connection: AsyncConnection) -> None:
    names = await app_connection.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert NEW_TABLES <= names


@pytest.mark.parametrize("title", ["", "x" * 121])
async def test_study_set_title_check(db_session: AsyncSession, title: str) -> None:
    uid = await _user(db_session)
    with pytest.raises(IntegrityError, match="ck_study_sets_title_length"):
        await _set(db_session, uid, title=title)


async def test_study_set_description_check(db_session: AsyncSession) -> None:
    uid = await _user(db_session)
    await _set(db_session, uid, desc="x" * 1000)
    with pytest.raises(IntegrityError, match="ck_study_sets_description_length"):
        await _set(db_session, uid, desc="x" * 1001)


@pytest.mark.parametrize(
    ("front", "back"), [("", "b"), ("x" * 501, "b"), ("f", ""), ("f", "x" * 2001)]
)
async def test_flashcard_length_checks(db_session: AsyncSession, front: str, back: str) -> None:
    sid = await _set(db_session, await _user(db_session))
    with pytest.raises(IntegrityError, match="ck_flashcards_"):
        await _card(db_session, sid, front, back)


async def test_flashcard_origin_check(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    await _card(db_session, sid)
    row = await db_session.execute(text("SELECT origin FROM flashcards"))
    assert row.scalar_one() == "manual"
    with pytest.raises(IntegrityError, match="ck_flashcards_origin"):
        await _card(db_session, sid, origin="ai")


async def test_one_document_per_set(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    await _doc(db_session, sid)
    with pytest.raises(IntegrityError):
        await _doc(db_session, sid)


async def test_document_status_check(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    with pytest.raises(IntegrityError, match="ck_documents_status"):
        await _doc(db_session, sid, status="done")


async def test_job_status_check_and_defaults(db_session: AsyncSession) -> None:
    uid = await _user(db_session)
    await db_session.execute(
        text("INSERT INTO jobs (id, user_id, kind, payload) VALUES (:i, :u, 'k', '{}')"),
        {"i": uuid.uuid4(), "u": uid},
    )
    row = (
        await db_session.execute(text("SELECT status, attempts, max_attempts, run_after FROM jobs"))
    ).one()
    assert (row.status, row.attempts, row.max_attempts) == ("queued", 0, 3)
    assert row.run_after is not None
    with pytest.raises(IntegrityError, match="ck_jobs_status"):
        await db_session.execute(
            text(
                "INSERT INTO jobs (id, user_id, kind, payload, status) "
                "VALUES (:i, :u, 'k', '{}', 'bogus')"
            ),
            {"i": uuid.uuid4(), "u": uid},
        )


async def _auth_session(s: AsyncSession, uid: uuid.UUID, token_hash: bytes) -> None:
    await s.execute(
        text(
            "INSERT INTO auth_sessions (id, user_id, token_hash, csrf_token, last_seen_at, "
            "expires_at) VALUES (:i, :u, :h, 'c', now(), now())"
        ),
        {"i": uuid.uuid4(), "u": uid, "h": token_hash},
    )


async def test_session_token_hash_unique(db_session: AsyncSession) -> None:
    uid = await _user(db_session)
    await _auth_session(db_session, uid, b"h" * 32)
    with pytest.raises(IntegrityError):
        await _auth_session(db_session, uid, b"h" * 32)


async def test_user_delete_cascades_everything(db_session: AsyncSession) -> None:
    uid = await _user(db_session)
    await _auth_session(db_session, uid, b"a" * 32)
    sid = await _set(db_session, uid)
    await _card(db_session, sid)
    did = await _doc(db_session, sid)
    await db_session.execute(
        text("INSERT INTO document_pages (document_id, page_number, text) VALUES (:d, 1, 'x')"),
        {"d": did},
    )
    await db_session.execute(
        text("INSERT INTO jobs (id, user_id, kind, payload) VALUES (:i, :u, 'k', '{}')"),
        {"i": uuid.uuid4(), "u": uid},
    )
    await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": uid})
    for table in (
        "auth_sessions",
        "study_sets",
        "flashcards",
        "documents",
        "document_pages",
        "jobs",
    ):
        count = (await db_session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()  # noqa: S608
        assert count == 0, table
