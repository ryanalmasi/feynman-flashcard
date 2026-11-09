import subprocess
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from feynman_api.config import Settings
from feynman_api.db import create_sessionmaker
from feynman_api.jobs.handlers.extract_pdf import (
    MSG_NO_TEXT,
    MSG_TOO_MANY_PAGES,
    MSG_UNREADABLE,
    ExtractPdfHandler,
)
from feynman_api.jobs.queue import enqueue
from feynman_api.jobs.registry import GENERIC_FAILURE, WorkerContext
from feynman_api.jobs.worker import run_once
from feynman_api.models.document import Document, DocumentPage
from feynman_api.models.job import Job
from feynman_api.models.study_set import StudySet
from feynman_api.models.user import User
from feynman_api.storage import LocalFileStore, new_storage_key

FIXTURES = Path(__file__).parent / "fixtures"
HANDLERS = {"extract_pdf": ExtractPdfHandler()}


@pytest.fixture
async def sm(
    clean_db: None, test_settings: Settings
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine: AsyncEngine = create_async_engine(test_settings.database_url.get_secret_value())
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest.fixture
def ctx(test_settings: Settings, file_store: LocalFileStore) -> WorkerContext:
    return WorkerContext(settings=test_settings, file_store=file_store)


async def _setup(
    sm: async_sessionmaker[AsyncSession],
    file_store: LocalFileStore,
    fixture: str | None,
) -> tuple[UUID, UUID, UUID]:
    """Create user, study set, document (+ file from fixture) and job. Returns ids."""
    key = new_storage_key()
    if fixture is not None:

        async def chunks() -> AsyncIterator[bytes]:
            yield (FIXTURES / fixture).read_bytes()

        await file_store.put(key, chunks())
    async with sm() as s:
        user = User(email="x@example.com")
        s.add(user)
        await s.flush()
        ss = StudySet(user_id=user.id, title="T")
        s.add(ss)
        await s.flush()
        doc = Document(
            study_set_id=ss.id,
            storage_key=key,
            original_filename="a.pdf",
            size_bytes=1,
            status="processing",
        )
        s.add(doc)
        await s.flush()
        job = await enqueue(
            s, kind="extract_pdf", payload={"document_id": str(doc.id)}, user_id=user.id
        )
        await s.commit()
        return doc.id, job.id, ss.id


async def _doc(sm: async_sessionmaker[AsyncSession], did: UUID) -> Document:
    async with sm() as s:
        return (await s.execute(select(Document).where(Document.id == did))).scalar_one()


async def _pages(sm: async_sessionmaker[AsyncSession], did: UUID) -> list[DocumentPage]:
    async with sm() as s:
        res = await s.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == did)
            .order_by(DocumentPage.page_number)
        )
        return list(res.scalars())


async def _job(sm: async_sessionmaker[AsyncSession], jid: UUID) -> Job:
    async with sm() as s:
        return (await s.execute(select(Job).where(Job.id == jid))).scalar_one()


async def _make_due(sm: async_sessionmaker[AsyncSession], jid: UUID) -> None:
    async with sm() as s:
        await s.execute(
            update(Job)
            .where(Job.id == jid)
            .values(run_after=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()


async def test_text_pdf_becomes_ready(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, jid, _ = await _setup(sm, file_store, "text.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.status == "ready"
    assert doc.page_count == 3
    assert doc.error_message is None
    pages = await _pages(sm, did)
    assert [p.page_number for p in pages] == [1, 2, 3]
    assert "Photosynthesis converts light energy" in pages[0].text
    assert "Mitochondria produce most of the ATP" in pages[1].text
    assert "Krebs cycle oxidizes" in pages[2].text
    job = await _job(sm, jid)
    assert job.status == "succeeded"
    assert job.result == {"page_count": 3}


async def test_reprocessing_replaces_pages(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, _, _ = await _setup(sm, file_store, "text.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    async with sm() as s:
        uid = (await s.execute(select(User.id))).scalar_one()
        await enqueue(s, kind="extract_pdf", payload={"document_id": str(did)}, user_id=uid)
        await s.commit()
    assert await run_once(sm, ctx, HANDLERS) is True
    assert len(await _pages(sm, did)) == 3
    assert (await _doc(sm, did)).status == "ready"


async def test_too_many_pages_fails_with_message(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, jid, _ = await _setup(sm, file_store, "too_many_pages.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.status == "failed"
    assert doc.error_message == MSG_TOO_MANY_PAGES
    job = await _job(sm, jid)
    assert job.status == "failed"
    assert job.attempts == 1


async def test_image_only_fails_with_message(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, _, _ = await _setup(sm, file_store, "image_only.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.status == "failed"
    assert doc.error_message == MSG_NO_TEXT
    assert await _pages(sm, did) == []


async def test_corrupt_pdf_fails_with_message(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, _, _ = await _setup(sm, file_store, "corrupt.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.status == "failed"
    assert doc.error_message == MSG_UNREADABLE


async def test_missing_file_fails_unreadable(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, _, _ = await _setup(sm, file_store, None)
    assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.status == "failed"
    assert doc.error_message == MSG_UNREADABLE


async def test_document_deleted_mid_processing_is_noop(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    _, jid, ssid = await _setup(sm, file_store, "text.pdf")
    async with sm() as s:
        ss = (await s.execute(select(StudySet).where(StudySet.id == ssid))).scalar_one()
        await s.delete(ss)
        await s.commit()
    assert await run_once(sm, ctx, HANDLERS) is True
    job = await _job(sm, jid)
    assert job.status == "succeeded"
    assert job.result == {"skipped": "document_deleted"}


async def test_unexpected_error_exhausts_to_generic(  # type: ignore[no-untyped-def]
    sm, ctx, file_store, monkeypatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("secret path /etc/passwd")

    monkeypatch.setattr("feynman_api.jobs.handlers.extract_pdf.pdfium.PdfDocument", boom)
    did, jid, _ = await _setup(sm, file_store, "text.pdf")
    for _ in range(3):
        assert await run_once(sm, ctx, HANDLERS) is True
        assert (await _doc(sm, did)).status in ("processing", "failed")
        await _make_due(sm, jid)
    doc = await _doc(sm, did)
    assert doc.status == "failed"
    assert doc.error_message == GENERIC_FAILURE
    assert (await _job(sm, jid)).status == "failed"


def test_extraction_not_imported_by_api() -> None:
    code = "import sys, feynman_api.main; sys.exit(1 if 'pypdfium2' in sys.modules else 0)"
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
