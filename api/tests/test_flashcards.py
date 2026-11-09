import httpx
import pytest
from conftest import auth_headers

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
