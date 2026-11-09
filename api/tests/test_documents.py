import httpx
import pytest
from conftest import auth_headers
from test_upload import PDF, multipart, post

pytestmark = pytest.mark.usefixtures("clean_db")


async def test_get_document_status(user_client: httpx.AsyncClient) -> None:
    up = (await post(user_client, multipart(PDF))).json()
    r = await user_client.get(f"/documents/{up['document']['id']}")
    assert r.status_code == 200
    assert r.json() == {
        "id": up["document"]["id"],
        "study_set_id": up["study_set"]["id"],
        "status": "processing",
        "page_count": None,
        "error_message": None,
        "original_filename": "text.pdf",
    }


async def test_get_other_users_document_404(
    user_client: httpx.AsyncClient, other_user_client: httpx.AsyncClient
) -> None:
    up = (await post(user_client, multipart(PDF))).json()
    await auth_headers(other_user_client)
    r = await other_user_client.get(f"/documents/{up['document']['id']}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
