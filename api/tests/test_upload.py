import re
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from conftest import auth_headers
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.config import Settings
from feynman_api.models import Document, Job, StudySet
from feynman_api.storage import LocalFileStore

pytestmark = pytest.mark.usefixtures("clean_db")
MIB = 1024 * 1024
BOUNDARY = "testboundary123"
PDF = b"%PDF-1.4\n%test\n"


def _head(filename: str = "text.pdf", title: str | None = None) -> bytes:
    out = b""
    if title is not None:
        out += (
            f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'
        ).encode()
    out += (
        f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename}"\r\nContent-Type: application/pdf\r\n\r\n'
    ).encode()
    return out


_TAIL = f"\r\n--{BOUNDARY}--\r\n".encode()
_CT = {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"}


def multipart(content: bytes, filename: str = "text.pdf", title: str | None = None) -> bytes:
    return _head(filename, title) + content + _TAIL


async def post(
    client: httpx.AsyncClient,
    body: bytes | AsyncIterator[bytes],
    extra: dict[str, str] | None = None,
) -> httpx.Response:
    headers = await auth_headers(client) | _CT | (extra or {})
    return await client.post("/documents", content=body, headers=headers)


def stored_files(store_root: Path) -> list[Path]:
    return sorted(store_root.iterdir())


@pytest.fixture
def tmp_tempdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "t"
    d.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(d))
    return d


async def assert_nothing_stored(
    db: AsyncSession, file_store: LocalFileStore, temp_dir: Path | None = None
) -> None:
    for model in (StudySet, Document, Job):
        assert (await db.execute(select(func.count()).select_from(model))).scalar_one() == 0
    root: Path = file_store._root
    assert stored_files(root) == []  # includes any .part file
    if temp_dir is not None:
        assert stored_files(temp_dir) == []


async def test_upload_text_pdf_202(
    user_client: httpx.AsyncClient, db: AsyncSession, file_store: LocalFileStore
) -> None:
    r = await post(user_client, multipart(PDF))
    assert r.status_code == 202
    body = r.json()
    assert body["study_set"]["title"] == "text"
    assert body["document"]["status"] == "processing"
    assert body["document"]["original_filename"] == "text.pdf"
    assert body["document"]["study_set_id"] == body["study_set"]["id"]
    jobs = (await db.execute(select(Job))).scalars().all()
    assert len(jobs) == 1 and jobs[0].kind == "extract_pdf" and jobs[0].status == "queued"
    assert jobs[0].payload == {"document_id": body["document"]["id"]}
    doc = (await db.execute(select(Document))).scalar_one()
    assert doc.size_bytes == len(PDF)
    with file_store.open(doc.storage_key) as fh:
        assert fh.read() == PDF


async def test_upload_title_override(user_client: httpx.AsyncClient) -> None:
    r = await post(user_client, multipart(PDF, title="  My Title  "))
    assert r.status_code == 202
    assert r.json()["study_set"]["title"] == "My Title"


async def test_upload_non_pdf_415(
    user_client: httpx.AsyncClient,
    db: AsyncSession,
    file_store: LocalFileStore,
    tmp_tempdir: Path,
) -> None:
    r = await post(user_client, multipart(b"hello", filename="x.pdf"))
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_file_type"
    await assert_nothing_stored(db, file_store, tmp_tempdir)


async def test_upload_too_large_declared_content_length(
    user_client: httpx.AsyncClient,
    db: AsyncSession,
    file_store: LocalFileStore,
    tmp_tempdir: Path,
) -> None:
    r = await post(user_client, multipart(PDF), extra={"Content-Length": "30000000"})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "file_too_large"
    await assert_nothing_stored(db, file_store, tmp_tempdir)


async def test_upload_too_large_chunked(
    user_client: httpx.AsyncClient,
    db: AsyncSession,
    file_store: LocalFileStore,
    tmp_tempdir: Path,
    test_settings: Settings,
) -> None:
    cap = test_settings.max_upload_bytes + test_settings.upload_multipart_allowance_bytes
    total = cap + 4 * MIB
    sent = 0

    async def body() -> AsyncIterator[bytes]:
        nonlocal sent
        block = b"x" * 65536
        for part in (_head(), PDF):
            sent += len(part)
            yield part
        while sent < total:
            sent += len(block)
            yield block
        yield _TAIL

    r = await post(user_client, body())
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "file_too_large"
    # The cap stops the read: far less than the full body was consumed.
    assert sent < total
    await assert_nothing_stored(db, file_store, tmp_tempdir)


async def test_upload_too_large_by_one_byte_in_handler(
    user_client: httpx.AsyncClient,
    db: AsyncSession,
    file_store: LocalFileStore,
    tmp_tempdir: Path,
    test_settings: Settings,
) -> None:
    content = b"%PDF-" + b"x" * (test_settings.max_upload_bytes - 5 + 1)
    r = await post(user_client, multipart(content))
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "file_too_large"
    await assert_nothing_stored(db, file_store, tmp_tempdir)


async def test_upload_exactly_20_mib_ok(
    user_client: httpx.AsyncClient, db: AsyncSession, test_settings: Settings
) -> None:
    assert test_settings.max_upload_bytes == 20 * MIB
    content = b"%PDF-" + b"x" * (20 * MIB - 5)
    r = await post(user_client, multipart(content))
    assert r.status_code == 202
    doc = (await db.execute(select(Document))).scalar_one()
    assert doc.size_bytes == 20 * MIB


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../evil.pdf", "evil.pdf"),
        ("..\\..\\evil.pdf", "evil.pdf"),
        ("C:\\x\\y\\my  file.pdf", "my file.pdf"),
    ],
)
async def test_upload_filename_never_used_as_path(
    user_client: httpx.AsyncClient,
    db: AsyncSession,
    file_store: LocalFileStore,
    tmp_path: Path,
    raw: str,
    expected: str,
) -> None:
    r = await post(user_client, multipart(PDF, filename=raw))
    assert r.status_code == 202
    assert r.json()["document"]["original_filename"] == expected
    doc = (await db.execute(select(Document))).scalar_one()
    assert re.fullmatch(r"[0-9a-f]{32}", doc.storage_key)
    assert [p.name for p in stored_files(file_store._root)] == [doc.storage_key]
    assert not (tmp_path / "evil.pdf").exists()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a\x01b\x7f.pdf", "ab.pdf"),
        ("a" * 300 + ".pdf", None),
        ("", "document.pdf"),
        ("/", "document.pdf"),
        ("\x01\x02", "document.pdf"),
    ],
)
def test_display_name(raw: str, expected: str | None) -> None:
    from feynman_api.routes.documents import display_name

    out = display_name(raw)
    if expected is None:
        assert len(out) == 255
    else:
        assert out == expected
    assert display_name(None) == "document.pdf"


def test_title_from_filename() -> None:
    from feynman_api.routes.documents import title_from_filename

    assert title_from_filename("Notes.PDF") == "Notes"
    assert title_from_filename(".pdf") == "Untitled PDF"
    assert len(title_from_filename("a" * 200 + ".pdf")) == 120


async def test_upload_requires_auth_and_csrf(
    api_client: httpx.AsyncClient, user_client: httpx.AsyncClient
) -> None:
    r = await api_client.post("/documents", content=multipart(PDF), headers=_CT)
    assert r.status_code == 401
    r = await user_client.post(
        "/documents",
        content=multipart(PDF),
        headers=_CT | {"Origin": "http://localhost:5173"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"


async def test_upload_db_failure_removes_file(
    user_client: httpx.AsyncClient,
    file_store: LocalFileStore,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr("feynman_api.routes.documents.enqueue", boom)
    r = await post(user_client, multipart(PDF))
    assert r.status_code == 500
    await assert_nothing_stored(db, file_store)
