import uuid
from datetime import timedelta
from typing import Any

import httpx
import pytest
from conftest import FrozenClock, auth_headers
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.auth.rate_limit import hit, map_build_key
from feynman_api.models import (
    Concept,
    Document,
    Flashcard,
    Job,
    KnowledgeMap,
    KnowledgeMapChunk,
)
from feynman_api.routes import knowledge_maps

pytestmark = pytest.mark.usefixtures("clean_db")

MAP_PROCESSING = "The Knowledge Map is still being built."
MAP_NOT_READY = "The Knowledge Map isn't ready."
CARDS_PROCESSING = "Flashcards are already being generated."
MAP_FULL = "This Knowledge Map has the maximum number of concepts."

NEW_CONCEPT: dict[str, Any] = {"title": "New", "explanation": "Body", "importance": "core"}


async def _set(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post("/study-sets", json={"title": "S"}, headers=await auth_headers(client))
    return uuid.UUID(r.json()["id"])


async def _user_id(client: httpx.AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get("/auth/session")).json()["user"]["id"])


async def _doc(
    db: AsyncSession, set_id: uuid.UUID, *, status: str = "ready", page_count: int | None = 5
) -> Document:
    doc = Document(
        study_set_id=set_id,
        storage_key=uuid.uuid4().hex,
        original_filename="lesson.pdf",
        size_bytes=1,
        status=status,
        page_count=page_count,
    )
    db.add(doc)
    await db.commit()
    return doc


async def _map(
    db: AsyncSession,
    set_id: uuid.UUID,
    *,
    status: str = "ready",
    cards_status: str = "idle",
    positions: list[int] | None = None,
    error_message: str | None = None,
) -> tuple[KnowledgeMap, list[Concept]]:
    doc = await _doc(db, set_id)
    km = KnowledgeMap(
        study_set_id=set_id,
        document_id=doc.id,
        status=status,
        cards_status=cards_status,
        error_message=error_message,
        model_id="m-1",
    )
    db.add(km)
    await db.flush()
    concepts = [
        Concept(
            knowledge_map_id=km.id,
            position=p,
            title=f"C{p}",
            explanation=f"E{p}",
            importance="core",
            key_terms=[{"term": f"t{p}", "synonyms": []}],
            misconceptions=[],
            source_pages=[1],
        )
        for p in (positions if positions is not None else [0, 1, 2])
    ]
    db.add_all(concepts)
    await db.commit()
    return km, concepts


async def _get_map(db: AsyncSession, map_id: uuid.UUID) -> KnowledgeMap:
    km = (
        await db.execute(
            select(KnowledgeMap)
            .where(KnowledgeMap.id == map_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    await db.commit()
    return km


async def _concepts(db: AsyncSession, map_id: uuid.UUID) -> list[Concept]:
    rows = list(
        (
            await db.execute(
                select(Concept)
                .where(Concept.knowledge_map_id == map_id)
                .order_by(Concept.position)
                .execution_options(populate_existing=True)
            )
        ).scalars()
    )
    await db.commit()
    return rows


async def _count(db: AsyncSession, model: Any) -> int:
    n = (await db.execute(select(func.count()).select_from(model))).scalar_one()
    await db.commit()
    return int(n)


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


async def _reset_ready(db: AsyncSession, map_id: uuid.UUID) -> None:
    km = await _get_map(db, map_id)
    km.status = "ready"
    await db.commit()


def _conflict(r: httpx.Response, message: str) -> None:
    assert r.status_code == 409, r.text
    assert r.json()["error"] == {"code": "conflict", "message": message, "details": None}


async def test_get_map_with_concepts_ordered(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid, positions=[5, 0, 2])
    r = await user_client.get(f"/study-sets/{sid}/knowledge-map")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "id",
        "status",
        "error_message",
        "model_id",
        "revision",
        "cards_status",
        "cards_error_message",
        "source_filename",
        "concepts",
    }
    assert body["id"] == str(km.id)
    assert body["status"] == "ready"
    assert body["error_message"] is None
    assert body["model_id"] == "m-1"
    assert body["revision"] == 0
    assert body["cards_status"] == "idle"
    assert body["cards_error_message"] is None
    assert body["source_filename"] == "lesson.pdf"
    assert [c["position"] for c in body["concepts"]] == [0, 2, 5]
    assert [c["title"] for c in body["concepts"]] == ["C0", "C2", "C5"]
    assert set(body["concepts"][0]) == {
        "id",
        "position",
        "title",
        "explanation",
        "importance",
        "key_terms",
        "misconceptions",
        "source_pages",
    }
    assert body["concepts"][0]["key_terms"] == [{"term": "t0", "synonyms": []}]


async def test_get_map_404_without_map(user_client: httpx.AsyncClient) -> None:
    sid = await _set(user_client)
    r = await user_client.get(f"/study-sets/{sid}/knowledge-map")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


async def test_add_concept_appends_and_bumps_revision(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid, positions=[0, 4])
    body = {
        "title": "  Photosynthesis  ",
        "explanation": "Light to sugar",
        "importance": "supporting",
        "key_terms": [{"term": " chlorophyll ", "synonyms": [" green pigment "]}],
        "misconceptions": ["Plants eat soil"],
        "source_pages": [2],
    }
    r = await user_client.post(
        f"/study-sets/{sid}/concepts", json=body, headers=await auth_headers(user_client)
    )
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["position"] == 5
    assert out["title"] == "Photosynthesis"
    assert out["importance"] == "supporting"
    assert out["key_terms"] == [{"term": "chlorophyll", "synonyms": ["green pigment"]}]
    assert out["misconceptions"] == ["Plants eat soil"]
    assert out["source_pages"] == [2]
    assert (await _get_map(db, km.id)).revision == 1
    assert [c.position for c in await _concepts(db, km.id)] == [0, 4, 5]


async def test_add_concept_validation(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid)
    h = await auth_headers(user_client)
    bad: list[dict[str, Any]] = [
        {"key_terms": [{"term": f"t{i}", "synonyms": []} for i in range(11)]},
        {"misconceptions": [f"m{i}" for i in range(6)]},
        {"source_pages": [0]},
        {"title": "   "},
        {"explanation": "  \n "},
        {"title": "a\x00b"},
        {"importance": "huge"},
        {"key_terms": [{"term": "t", "synonyms": [f"s{i}" for i in range(6)]}]},
        {"misconceptions": ["x" * 301]},
        {"source_pages": list(range(1, 52))},
    ]
    for extra in bad:
        r = await user_client.post(
            f"/study-sets/{sid}/concepts", json=NEW_CONCEPT | extra, headers=h
        )
        assert r.status_code == 422, extra
        assert r.json()["error"]["code"] == "validation_error"
    r = await user_client.post(
        f"/study-sets/{sid}/concepts", json=NEW_CONCEPT | {"source_pages": [6]}, headers=h
    )
    assert r.status_code == 422
    assert r.json()["error"]["details"] == [
        {"loc": ["body", "source_pages"], "msg": "page numbers must be within the document"}
    ]
    assert (await _get_map(db, km.id)).revision == 0
    r = await user_client.post(
        f"/study-sets/{sid}/concepts", json=NEW_CONCEPT | {"source_pages": [3, 1, 3]}, headers=h
    )
    assert r.status_code == 201
    assert r.json()["source_pages"] == [1, 3]
    stored = [c for c in await _concepts(db, km.id) if c.title == "New"]
    assert stored[0].source_pages == [1, 3]


async def test_add_concept_full_map_409(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid, positions=list(range(100)))
    r = await user_client.post(
        f"/study-sets/{sid}/concepts", json=NEW_CONCEPT, headers=await auth_headers(user_client)
    )
    _conflict(r, MAP_FULL)
    assert len(await _concepts(db, km.id)) == 100
    assert (await _get_map(db, km.id)).revision == 0


async def test_patch_concept_partial(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    sid = await _set(user_client)
    km, concepts = await _map(db, sid)
    h = await auth_headers(user_client)
    cid = concepts[1].id
    r = await user_client.patch(f"/concepts/{cid}", json={"title": " Renamed "}, headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["title"] == "Renamed"
    assert out["explanation"] == "E1"
    assert out["key_terms"] == [{"term": "t1", "synonyms": []}]
    assert out["position"] == 1
    r = await user_client.patch(
        f"/concepts/{cid}", json={"source_pages": [4, 2, 4], "misconceptions": ["m"]}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["source_pages"] == [2, 4] and r.json()["title"] == "Renamed"
    assert (await _get_map(db, km.id)).revision == 2
    for bad in ({"title": None}, {"importance": None}, {"source_pages": [9]}, {"title": ""}):
        r = await user_client.patch(f"/concepts/{cid}", json=bad, headers=h)
        assert r.status_code == 422, bad
    assert (await _get_map(db, km.id)).revision == 2
    stored = next(c for c in await _concepts(db, km.id) if c.id == cid)
    assert stored.title == "Renamed" and stored.source_pages == [2, 4]


async def test_delete_concept_unlinks_cards(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, concepts = await _map(db, sid)
    card = Flashcard(study_set_id=sid, front="f", back="b", concept_id=concepts[1].id)
    db.add(card)
    await db.commit()
    r = await user_client.delete(
        f"/concepts/{concepts[1].id}", headers=await auth_headers(user_client)
    )
    assert r.status_code == 204
    assert [c.position for c in await _concepts(db, km.id)] == [0, 2]
    kept = (
        await db.execute(
            select(Flashcard)
            .where(Flashcard.id == card.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert kept.front == "f" and kept.concept_id is None
    await db.commit()
    assert (await _get_map(db, km.id)).revision == 1


async def test_order_rewrites_positions(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    sid = await _set(user_client)
    km, concepts = await _map(db, sid, positions=[0, 3, 7])
    order = [concepts[2].id, concepts[0].id, concepts[1].id]
    r = await user_client.put(
        f"/study-sets/{sid}/knowledge-map/order",
        json={"concept_ids": [str(i) for i in order]},
        headers=await auth_headers(user_client),
    )
    assert r.status_code == 200, r.text
    assert [c["id"] for c in r.json()["concepts"]] == [str(i) for i in order]
    assert [c["position"] for c in r.json()["concepts"]] == [0, 1, 2]
    assert r.json()["revision"] == 1
    stored = await _concepts(db, km.id)
    assert [(c.id, c.position) for c in stored] == list(zip(order, [0, 1, 2], strict=True))
    assert (await _get_map(db, km.id)).revision == 1


@pytest.mark.parametrize("bad", ["missing", "extra", "duplicate", "foreign"])
async def test_order_must_be_exact_permutation(
    user_client: httpx.AsyncClient, db: AsyncSession, bad: str
) -> None:
    sid = await _set(user_client)
    km, concepts = await _map(db, sid)
    other_sid = await _set(user_client)
    _, other_concepts = await _map(db, other_sid)
    ids = [str(c.id) for c in concepts]
    if bad == "missing":
        ids = ids[:-1]
    elif bad == "extra":
        ids = [*ids, str(uuid.uuid4())]
    elif bad == "duplicate":
        ids = [ids[0], ids[0], ids[1]]
    else:
        ids = [ids[0], ids[1], str(other_concepts[0].id)]
    r = await user_client.put(
        f"/study-sets/{sid}/knowledge-map/order",
        json={"concept_ids": ids},
        headers=await auth_headers(user_client),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert [c.position for c in await _concepts(db, km.id)] == [0, 1, 2]
    assert (await _get_map(db, km.id)).revision == 0


async def _mutations(
    client: httpx.AsyncClient, sid: uuid.UUID, concepts: list[Concept]
) -> list[httpx.Response]:
    h = await auth_headers(client)
    return [
        await client.post(f"/study-sets/{sid}/concepts", json=NEW_CONCEPT, headers=h),
        await client.patch(f"/concepts/{concepts[0].id}", json={"title": "x"}, headers=h),
        await client.delete(f"/concepts/{concepts[1].id}", headers=h),
        await client.put(
            f"/study-sets/{sid}/knowledge-map/order",
            json={"concept_ids": [str(c.id) for c in reversed(concepts)]},
            headers=h,
        ),
    ]


async def test_mutations_409_while_processing(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, concepts = await _map(db, sid, status="processing")
    for r in await _mutations(user_client, sid, concepts):
        _conflict(r, MAP_PROCESSING)
    km_failed = await _get_map(db, km.id)
    km_failed.status = "failed"
    await db.commit()
    for r in await _mutations(user_client, sid, concepts):
        _conflict(r, MAP_NOT_READY)
    assert [c.title for c in await _concepts(db, km.id)] == ["C0", "C1", "C2"]
    assert (await _get_map(db, km.id)).revision == 0


async def test_mutations_409_while_cards_processing(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, concepts = await _map(db, sid, cards_status="processing")
    for r in await _mutations(user_client, sid, concepts):
        _conflict(r, CARDS_PROCESSING)
    assert [c.title for c in await _concepts(db, km.id)] == ["C0", "C1", "C2"]
    assert (await _get_map(db, km.id)).revision == 0


async def _rebuild(client: httpx.AsyncClient, sid: uuid.UUID) -> httpx.Response:
    return await client.post(
        f"/study-sets/{sid}/knowledge-map/rebuild", headers=await auth_headers(client)
    )


async def test_rebuild_resets_and_enqueues(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid, error_message="old")
    db.add_all(
        KnowledgeMapChunk(
            knowledge_map_id=km.id, chunk_index=i, page_start=i + 1, page_end=i + 1, status="done"
        )
        for i in range(2)
    )
    await db.commit()
    r = await _rebuild(user_client, sid)
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "processing"
    assert r.json()["error_message"] is None
    assert len(r.json()["concepts"]) == 3
    stored = await _get_map(db, km.id)
    assert stored.status == "processing" and stored.error_message is None
    assert await _count(db, KnowledgeMapChunk) == 0
    assert len(await _concepts(db, km.id)) == 3
    jobs = await _jobs(db)
    assert [(j.kind, j.payload, j.status) for j in jobs] == [
        ("build_knowledge_map", {"knowledge_map_id": str(km.id)}, "queued")
    ]


async def test_rebuild_failed_map_is_retry(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid, status="failed", error_message="boom")
    r = await _rebuild(user_client, sid)
    assert r.status_code == 202
    stored = await _get_map(db, km.id)
    assert stored.status == "processing" and stored.error_message is None
    assert len(await _jobs(db)) == 1


async def test_rebuild_409_states(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid, status="processing")
    _conflict(await _rebuild(user_client, sid), MAP_PROCESSING)
    stored = await _get_map(db, km.id)
    stored.status = "ready"
    stored.cards_status = "processing"
    await db.commit()
    _conflict(await _rebuild(user_client, sid), CARDS_PROCESSING)
    assert await _jobs(db) == []
    assert (await _get_map(db, km.id)).status == "ready"


async def test_rebuild_rate_limited(
    user_client: httpx.AsyncClient, db: AsyncSession, clock: FrozenClock
) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid)
    for _ in range(5):
        assert (await _rebuild(user_client, sid)).status_code == 202
        await _reset_ready(db, km.id)
    r = await _rebuild(user_client, sid)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    assert (await _get_map(db, km.id)).status == "ready"
    assert len(await _jobs(db)) == 5
    clock.advance(days=1)
    assert (await _rebuild(user_client, sid)).status_code == 202


async def test_failed_rebuilds_do_not_consume_limit(
    user_client: httpx.AsyncClient, other_user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    km, _ = await _map(db, sid, status="processing")
    other_sid = await _set(other_user_client)
    await _map(db, other_sid)
    for _ in range(6):
        assert (await _rebuild(user_client, other_sid)).status_code == 404
    for _ in range(6):
        assert (await _rebuild(user_client, sid)).status_code == 409
    for _ in range(5):
        await _reset_ready(db, km.id)
        assert (await _rebuild(user_client, sid)).status_code == 202


async def test_rebuild_without_map_404(user_client: httpx.AsyncClient, db: AsyncSession) -> None:
    sid = await _set(user_client)
    r = await _rebuild(user_client, sid)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    failed_sid = await _set(user_client)
    await _doc(db, failed_sid, status="failed", page_count=None)
    r = await _rebuild(user_client, failed_sid)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert await _count(db, KnowledgeMap) == 0
    assert await _jobs(db) == []


async def test_rebuild_creates_missing_map_for_ready_document(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    doc = await _doc(db, sid)
    r = await _rebuild(user_client, sid)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "processing"
    assert body["revision"] == 0
    assert body["concepts"] == []
    assert body["source_filename"] == "lesson.pdf"
    maps = list((await db.execute(select(KnowledgeMap))).scalars())
    await db.commit()
    assert len(maps) == 1
    assert maps[0].id == uuid.UUID(body["id"])
    assert maps[0].status == "processing"
    assert maps[0].document_id == doc.id
    assert maps[0].study_set_id == sid
    assert maps[0].revision == 0
    jobs = await _jobs(db)
    assert [(j.kind, j.payload, j.status) for j in jobs] == [
        ("build_knowledge_map", {"knowledge_map_id": body["id"]}, "queued")
    ]


async def test_rebuild_missing_map_document_processing_409(
    user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    sid = await _set(user_client)
    await _doc(db, sid, status="processing", page_count=None)
    _conflict(await _rebuild(user_client, sid), MAP_PROCESSING)
    assert await _count(db, KnowledgeMap) == 0
    assert await _jobs(db) == []


async def test_rebuild_missing_map_counts_against_limit(
    user_client: httpx.AsyncClient, db: AsyncSession, clock: FrozenClock
) -> None:
    sid = await _set(user_client)
    await _doc(db, sid)
    key = map_build_key(await _user_id(user_client))
    for _ in range(5):  # settings.map_build_limit
        await hit(db, key, 5, timedelta(seconds=86_400), clock())
    r = await _rebuild(user_client, sid)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    assert await _count(db, KnowledgeMap) == 0
    assert await _jobs(db) == []


async def test_rebuild_missing_map_cross_user_404(
    user_client: httpx.AsyncClient, other_user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    other_sid = await _set(other_user_client)
    await _doc(db, other_sid)
    r = await _rebuild(user_client, other_sid)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert await _count(db, KnowledgeMap) == 0
    assert await _jobs(db) == []


async def test_rebuild_concurrent_map_create_409(
    user_client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A competing request commits the set's map after this one found none (the unique
    # study_set_id is not deferrable, so the violation surfaces at the INSERT's flush).
    sid = await _set(user_client)
    doc = await _doc(db, sid)
    real_hit = hit

    async def hit_then_race(*args: Any, **kwargs: Any) -> Any:
        result = await real_hit(*args, **kwargs)
        db.add(KnowledgeMap(study_set_id=sid, document_id=doc.id, status="processing"))
        await db.commit()
        return result

    monkeypatch.setattr(knowledge_maps, "hit", hit_then_race)
    _conflict(await _rebuild(user_client, sid), MAP_PROCESSING)
    assert await _count(db, KnowledgeMap) == 1
    assert await _jobs(db) == []
