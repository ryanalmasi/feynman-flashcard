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
    with pytest.raises(IntegrityError, match=r'constraint "ck_study_sets_title_length"'):
        await _set(db_session, uid, title=title)


async def test_study_set_description_check(db_session: AsyncSession) -> None:
    uid = await _user(db_session)
    await _set(db_session, uid, desc="x" * 1000)
    with pytest.raises(IntegrityError, match=r'constraint "ck_study_sets_description_length"'):
        await _set(db_session, uid, desc="x" * 1001)


@pytest.mark.parametrize(
    ("front", "back"), [("", "b"), ("x" * 501, "b"), ("f", ""), ("f", "x" * 2001)]
)
async def test_flashcard_length_checks(db_session: AsyncSession, front: str, back: str) -> None:
    sid = await _set(db_session, await _user(db_session))
    with pytest.raises(IntegrityError, match=r'constraint "ck_flashcards_(front|back)_length"'):
        await _card(db_session, sid, front, back)


async def test_flashcard_origin_check(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    await _card(db_session, sid)
    row = await db_session.execute(text("SELECT origin FROM flashcards"))
    assert row.scalar_one() == "manual"
    with pytest.raises(IntegrityError, match=r'constraint "ck_flashcards_origin"'):
        await _card(db_session, sid, origin="ai")


async def test_one_document_per_set(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    await _doc(db_session, sid)
    with pytest.raises(IntegrityError):
        await _doc(db_session, sid)


async def test_document_status_check(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    with pytest.raises(IntegrityError, match=r'constraint "ck_documents_status"'):
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
    with pytest.raises(IntegrityError, match=r'constraint "ck_jobs_status"'):
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


async def test_check_constraint_names_exact(app_connection: AsyncConnection) -> None:
    rows = await app_connection.execute(
        text(
            "SELECT conname FROM pg_constraint WHERE contype = 'c' "
            "AND connamespace = 'public'::regnamespace ORDER BY conname"
        )
    )
    assert {r[0] for r in rows} == {
        "ck_study_sets_title_length",
        "ck_study_sets_description_length",
        "ck_flashcards_front_length",
        "ck_flashcards_back_length",
        "ck_flashcards_origin",
        "ck_documents_status",
        "ck_documents_original_filename_length",
        "ck_jobs_status",
        "ck_knowledge_maps_status",
        "ck_knowledge_maps_cards_status",
        "ck_concepts_title_length",
        "ck_concepts_explanation_length",
        "ck_concepts_importance",
        "ck_knowledge_map_chunks_status",
        "ck_flashcards_kind",
        "ck_flashcards_status",
    }


@pytest.mark.parametrize("name", ["", "x" * 256])
async def test_document_filename_length_check(db_session: AsyncSession, name: str) -> None:
    sid = await _set(db_session, await _user(db_session))
    with pytest.raises(IntegrityError, match='constraint "ck_documents_original_filename_length"'):
        await db_session.execute(
            text(
                "INSERT INTO documents (id, study_set_id, storage_key, original_filename, "
                "size_bytes, status) VALUES (:i, :s, :k, :n, 1, 'ready')"
            ),
            {"i": uuid.uuid4(), "s": sid, "k": uuid.uuid4().hex, "n": name},
        )


async def _map(s: AsyncSession, sid: uuid.UUID) -> uuid.UUID:
    did = await _doc(s, sid, status="ready")
    mid = uuid.uuid4()
    await s.execute(
        text(
            "INSERT INTO knowledge_maps (id, study_set_id, document_id, status) "
            "VALUES (:i, :s, :d, 'ready')"
        ),
        {"i": mid, "s": sid, "d": did},
    )
    return mid


async def _concept(
    s: AsyncSession,
    mid: uuid.UUID,
    position: int = 0,
    title: str = "t",
    explanation: str = "e",
    importance: str = "core",
) -> uuid.UUID:
    cid = uuid.uuid4()
    await s.execute(
        text(
            "INSERT INTO concepts (id, knowledge_map_id, position, title, explanation, "
            "importance) VALUES (:i, :m, :p, :t, :e, :im)"
        ),
        {"i": cid, "m": mid, "p": position, "t": title, "e": explanation, "im": importance},
    )
    return cid


async def test_concept_position_unique_is_deferred(db_session: AsyncSession) -> None:
    mid = await _map(db_session, await _set(db_session, await _user(db_session)))
    a = await _concept(db_session, mid, 0)
    b = await _concept(db_session, mid, 1)
    upd = text("UPDATE concepts SET position = :p WHERE id = :i")
    await db_session.execute(upd, {"p": 1, "i": a})
    await db_session.execute(upd, {"p": 0, "i": b})
    await db_session.flush()
    await db_session.execute(upd, {"p": 0, "i": a})
    with pytest.raises(IntegrityError, match="uq_concepts_map_position"):
        await db_session.execute(text("SET CONSTRAINTS uq_concepts_map_position IMMEDIATE"))


async def test_one_map_per_set(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    await _map(db_session, sid)
    with pytest.raises(IntegrityError):
        await _map(db_session, sid)


@pytest.mark.parametrize(
    ("field", "value", "name"),
    [
        ("title", "", "ck_concepts_title_length"),
        ("title", "x" * 121, "ck_concepts_title_length"),
        ("explanation", "x" * 2001, "ck_concepts_explanation_length"),
        ("importance", "x", "ck_concepts_importance"),
    ],
)
async def test_concept_checks(db_session: AsyncSession, field: str, value: str, name: str) -> None:
    mid = await _map(db_session, await _set(db_session, await _user(db_session)))
    with pytest.raises(IntegrityError, match=f'constraint "{name}"'):
        await _concept(db_session, mid, **{field: value})  # type: ignore[arg-type]


async def test_flashcard_cloze_back_may_be_empty(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    ins = text(
        "INSERT INTO flashcards (id, study_set_id, front, back, kind) VALUES (:i, :s, 'f', '', :k)"
    )
    await db_session.execute(ins, {"i": uuid.uuid4(), "s": sid, "k": "cloze"})
    with pytest.raises(IntegrityError, match=r'constraint "ck_flashcards_back_length"'):
        await db_session.execute(ins, {"i": uuid.uuid4(), "s": sid, "k": "qa"})


async def test_flashcard_new_defaults(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    await _card(db_session, sid)
    row = (
        await db_session.execute(text("SELECT kind, status, edited, concept_id FROM flashcards"))
    ).one()
    assert (row.kind, row.status, row.edited, row.concept_id) == ("qa", "accepted", False, None)


@pytest.mark.parametrize("col", ["kind", "status"])
async def test_flashcard_kind_and_status_checks(db_session: AsyncSession, col: str) -> None:
    sid = await _set(db_session, await _user(db_session))
    # An unknown kind also fails back_length (neither branch matches); Postgres may report either.
    pattern = (
        r'constraint "ck_flashcards_(kind|back_length)"'
        if col == "kind"
        else (r'constraint "ck_flashcards_status"')
    )
    with pytest.raises(IntegrityError, match=pattern):
        await db_session.execute(
            text(
                f"INSERT INTO flashcards (id, study_set_id, front, back, {col}) "  # noqa: S608
                "VALUES (:i, :s, 'f', 'b', 'x')"
            ),
            {"i": uuid.uuid4(), "s": sid},
        )


async def test_concept_delete_unlinks_cards(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    mid = await _map(db_session, sid)
    cid = await _concept(db_session, mid)
    await db_session.execute(
        text(
            "INSERT INTO flashcards (id, study_set_id, front, back, concept_id) "
            "VALUES (:i, :s, 'f', 'b', :c)"
        ),
        {"i": uuid.uuid4(), "s": sid, "c": cid},
    )
    await db_session.execute(text("DELETE FROM concepts WHERE id = :c"), {"c": cid})
    row = (await db_session.execute(text("SELECT concept_id FROM flashcards"))).all()
    assert len(row) == 1
    assert row[0].concept_id is None


_CHUNK = (
    "INSERT INTO knowledge_map_chunks (knowledge_map_id, chunk_index, page_start, page_end, "
    "status) VALUES (:m, :n, 1, 2, :st)"
)


async def test_chunk_status_check(db_session: AsyncSession) -> None:
    mid = await _map(db_session, await _set(db_session, await _user(db_session)))
    with pytest.raises(IntegrityError, match='constraint "ck_knowledge_map_chunks_status"'):
        await db_session.execute(text(_CHUNK), {"m": mid, "n": 0, "st": "x"})


async def test_set_delete_cascades_map(db_session: AsyncSession) -> None:
    sid = await _set(db_session, await _user(db_session))
    mid = await _map(db_session, sid)
    await _concept(db_session, mid)
    await db_session.execute(text(_CHUNK), {"m": mid, "n": 0, "st": "pending"})
    await db_session.execute(text("DELETE FROM study_sets WHERE id = :s"), {"s": sid})
    for table in ("knowledge_maps", "concepts", "knowledge_map_chunks"):
        count = (await db_session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()  # noqa: S608
        assert count == 0, table
