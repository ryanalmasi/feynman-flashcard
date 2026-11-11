import logging
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from conftest import auth_headers
from fastapi import FastAPI
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.models import Document, DocumentPage, Flashcard, KnowledgeMap
from feynman_api.storage import LocalFileStore, new_storage_key

pytestmark = pytest.mark.usefixtures("clean_db")


async def _make_set(
    client: httpx.AsyncClient, title: str = "Biology", **kw: object
) -> dict[str, Any]:
    r = await client.post(
        "/study-sets", json={"title": title, **kw}, headers=await auth_headers(client)
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


async def _add_document(
    client: httpx.AsyncClient, db: AsyncSession, file_store: LocalFileStore, set_id: str
) -> tuple[uuid.UUID, str]:
    key = new_storage_key()

    async def chunks() -> AsyncIterator[bytes]:
        yield b"%PDF-fake"

    await file_store.put(key, chunks())
    doc = Document(
        study_set_id=uuid.UUID(set_id),
        storage_key=key,
        original_filename="a.pdf",
        size_bytes=9,
        status="ready",
        page_count=1,
    )
    db.add(doc)
    await db.flush()
    db.add(DocumentPage(document_id=doc.id, page_number=1, text="hi"))
    await db.commit()
    return doc.id, key


async def test_create_list_get_update_delete_set(user_client: httpx.AsyncClient) -> None:
    h = await auth_headers(user_client)
    first = await _make_set(user_client, "First")
    second = await _make_set(user_client, "Second", description="d")
    assert first["card_count"] == 0 and first["document"] is None
    assert second["description"] == "d"
    await user_client.post(
        f"/study-sets/{first['id']}/flashcards", json={"front": "f", "back": "b"}, headers=h
    )
    listed = (await user_client.get("/study-sets")).json()
    assert [s["title"] for s in listed] == ["Second", "First"]
    assert [s["card_count"] for s in listed] == [0, 1]
    assert all(s["document"] is None for s in listed)
    got = await user_client.get(f"/study-sets/{first['id']}")
    assert got.status_code == 200 and got.json()["card_count"] == 1
    r = await user_client.patch(f"/study-sets/{first['id']}", json={"title": "Renamed"}, headers=h)
    assert r.status_code == 200 and r.json()["title"] == "Renamed"
    r = await user_client.delete(f"/study-sets/{first['id']}", headers=h)
    assert r.status_code == 204 and r.content == b""
    assert (await user_client.get(f"/study-sets/{first['id']}")).status_code == 404


@pytest.mark.parametrize(
    ("title", "ok"), [("", False), ("   ", False), ("x" * 121, False), ("x" * 120, True)]
)
async def test_set_title_validation(user_client: httpx.AsyncClient, title: str, ok: bool) -> None:
    r = await user_client.post(
        "/study-sets", json={"title": title}, headers=await auth_headers(user_client)
    )
    assert r.status_code == (201 if ok else 422)
    if not ok:
        assert r.json()["error"]["code"] == "validation_error"


async def test_patch_description_null_clears(user_client: httpx.AsyncClient) -> None:
    h = await auth_headers(user_client)
    s = await _make_set(user_client, description="keep")
    r = await user_client.patch(f"/study-sets/{s['id']}", json={"title": "T2"}, headers=h)
    assert r.json()["description"] == "keep"
    r = await user_client.patch(f"/study-sets/{s['id']}", json={"description": None}, headers=h)
    assert r.json()["description"] is None and r.json()["title"] == "T2"
    r = await user_client.patch(f"/study-sets/{s['id']}", json={"title": None}, headers=h)
    assert r.status_code == 422


async def test_delete_set_removes_cards_document_pages_and_file(
    user_client: httpx.AsyncClient, file_store: LocalFileStore, db: AsyncSession, tmp_path: Path
) -> None:
    h = await auth_headers(user_client)
    s = await _make_set(user_client)
    await user_client.post(
        f"/study-sets/{s['id']}/flashcards", json={"front": "f", "back": "b"}, headers=h
    )
    doc_id, key = await _add_document(user_client, db, file_store, s["id"])
    listed = (await user_client.get("/study-sets")).json()
    assert listed[0]["document"] == {
        "id": str(doc_id),
        "status": "ready",
        "page_count": 1,
        "original_filename": "a.pdf",
        "error_message": None,
    }
    assert (tmp_path / "uploads" / key).exists()
    r = await user_client.delete(f"/study-sets/{s['id']}", headers=h)
    assert r.status_code == 204
    db.expire_all()
    for model in (Document, DocumentPage):
        assert (await db.execute(select(func.count()).select_from(model))).scalar_one() == 0
    assert not (tmp_path / "uploads" / key).exists()
    assert (await user_client.get(f"/study-sets/{s['id']}/flashcards")).status_code == 404


async def test_delete_set_file_delete_failure_is_logged_not_raised(
    user_client: httpx.AsyncClient,
    file_store: LocalFileStore,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    h = await auth_headers(user_client)
    s = await _make_set(user_client)
    _, key = await _add_document(user_client, db, file_store, s["id"])

    async def boom(_key: str) -> None:
        raise OSError("secret path detail")

    monkeypatch.setattr(file_store, "delete", boom)
    with caplog.at_level(logging.WARNING):
        r = await user_client.delete(f"/study-sets/{s['id']}", headers=h)
    assert r.status_code == 204
    assert any(key in m and "OSError" in m for m in caplog.messages)
    assert "secret path detail" not in caplog.text
    assert (await user_client.get(f"/study-sets/{s['id']}")).status_code == 404


async def test_list_sets_requires_auth(api_client: httpx.AsyncClient) -> None:
    r = await api_client.get("/study-sets")
    assert r.status_code == 401 and r.json()["error"]["code"] == "not_authenticated"


async def test_list_sets_is_one_query(user_client: httpx.AsyncClient, app: FastAPI) -> None:
    statements: list[str] = []

    def count(conn: Any, cursor: Any, statement: str, *a: Any) -> None:
        statements.append(statement)

    engine = app.state.engine.sync_engine
    event.listen(engine, "before_cursor_execute", count)
    try:
        await _make_set(user_client, "one")
        statements.clear()
        await user_client.get("/study-sets")
        baseline = len(statements)
        for i in range(4):
            s = await _make_set(user_client, f"s{i}")
            await user_client.post(
                f"/study-sets/{s['id']}/flashcards",
                json={"front": "f", "back": "b"},
                headers=await auth_headers(user_client),
            )
        statements.clear()
        r = await user_client.get("/study-sets")
        assert len(r.json()) == 5
        assert len(statements) == baseline
        assert sum("study_sets" in s for s in statements) == 1
    finally:
        event.remove(engine, "before_cursor_execute", count)


async def test_nul_character_rejected_with_422(user_client: httpx.AsyncClient) -> None:
    h = await auth_headers(user_client)
    r = await user_client.post("/study-sets", json={"title": "a\x00b"}, headers=h)
    assert r.status_code == 422
    r = await user_client.post(
        "/study-sets", json={"title": "ok", "description": "a\x00b"}, headers=h
    )
    assert r.status_code == 422
    s = await user_client.post("/study-sets", json={"title": "ok"}, headers=h)
    sid = s.json()["id"]
    r = await user_client.patch(f"/study-sets/{sid}", json={"title": "a\x00b"}, headers=h)
    assert r.status_code == 422
    for body in ({"front": "a\x00", "back": "b"}, {"front": "a", "back": "b\x00"}):
        r = await user_client.post(f"/study-sets/{sid}/flashcards", json=body, headers=h)
        assert r.status_code == 422


async def _seed_map(db: AsyncSession, set_id: str, *, cards_status: str = "idle") -> None:
    doc = Document(
        study_set_id=uuid.UUID(set_id),
        storage_key=uuid.uuid4().hex,
        original_filename="lesson.pdf",
        size_bytes=1,
        status="ready",
        page_count=1,
    )
    db.add(doc)
    await db.flush()
    db.add(
        KnowledgeMap(
            study_set_id=uuid.UUID(set_id),
            document_id=doc.id,
            status="ready",
            cards_status=cards_status,
        )
    )
    await db.commit()


async def test_card_count_counts_only_accepted(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    h = await auth_headers(user_client)
    s = await _make_set(user_client)
    empty = await _make_set(user_client, "Empty")
    assert s["card_count"] == 0 and s["suggested_count"] == 0
    await user_client.post(
        f"/study-sets/{s['id']}/flashcards", json={"front": "f", "back": "b"}, headers=h
    )
    db.add(
        Flashcard(
            study_set_id=uuid.UUID(s["id"]),
            front="g",
            back="b",
            origin="generated",
            status="accepted",
        )
    )
    for i in range(3):
        db.add(
            Flashcard(
                study_set_id=uuid.UUID(s["id"]),
                front=f"s{i}",
                back="b",
                origin="generated",
                status="suggested",
            )
        )
    await db.commit()
    got = (await user_client.get(f"/study-sets/{s['id']}")).json()
    assert got["card_count"] == 2 and got["suggested_count"] == 3
    listed = {x["id"]: x for x in (await user_client.get("/study-sets")).json()}
    assert (listed[s["id"]]["card_count"], listed[s["id"]]["suggested_count"]) == (2, 3)
    assert (listed[empty["id"]]["card_count"], listed[empty["id"]]["suggested_count"]) == (0, 0)


async def test_set_out_has_map_summary(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    plain = await _make_set(user_client, "Plain")
    assert plain["knowledge_map"] is None
    mapped = await _make_set(user_client, "Mapped")
    await _seed_map(db, mapped["id"], cards_status="processing")
    got = (await user_client.get(f"/study-sets/{mapped['id']}")).json()
    assert got["knowledge_map"] == {"status": "ready", "cards_status": "processing"}
    listed = {x["id"]: x for x in (await user_client.get("/study-sets")).json()}
    assert listed[plain["id"]]["knowledge_map"] is None
    assert listed[mapped["id"]]["knowledge_map"] == {
        "status": "ready",
        "cards_status": "processing",
    }
