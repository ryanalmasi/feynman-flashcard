import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from conftest import auth_headers, walk_routes
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.models import Concept, Document, Flashcard, KnowledgeMap

pytestmark = pytest.mark.usefixtures("clean_db")


@dataclass
class Ids:
    set_id: uuid.UUID
    card_id: uuid.UUID
    document_id: uuid.UUID | None = None
    concept_id: uuid.UUID | None = None


OwnedEndpoint = tuple[str, str, Callable[[Ids], str], dict[str, Any] | None]
OWNED_ENDPOINTS: list[OwnedEndpoint] = [
    ("GET", "/study-sets/{set_id}", lambda i: f"/study-sets/{i.set_id}", None),
    ("PATCH", "/study-sets/{set_id}", lambda i: f"/study-sets/{i.set_id}", {"title": "hacked"}),
    ("DELETE", "/study-sets/{set_id}", lambda i: f"/study-sets/{i.set_id}", None),
    (
        "GET",
        "/study-sets/{set_id}/flashcards",
        lambda i: f"/study-sets/{i.set_id}/flashcards",
        None,
    ),
    (
        "POST",
        "/study-sets/{set_id}/flashcards",
        lambda i: f"/study-sets/{i.set_id}/flashcards",
        {"front": "f", "back": "b"},
    ),
    (
        "POST",
        "/study-sets/{set_id}/flashcards/generate",
        lambda i: f"/study-sets/{i.set_id}/flashcards/generate",
        {"concept_id": None},
    ),
    (
        "POST",
        "/study-sets/{set_id}/suggested-cards/accept",
        lambda i: f"/study-sets/{i.set_id}/suggested-cards/accept",
        {"card_ids": None},
    ),
    (
        "POST",
        "/study-sets/{set_id}/suggested-cards/reject",
        lambda i: f"/study-sets/{i.set_id}/suggested-cards/reject",
        {"card_ids": None},
    ),
    ("PATCH", "/flashcards/{card_id}", lambda i: f"/flashcards/{i.card_id}", {"front": "hacked"}),
    ("DELETE", "/flashcards/{card_id}", lambda i: f"/flashcards/{i.card_id}", None),
    ("GET", "/documents/{document_id}", lambda i: f"/documents/{i.document_id}", None),
    (
        "GET",
        "/study-sets/{set_id}/knowledge-map",
        lambda i: f"/study-sets/{i.set_id}/knowledge-map",
        None,
    ),
    (
        "POST",
        "/study-sets/{set_id}/knowledge-map/rebuild",
        lambda i: f"/study-sets/{i.set_id}/knowledge-map/rebuild",
        None,
    ),
    (
        "POST",
        "/study-sets/{set_id}/concepts",
        lambda i: f"/study-sets/{i.set_id}/concepts",
        {"title": "t", "explanation": "e", "importance": "core"},
    ),
    ("PATCH", "/concepts/{concept_id}", lambda i: f"/concepts/{i.concept_id}", {"title": "hacked"}),
    ("DELETE", "/concepts/{concept_id}", lambda i: f"/concepts/{i.concept_id}", None),
    (
        "PUT",
        "/study-sets/{set_id}/knowledge-map/order",
        lambda i: f"/study-sets/{i.set_id}/knowledge-map/order",
        {"concept_ids": [str(uuid.uuid4())]},
    ),
]


async def _seed(client: httpx.AsyncClient, db: AsyncSession) -> Ids:
    h = await auth_headers(client)
    s = await client.post("/study-sets", json={"title": "Mine"}, headers=h)
    c = await client.post(
        f"/study-sets/{s.json()['id']}/flashcards", json={"front": "f", "back": "b"}, headers=h
    )
    set_id = uuid.UUID(s.json()["id"])
    doc = Document(
        study_set_id=set_id,
        storage_key=uuid.uuid4().hex,
        original_filename="a.pdf",
        size_bytes=1,
        status="processing",
    )
    db.add(doc)
    await db.flush()
    kmap = KnowledgeMap(study_set_id=set_id, document_id=doc.id, status="ready")
    db.add(kmap)
    await db.flush()
    concept = Concept(
        knowledge_map_id=kmap.id, position=0, title="c", explanation="e", importance="core"
    )
    db.add(concept)
    # A suggested card, so a cross-user accept/reject would visibly change the set.
    db.add(
        Flashcard(study_set_id=set_id, front="s", back="b", origin="generated", status="suggested")
    )
    await db.commit()
    return Ids(
        set_id=set_id,
        card_id=uuid.UUID(c.json()["id"]),
        document_id=doc.id,
        concept_id=concept.id,
    )


async def test_ownership_matrix(
    user_client: httpx.AsyncClient, other_user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    ids = await _seed(user_client, db)
    before_set = (await user_client.get(f"/study-sets/{ids.set_id}")).json()
    before_cards = (await user_client.get(f"/study-sets/{ids.set_id}/flashcards")).json()
    before_map = (await user_client.get(f"/study-sets/{ids.set_id}/knowledge-map")).json()
    suggested_url = f"/study-sets/{ids.set_id}/flashcards?status=suggested"
    before_suggested = (await user_client.get(suggested_url)).json()
    assert len(before_suggested) == 1
    random_ids = Ids(
        set_id=uuid.uuid4(),
        card_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        concept_id=uuid.uuid4(),
    )
    h = await auth_headers(other_user_client)
    for method, path, url, body in OWNED_ENDPOINTS:
        mine = await other_user_client.request(method, url(ids), json=body, headers=h)
        rand = await other_user_client.request(method, url(random_ids), json=body, headers=h)
        assert mine.status_code == 404, (method, path)
        assert mine.json()["error"]["code"] == "not_found", (method, path)
        assert mine.content == rand.content, (method, path)
    assert (await user_client.get(f"/study-sets/{ids.set_id}")).json() == before_set
    assert before_set["document"] is not None  # the set under attack carries a document
    assert (await user_client.get(f"/study-sets/{ids.set_id}/flashcards")).json() == before_cards
    assert (await user_client.get(suggested_url)).json() == before_suggested
    after_map = (await user_client.get(f"/study-sets/{ids.set_id}/knowledge-map")).json()
    assert after_map == before_map
    assert [c["id"] for c in after_map["concepts"]] == [str(ids.concept_id)]


async def test_ownership_matrix_covers_every_id_route(app: FastAPI) -> None:
    # walk_routes recurses into FastAPI's _IncludedRouter; include_in_schema=False is covered.
    actual = {
        (method, r.path)
        for r in walk_routes(app.routes)
        if "{" in r.path
        for method in (r.methods or set())
    }
    assert actual == {(m, p) for m, p, *_ in OWNED_ENDPOINTS}


async def test_list_sets_shows_only_own(
    user_client: httpx.AsyncClient, other_user_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await _seed(user_client, db)
    assert (await other_user_client.get("/study-sets")).json() == []
    assert len((await user_client.get("/study-sets")).json()) == 1
