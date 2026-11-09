import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from conftest import auth_headers, walk_routes
from fastapi import FastAPI

pytestmark = pytest.mark.usefixtures("clean_db")


@dataclass
class Ids:
    set_id: uuid.UUID
    card_id: uuid.UUID
    document_id: uuid.UUID | None = None


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
    ("PATCH", "/flashcards/{card_id}", lambda i: f"/flashcards/{i.card_id}", {"front": "hacked"}),
    ("DELETE", "/flashcards/{card_id}", lambda i: f"/flashcards/{i.card_id}", None),
]


async def _seed(client: httpx.AsyncClient) -> Ids:
    h = await auth_headers(client)
    s = await client.post("/study-sets", json={"title": "Mine"}, headers=h)
    c = await client.post(
        f"/study-sets/{s.json()['id']}/flashcards", json={"front": "f", "back": "b"}, headers=h
    )
    return Ids(set_id=uuid.UUID(s.json()["id"]), card_id=uuid.UUID(c.json()["id"]))


async def test_ownership_matrix(
    user_client: httpx.AsyncClient, other_user_client: httpx.AsyncClient
) -> None:
    ids = await _seed(user_client)
    before_set = (await user_client.get(f"/study-sets/{ids.set_id}")).json()
    before_cards = (await user_client.get(f"/study-sets/{ids.set_id}/flashcards")).json()
    random_ids = Ids(set_id=uuid.uuid4(), card_id=uuid.uuid4(), document_id=uuid.uuid4())
    h = await auth_headers(other_user_client)
    for method, path, url, body in OWNED_ENDPOINTS:
        mine = await other_user_client.request(method, url(ids), json=body, headers=h)
        rand = await other_user_client.request(method, url(random_ids), json=body, headers=h)
        assert mine.status_code == 404, (method, path)
        assert mine.json()["error"]["code"] == "not_found", (method, path)
        assert mine.content == rand.content, (method, path)
    assert (await user_client.get(f"/study-sets/{ids.set_id}")).json() == before_set
    assert (await user_client.get(f"/study-sets/{ids.set_id}/flashcards")).json() == before_cards


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
    user_client: httpx.AsyncClient, other_user_client: httpx.AsyncClient
) -> None:
    await _seed(user_client)
    assert (await other_user_client.get("/study-sets")).json() == []
    assert len((await user_client.get("/study-sets")).json()) == 1
