import uuid
from typing import Any

import httpx
import pytest
from conftest import FrozenClock, auth_headers
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.models import Concept, Document, Flashcard, Job, KnowledgeMap

pytestmark = pytest.mark.usefixtures("clean_db")


async def _set(client: httpx.AsyncClient) -> str:
    r = await client.post("/study-sets", json={"title": "S"}, headers=await auth_headers(client))
    return str(r.json()["id"])


async def test_card_crud_and_order(user_client: httpx.AsyncClient) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    ids = []
    for i in range(3):
        r = await user_client.post(
            f"/study-sets/{sid}/flashcards", json={"front": f"f{i}", "back": f"b{i}"}, headers=h
        )
        assert r.status_code == 201
        ids.append(r.json()["id"])
        assert r.json()["study_set_id"] == sid
    listed = (await user_client.get(f"/study-sets/{sid}/flashcards")).json()
    assert [c["id"] for c in listed] == ids
    r = await user_client.patch(f"/flashcards/{ids[0]}", json={"front": "new"}, headers=h)
    assert r.status_code == 200 and r.json()["front"] == "new" and r.json()["back"] == "b0"
    r = await user_client.delete(f"/flashcards/{ids[1]}", headers=h)
    assert r.status_code == 204
    listed = (await user_client.get(f"/study-sets/{sid}/flashcards")).json()
    assert [c["id"] for c in listed] == [ids[0], ids[2]]
    count = (await user_client.get(f"/study-sets/{sid}")).json()["card_count"]
    assert count == 2


async def test_card_preserves_line_breaks(user_client: httpx.AsyncClient) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    r = await user_client.post(
        f"/study-sets/{sid}/flashcards", json={"front": "a\nb", "back": " x\n\ny "}, headers=h
    )
    assert r.json()["front"] == "a\nb" and r.json()["back"] == " x\n\ny "
    cid = r.json()["id"]
    r = await user_client.patch(f"/flashcards/{cid}", json={"back": "p\nq"}, headers=h)
    assert r.json()["back"] == "p\nq"
    listed = (await user_client.get(f"/study-sets/{sid}/flashcards")).json()
    assert listed[0]["front"] == "a\nb" and listed[0]["back"] == "p\nq"


@pytest.mark.parametrize(
    ("front", "back"), [("", "b"), ("  ", "b"), ("x" * 501, "b"), ("f", "x" * 2001), ("f", " \n ")]
)
async def test_card_validation(user_client: httpx.AsyncClient, front: str, back: str) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    r = await user_client.post(
        f"/study-sets/{sid}/flashcards", json={"front": front, "back": back}, headers=h
    )
    assert r.status_code == 422
    ok = await user_client.post(
        f"/study-sets/{sid}/flashcards", json={"front": "f", "back": "b"}, headers=h
    )
    r = await user_client.patch(
        f"/flashcards/{ok.json()['id']}", json={"front": front, "back": back}, headers=h
    )
    assert r.status_code == 422


async def test_card_origin_is_manual(user_client: httpx.AsyncClient) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    r = await user_client.post(
        f"/study-sets/{sid}/flashcards",
        json={"front": "f", "back": "b", "origin": "generated"},
        headers=h,
    )
    assert r.status_code == 201 and r.json()["origin"] == "manual"


# --- Phase 2b: kinds, suggested cards, generate, accept/reject -------------------------------

CLOZE_MSG = "Cloze cards need exactly one {{answer}}."
MAP_PROCESSING = "The Knowledge Map is still being built."
MAP_NOT_READY = "The Knowledge Map isn't ready."
CARDS_PROCESSING = "Flashcards are already being generated."


async def _map(
    db: AsyncSession,
    set_id: str,
    *,
    status: str = "ready",
    cards_status: str = "idle",
    n_concepts: int = 2,
) -> tuple[KnowledgeMap, list[Concept]]:
    doc = Document(
        study_set_id=uuid.UUID(set_id),
        storage_key=uuid.uuid4().hex,
        original_filename="lesson.pdf",
        size_bytes=1,
        status="ready",
        page_count=3,
    )
    db.add(doc)
    await db.flush()
    km = KnowledgeMap(
        study_set_id=uuid.UUID(set_id),
        document_id=doc.id,
        status=status,
        cards_status=cards_status,
    )
    db.add(km)
    await db.flush()
    concepts = [
        Concept(
            knowledge_map_id=km.id, position=p, title=f"C{p}", explanation="E", importance="core"
        )
        for p in range(n_concepts)
    ]
    db.add_all(concepts)
    await db.commit()
    return km, concepts


async def _card(
    db: AsyncSession,
    set_id: str,
    *,
    status: str = "suggested",
    origin: str = "generated",
    kind: str = "qa",
    front: str = "Q?",
    back: str = "A.",
    concept_id: uuid.UUID | None = None,
) -> uuid.UUID:
    card = Flashcard(
        study_set_id=uuid.UUID(set_id),
        status=status,
        origin=origin,
        kind=kind,
        front=front,
        back=back,
        concept_id=concept_id,
    )
    db.add(card)
    await db.commit()
    return card.id


async def _row(db: AsyncSession, model: Any, row_id: uuid.UUID) -> Any:
    row = (
        await db.execute(
            select(model).where(model.id == row_id).execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    await db.commit()
    return row


async def _set_cards_status(db: AsyncSession, map_id: uuid.UUID, value: str) -> None:
    km = await _row(db, KnowledgeMap, map_id)
    km.cards_status = value
    await db.commit()


async def _jobs(db: AsyncSession) -> list[Job]:
    rows = list(
        (
            await db.execute(
                select(Job).order_by(Job.created_at).execution_options(populate_existing=True)
            )
        ).scalars()
    )
    await db.commit()
    return rows


async def _statuses(db: AsyncSession, set_id: str) -> dict[uuid.UUID, str]:
    rows = (
        await db.execute(
            select(Flashcard.id, Flashcard.status).where(
                Flashcard.study_set_id == uuid.UUID(set_id)
            )
        )
    ).all()
    await db.commit()
    return {r[0]: r[1] for r in rows}


def _ids(r: httpx.Response) -> list[str]:
    return [c["id"] for c in r.json()]


async def test_list_default_excludes_suggested(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    manual = await user_client.post(
        f"/study-sets/{sid}/flashcards", json={"front": "f", "back": "b"}, headers=h
    )
    accepted = await _card(db, sid, status="accepted")
    await _card(db, sid, status="suggested")
    r = await user_client.get(f"/study-sets/{sid}/flashcards")
    assert r.status_code == 200
    assert _ids(r) == [manual.json()["id"], str(accepted)]
    assert all(c["status"] == "accepted" for c in r.json())
    r = await user_client.get(f"/study-sets/{sid}/flashcards?status=accepted")
    assert _ids(r) == [manual.json()["id"], str(accepted)]


async def test_list_suggested_filter(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    sid = await _set(user_client)
    await _card(db, sid, status="accepted")
    s1 = await _card(db, sid, status="suggested", front="one")
    s2 = await _card(db, sid, status="suggested", front="two")
    r = await user_client.get(f"/study-sets/{sid}/flashcards?status=suggested")
    assert r.status_code == 200
    assert _ids(r) == [str(s1), str(s2)]
    body = r.json()[0]
    assert set(body) == {
        "id",
        "study_set_id",
        "front",
        "back",
        "origin",
        "kind",
        "status",
        "edited",
        "concept_id",
        "created_at",
        "updated_at",
    }
    assert body["status"] == "suggested" and body["origin"] == "generated"
    assert body["edited"] is False and body["kind"] == "qa" and body["concept_id"] is None
    r = await user_client.get(f"/study-sets/{sid}/flashcards?status=bogus")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_create_cloze_card(user_client: httpx.AsyncClient) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    r = await user_client.post(
        f"/study-sets/{sid}/flashcards",
        json={"kind": "cloze", "front": "The capital of France is {{Paris}}.", "back": ""},
        headers=h,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "cloze" and body["back"] == ""
    assert body["origin"] == "manual" and body["status"] == "accepted"
    assert body["edited"] is False and body["concept_id"] is None
    r = await user_client.post(
        f"/study-sets/{sid}/flashcards",
        json={"kind": "cloze", "front": "It is {{x}} here"},
        headers=h,
    )
    assert r.status_code == 201 and r.json()["back"] == ""
    r = await user_client.post(
        f"/study-sets/{sid}/flashcards", json={"front": "q", "back": "a"}, headers=h
    )
    assert r.status_code == 201 and r.json()["kind"] == "qa"


async def test_create_cloze_invalid_422(user_client: httpx.AsyncClient) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    for front in ("No blank", "{{a}} and {{b}}", "x {{ }} y", "{{only}}"):
        r = await user_client.post(
            f"/study-sets/{sid}/flashcards",
            json={"kind": "cloze", "front": front, "back": ""},
            headers=h,
        )
        assert r.status_code == 422, front
        assert r.json()["error"]["code"] == "validation_error"
    r = await user_client.post(
        f"/study-sets/{sid}/flashcards",
        json={"kind": "cloze", "front": "No blank", "back": ""},
        headers=h,
    )
    assert "exactly one" in r.json()["error"]["details"][0]["msg"]
    r = await user_client.post(
        f"/study-sets/{sid}/flashcards",
        json={"kind": "bogus", "front": "f", "back": "b"},
        headers=h,
    )
    assert r.status_code == 422
    assert (await user_client.get(f"/study-sets/{sid}/flashcards")).json() == []


async def test_create_qa_blank_back_422(user_client: httpx.AsyncClient) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    for body in (
        {"front": "q"},
        {"kind": "qa", "front": "q", "back": ""},
        {"kind": "qa", "front": "q", "back": "  \n"},
        {"kind": "cloze", "front": "   ", "back": ""},
    ):
        r = await user_client.post(f"/study-sets/{sid}/flashcards", json=body, headers=h)
        assert r.status_code == 422, body
        assert r.json()["error"]["code"] == "validation_error"
        assert not r.json()["error"]["details"][0]["msg"].startswith("Value error")


async def test_cloze_msg_has_no_value_error_prefix(user_client: httpx.AsyncClient) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    r = await user_client.post(
        f"/study-sets/{sid}/flashcards",
        json={"kind": "cloze", "front": "No blank", "back": ""},
        headers=h,
    )
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["msg"] == CLOZE_MSG
    ok = await user_client.post(
        f"/study-sets/{sid}/flashcards", json={"front": "q", "back": "a"}, headers=h
    )
    r = await user_client.patch(f"/flashcards/{ok.json()['id']}", json={"kind": "cloze"}, headers=h)
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["msg"] == CLOZE_MSG


async def test_patch_validates_merged_row(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    qa = (
        await user_client.post(
            f"/study-sets/{sid}/flashcards", json={"front": "q", "back": "a"}, headers=h
        )
    ).json()["id"]
    # a qa card with back "" is impossible
    r = await user_client.patch(f"/flashcards/{qa}", json={"back": ""}, headers=h)
    assert r.status_code == 422
    # a cloze card switched to qa without a back
    cz = (
        await user_client.post(
            f"/study-sets/{sid}/flashcards",
            json={"kind": "cloze", "front": "It is {{x}} here", "back": ""},
            headers=h,
        )
    ).json()["id"]
    r = await user_client.patch(f"/flashcards/{cz}", json={"kind": "qa"}, headers=h)
    assert r.status_code == 422
    assert not r.json()["error"]["details"][0]["msg"].startswith("Value error")
    r = await user_client.patch(f"/flashcards/{cz}", json={"kind": "qa", "back": "x"}, headers=h)
    assert r.status_code == 200 and r.json()["kind"] == "qa" and r.json()["back"] == "x"
    # cloze card: a front that breaks the rule is refused
    cz2 = (
        await user_client.post(
            f"/study-sets/{sid}/flashcards",
            json={"kind": "cloze", "front": "It is {{y}} here", "back": ""},
            headers=h,
        )
    ).json()["id"]
    r = await user_client.patch(f"/flashcards/{cz2}", json={"front": "no blank"}, headers=h)
    assert r.status_code == 422
    # qa → cloze: the stored qa front is not a valid cloze
    r = await user_client.patch(f"/flashcards/{qa}", json={"kind": "cloze"}, headers=h)
    assert r.status_code == 422
    # qa → cloze with a valid front
    r = await user_client.patch(
        f"/flashcards/{qa}", json={"kind": "cloze", "front": "Paris is in {{France}}."}, headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "cloze" and r.json()["back"] == "a"
    # a cloze card may clear its back
    r = await user_client.patch(f"/flashcards/{qa}", json={"back": ""}, headers=h)
    assert r.status_code == 200 and r.json()["back"] == ""
    # explicit nulls are 422
    for field in ("front", "back", "kind", "status"):
        r = await user_client.patch(f"/flashcards/{qa}", json={field: None}, headers=h)
        assert r.status_code == 422, field
    # nothing changed by the refused patches
    row = await _row(db, Flashcard, uuid.UUID(qa))
    assert (row.kind, row.front, row.back) == ("cloze", "Paris is in {{France}}.", "")


async def test_patch_sets_edited_only_on_generated_change(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    gen = await _card(db, sid, status="suggested", front="Q?", back="A.")
    # same values → not edited
    r = await user_client.patch(f"/flashcards/{gen}", json={"front": "Q?", "back": "A."}, headers=h)
    assert r.status_code == 200 and r.json()["edited"] is False
    r = await user_client.patch(f"/flashcards/{gen}", json={"kind": "qa"}, headers=h)
    assert r.json()["edited"] is False
    # accepting is not an edit
    r = await user_client.patch(f"/flashcards/{gen}", json={"status": "accepted"}, headers=h)
    assert r.json()["edited"] is False and r.json()["status"] == "accepted"
    # a front change → edited
    r = await user_client.patch(f"/flashcards/{gen}", json={"front": "Q2?"}, headers=h)
    assert r.json()["edited"] is True
    assert (await _row(db, Flashcard, gen)).edited is True
    # a back change → edited
    gen_b = await _card(db, sid)
    r = await user_client.patch(f"/flashcards/{gen_b}", json={"back": "B."}, headers=h)
    assert r.json()["edited"] is True
    # a kind change on a generated card → edited
    gen_k = await _card(db, sid, front="It is {{x}} here", back="note")
    r = await user_client.patch(f"/flashcards/{gen_k}", json={"kind": "cloze"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["edited"] is True
    # a manual card is never edited
    manual = (
        await user_client.post(
            f"/study-sets/{sid}/flashcards", json={"front": "m", "back": "n"}, headers=h
        )
    ).json()["id"]
    r = await user_client.patch(
        f"/flashcards/{manual}", json={"front": "m2", "back": "n2"}, headers=h
    )
    assert r.status_code == 200 and r.json()["edited"] is False
    assert (await _row(db, Flashcard, uuid.UUID(manual))).edited is False


async def test_accept_via_patch_and_noop(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    h = await auth_headers(user_client)
    sid = await _set(user_client)
    gen = await _card(db, sid, status="suggested")
    r = await user_client.patch(f"/flashcards/{gen}", json={"status": "accepted"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    r = await user_client.patch(f"/flashcards/{gen}", json={"status": "accepted"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    r = await user_client.patch(f"/flashcards/{gen}", json={"status": "suggested"}, headers=h)
    assert r.status_code == 422
    assert (await _row(db, Flashcard, gen)).status == "accepted"
    assert _ids(await user_client.get(f"/study-sets/{sid}/flashcards")) == [str(gen)]


async def _generate(
    client: httpx.AsyncClient, sid: str, concept_id: uuid.UUID | str | None = None
) -> httpx.Response:
    return await client.post(
        f"/study-sets/{sid}/flashcards/generate",
        json={"concept_id": None if concept_id is None else str(concept_id)},
        headers=await auth_headers(client),
    )


async def test_generate_enqueues_and_sets_processing(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, concepts = await _map(db, sid, cards_status="failed")
    km.cards_error_message = "old failure"
    await db.commit()
    r = await _generate(user_client, sid)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["id"] == str(km.id)
    assert body["cards_status"] == "processing" and body["cards_error_message"] is None
    assert [c["id"] for c in body["concepts"]] == [str(c.id) for c in concepts]
    row = await _row(db, KnowledgeMap, km.id)
    assert row.cards_status == "processing" and row.cards_error_message is None
    jobs = await _jobs(db)
    assert len(jobs) == 1
    assert jobs[0].kind == "generate_flashcards"
    assert jobs[0].payload == {"knowledge_map_id": str(km.id), "concept_id": None}
    # one concept
    await _set_cards_status(db, km.id, "idle")
    r = await _generate(user_client, sid, concepts[1].id)
    assert r.status_code == 202
    jobs = await _jobs(db)
    assert jobs[-1].payload == {"knowledge_map_id": str(km.id), "concept_id": str(concepts[1].id)}
    # an empty body means the whole set
    await _set_cards_status(db, km.id, "idle")
    r = await user_client.post(
        f"/study-sets/{sid}/flashcards/generate", json={}, headers=await auth_headers(user_client)
    )
    assert r.status_code == 202
    assert (await _jobs(db))[-1].payload["concept_id"] is None


async def test_generate_concept_from_other_map_404(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid)
    other_sid = await _set(user_client)
    _, other_concepts = await _map(db, other_sid)
    for cid in (other_concepts[0].id, uuid.uuid4()):
        r = await _generate(user_client, sid, cid)
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert (await _row(db, KnowledgeMap, km.id)).cards_status == "idle"
    assert await _jobs(db) == []
    # a set without a map
    bare = await _set(user_client)
    r = await _generate(user_client, bare)
    assert r.status_code == 404


async def test_generate_409_states(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    cases = [
        ("processing", "idle", MAP_PROCESSING),
        ("failed", "idle", MAP_NOT_READY),
        ("ready", "processing", CARDS_PROCESSING),
    ]
    for map_status, cards_status, message in cases:
        sid = await _set(user_client)
        km, _ = await _map(db, sid, status=map_status, cards_status=cards_status)
        r = await _generate(user_client, sid)
        assert r.status_code == 409, (map_status, cards_status, r.text)
        assert r.json()["error"] == {"code": "conflict", "message": message, "details": None}
        row = await _row(db, KnowledgeMap, km.id)
        assert (row.status, row.cards_status) == (map_status, cards_status)
    assert await _jobs(db) == []


async def test_generate_rate_limited(
    user_client: httpx.AsyncClient, db: AsyncSession, clock: FrozenClock
) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid)
    for _ in range(20):
        assert (await _generate(user_client, sid)).status_code == 202
        await _set_cards_status(db, km.id, "idle")
    r = await _generate(user_client, sid)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    assert (await _row(db, KnowledgeMap, km.id)).cards_status == "idle"
    assert len(await _jobs(db)) == 20
    clock.advance(days=1)
    assert (await _generate(user_client, sid)).status_code == 202


async def test_failed_generates_do_not_consume_limit(
    user_client: httpx.AsyncClient, other_user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid, cards_status="processing")
    other_sid = await _set(other_user_client)
    await _map(db, other_sid)
    for _ in range(21):
        assert (await _generate(user_client, sid)).status_code == 409
    for _ in range(21):
        assert (await _generate(user_client, other_sid)).status_code == 404
    for _ in range(21):
        assert (await _generate(user_client, sid, uuid.uuid4())).status_code == 409
    await _set_cards_status(db, km.id, "idle")
    for _ in range(21):
        assert (await _generate(user_client, sid, uuid.uuid4())).status_code == 404
    for _ in range(20):
        await _set_cards_status(db, km.id, "idle")
        assert (await _generate(user_client, sid)).status_code == 202


async def _tray(
    client: httpx.AsyncClient, sid: str, action: str, card_ids: list[Any] | None
) -> httpx.Response:
    return await client.post(
        f"/study-sets/{sid}/suggested-cards/{action}",
        json={"card_ids": None if card_ids is None else [str(i) for i in card_ids]},
        headers=await auth_headers(client),
    )


async def test_accept_all_and_some(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    sid = await _set(user_client)
    other = await _set(user_client)
    s = [await _card(db, sid) for _ in range(4)]
    foreign_set_card = await _card(db, other)
    r = await _tray(user_client, sid, "accept", [s[0], s[1], s[1]])
    assert r.status_code == 200 and r.json() == {"accepted": 2}
    st = await _statuses(db, sid)
    assert [st[i] for i in s] == ["accepted", "accepted", "suggested", "suggested"]
    r = await _tray(user_client, sid, "accept", None)
    assert r.status_code == 200 and r.json() == {"accepted": 2}
    assert set((await _statuses(db, sid)).values()) == {"accepted"}
    assert (await _statuses(db, other))[foreign_set_card] == "suggested"
    r = await _tray(user_client, sid, "accept", None)
    assert r.json() == {"accepted": 0}
    r = await user_client.post(
        f"/study-sets/{sid}/suggested-cards/accept",
        json={},
        headers=await auth_headers(user_client),
    )
    assert r.status_code == 200 and r.json() == {"accepted": 0}


async def test_accept_reject_all_or_nothing(
    user_client: httpx.AsyncClient, other_user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    other_set = await _set(user_client)
    foreign_sid = await _set(other_user_client)
    s1 = await _card(db, sid)
    s2 = await _card(db, sid)
    accepted = await _card(db, sid, status="accepted")
    other_set_card = await _card(db, other_set)
    foreign = await _card(db, foreign_sid)
    before = await _statuses(db, sid)
    for action in ("accept", "reject"):
        for bad in (accepted, other_set_card, foreign, uuid.uuid4()):
            r = await _tray(user_client, sid, action, [s1, bad, s2])
            assert r.status_code == 404, (action, bad)
            assert r.json()["error"]["code"] == "not_found"
            assert await _statuses(db, sid) == before
    assert (await _statuses(db, foreign_sid))[foreign] == "suggested"
    assert (await _statuses(db, other_set))[other_set_card] == "suggested"


async def test_reject_deletes_suggested(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    sid = await _set(user_client)
    other = await _set(user_client)
    s = [await _card(db, sid) for _ in range(3)]
    accepted = await _card(db, sid, status="accepted")
    manual = await _card(db, sid, status="accepted", origin="manual")
    elsewhere = await _card(db, other)
    r = await _tray(user_client, sid, "reject", [s[0]])
    assert r.status_code == 200 and r.json() == {"rejected": 1}
    assert set(await _statuses(db, sid)) == {s[1], s[2], accepted, manual}
    r = await _tray(user_client, sid, "reject", None)
    assert r.status_code == 200 and r.json() == {"rejected": 2}
    assert set(await _statuses(db, sid)) == {accepted, manual}
    assert elsewhere in await _statuses(db, other)
    r = await _tray(user_client, sid, "reject", None)
    assert r.json() == {"rejected": 0}


async def test_card_ids_max_150(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    sid = await _set(user_client)
    s = await _card(db, sid)
    for action in ("accept", "reject"):
        r = await _tray(user_client, sid, action, [uuid.uuid4() for _ in range(151)])
        assert r.status_code == 422, action
        assert r.json()["error"]["code"] == "validation_error"
        r = await _tray(user_client, sid, action, [])
        assert r.status_code == 200 and r.json() == {f"{action}ed": 0}
    assert (await _statuses(db, sid))[s] == "suggested"
    # exactly 150 entries (duplicates of one id) are allowed
    r = await _tray(user_client, sid, "accept", [s] * 150)
    assert r.status_code == 200 and r.json() == {"accepted": 1}
