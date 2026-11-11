import asyncio
import subprocess
import sys
import threading
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from conftest import FrozenClock
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from feynman_api.auth.rate_limit import hit, map_build_key
from feynman_api.config import Settings
from feynman_api.db import create_sessionmaker
from feynman_api.jobs.handlers.extract_pdf import (
    MSG_MAP_LIMIT,
    MSG_NO_TEXT,
    MSG_TOO_MANY_PAGES,
    MSG_TOO_MUCH_TEXT,
    MSG_UNREADABLE,
    ExtractPdfHandler,
    _extract_pages,
)
from feynman_api.jobs.queue import enqueue
from feynman_api.jobs.registry import GENERIC_FAILURE, JobHandler, WorkerContext
from feynman_api.jobs.worker import run_once
from feynman_api.models.document import Document, DocumentPage
from feynman_api.models.job import Job
from feynman_api.models.knowledge_map import KnowledgeMap, KnowledgeMapChunk
from feynman_api.models.study_set import StudySet
from feynman_api.models.user import User
from feynman_api.storage import LocalFileStore, new_storage_key

FIXTURES = Path(__file__).parent / "fixtures"


class _NoopBuildHandler:
    async def run(self, db: AsyncSession, job: Job, ctx: WorkerContext) -> dict[str, Any] | None:
        return None

    async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None:
        pass


HANDLERS: dict[str, JobHandler] = {
    "extract_pdf": ExtractPdfHandler(),
    "build_knowledge_map": _NoopBuildHandler(),
}


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
    return WorkerContext(settings=test_settings, file_store=file_store, clock=FrozenClock())


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
        second = await enqueue(
            s, kind="extract_pdf", payload={"document_id": str(did)}, user_id=uid
        )
        await s.commit()
    assert await run_once(sm, ctx, HANDLERS) is True  # the queued (no-op) build job
    assert await run_once(sm, ctx, HANDLERS) is True  # the re-extraction
    assert (await _job(sm, second.id)).status == "succeeded"
    assert len(await _pages(sm, did)) == 3
    assert (await _doc(sm, did)).status == "ready"


async def test_too_many_pages_fails_with_message(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, jid, _ = await _setup(sm, file_store, "too_many_pages.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.status == "failed"
    assert doc.error_message == MSG_TOO_MANY_PAGES
    assert await _pages(sm, did) == []
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


class _FakeTextPage:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_text_range(self) -> str:
        return self._text

    def close(self) -> None:
        pass


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_textpage(self) -> _FakeTextPage:
        return _FakeTextPage(self._text)

    def close(self) -> None:
        pass


def _fake_pdf(texts: list[str]):  # type: ignore[no-untyped-def]
    class FakePdf:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __len__(self) -> int:
            return len(texts)

        def __getitem__(self, i: int) -> _FakePage:
            return _FakePage(texts[i])

        def close(self) -> None:
            pass

    return FakePdf


async def test_nul_characters_are_stripped(sm, ctx, file_store, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    text = "ab\x00c " * 40  # 120 non-whitespace chars after stripping NULs
    monkeypatch.setattr(
        "feynman_api.jobs.handlers.extract_pdf.pdfium.PdfDocument", _fake_pdf([text])
    )
    did, jid, _ = await _setup(sm, file_store, "text.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.status == "ready"
    pages = await _pages(sm, did)
    assert len(pages) == 1
    assert "\x00" not in pages[0].text
    assert (await _job(sm, jid)).attempts == 1


async def test_only_nul_and_whitespace_is_no_text(sm, ctx, file_store, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    text = "\x00 \n\t" * 100
    monkeypatch.setattr(
        "feynman_api.jobs.handlers.extract_pdf.pdfium.PdfDocument", _fake_pdf([text])
    )
    did, jid, _ = await _setup(sm, file_store, "text.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.status == "failed"
    assert doc.error_message == MSG_NO_TEXT
    assert (await _job(sm, jid)).attempts == 1


async def test_broken_on_failed_still_fails_document(  # type: ignore[no-untyped-def]
    sm, ctx, file_store, monkeypatch
) -> None:
    async def broken_on_failed(self, db, job, user_message) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("on_failed broke")

    def boom(*args: object, **kwargs: object) -> list[str]:
        raise RuntimeError("boom")

    monkeypatch.setattr(ExtractPdfHandler, "on_failed", broken_on_failed)
    monkeypatch.setattr("feynman_api.jobs.handlers.extract_pdf._extract_pages", boom)
    did, jid, _ = await _setup(sm, file_store, "text.pdf")
    for _ in range(3):
        await _make_due(sm, jid)
        assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.status == "failed"
    assert doc.error_message == GENERIC_FAILURE
    job = await _job(sm, jid)
    assert job.status == "failed"
    assert job.locked_until is None


async def _maps(sm: async_sessionmaker[AsyncSession]) -> list[KnowledgeMap]:
    async with sm() as s:
        return list((await s.execute(select(KnowledgeMap))).scalars())


async def _build_jobs(sm: async_sessionmaker[AsyncSession]) -> list[Job]:
    async with sm() as s:
        res = await s.execute(select(Job).where(Job.kind == "build_knowledge_map"))
        return list(res.scalars())


async def test_ready_creates_map_and_job_atomically(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, jid, ssid = await _setup(sm, file_store, "text.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    assert (await _doc(sm, did)).status == "ready"
    assert (await _job(sm, jid)).result == {"page_count": 3}
    maps = await _maps(sm)
    assert len(maps) == 1
    kmap = maps[0]
    assert kmap.study_set_id == ssid
    assert kmap.document_id == did
    assert kmap.status == "processing"
    assert kmap.error_message is None
    jobs = await _build_jobs(sm)
    assert len(jobs) == 1
    assert jobs[0].status == "queued"
    assert jobs[0].payload == {"knowledge_map_id": str(kmap.id)}
    assert jobs[0].user_id == (await _job(sm, jid)).user_id


async def test_ready_rolls_back_map_and_job_when_lease_lost(  # type: ignore[no-untyped-def]
    sm, ctx, file_store, monkeypatch
) -> None:
    """The map and its job commit only with mark_succeeded: a lost lease leaves neither."""

    async def lost(*args: object, **kwargs: object) -> bool:
        return False

    monkeypatch.setattr("feynman_api.jobs.worker.mark_succeeded", lost)
    did, _, _ = await _setup(sm, file_store, "text.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    assert (await _doc(sm, did)).status == "processing"
    assert await _maps(sm) == []
    assert await _build_jobs(sm) == []


async def test_map_limit_reached_fails_map_without_job(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, jid, _ = await _setup(sm, file_store, "text.pdf")
    uid = (await _job(sm, jid)).user_id
    window = timedelta(seconds=ctx.settings.llm_limit_window_seconds)
    async with sm() as s:
        for _ in range(ctx.settings.map_build_limit):
            await hit(s, map_build_key(uid), ctx.settings.map_build_limit, window, ctx.clock())
    assert await run_once(sm, ctx, HANDLERS) is True
    assert (await _doc(sm, did)).status == "ready"
    maps = await _maps(sm)
    assert len(maps) == 1
    assert maps[0].status == "failed"
    assert maps[0].error_message == MSG_MAP_LIMIT
    assert await _build_jobs(sm) == []
    assert (await _job(sm, jid)).status == "succeeded"


async def test_map_limit_counts_each_build(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    """With one build left, the build is allowed (the limit is inclusive)."""
    _, jid, _ = await _setup(sm, file_store, "text.pdf")
    uid = (await _job(sm, jid)).user_id
    window = timedelta(seconds=ctx.settings.llm_limit_window_seconds)
    async with sm() as s:
        for _ in range(ctx.settings.map_build_limit - 1):
            await hit(s, map_build_key(uid), ctx.settings.map_build_limit, window, ctx.clock())
    assert await run_once(sm, ctx, HANDLERS) is True
    maps = await _maps(sm)
    assert [m.status for m in maps] == ["processing"]
    assert len(await _build_jobs(sm)) == 1


async def test_too_much_text_fails(sm, ctx, file_store, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(ctx.settings, "max_document_text_chars", 50)
    did, jid, _ = await _setup(sm, file_store, "text.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.status == "failed"
    assert doc.error_message == MSG_TOO_MUCH_TEXT
    assert await _pages(sm, did) == []
    assert await _maps(sm) == []
    assert await _build_jobs(sm) == []
    assert (await _job(sm, jid)).attempts == 1


async def test_text_at_cap_is_allowed(sm, ctx, file_store, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    page = "word " * 40  # 200 raw characters
    monkeypatch.setattr(
        "feynman_api.jobs.handlers.extract_pdf.pdfium.PdfDocument", _fake_pdf([page, page])
    )
    monkeypatch.setattr(ctx.settings, "max_document_text_chars", 400)
    did, _, _ = await _setup(sm, file_store, "text.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    assert (await _doc(sm, did)).status == "ready"
    monkeypatch.setattr(ctx.settings, "max_document_text_chars", 399)
    async with sm() as s:
        uid = (await s.execute(select(User.id))).scalar_one()
        await enqueue(s, kind="extract_pdf", payload={"document_id": str(did)}, user_id=uid)
        await s.commit()
    # Run the queued no-op build job, then the second extraction.
    assert await run_once(sm, ctx, HANDLERS) is True
    assert await run_once(sm, ctx, HANDLERS) is True
    doc = await _doc(sm, did)
    assert doc.error_message == MSG_TOO_MUCH_TEXT


async def test_document_row_not_locked_while_parsing(  # type: ignore[no-untyped-def]
    sm, ctx, file_store, monkeypatch
) -> None:
    started = threading.Event()
    release = threading.Event()

    def blocking(*args: Any) -> list[str]:
        started.set()
        release.wait(timeout=5)
        return _extract_pages(*args)

    monkeypatch.setattr("feynman_api.jobs.handlers.extract_pdf._extract_pages", blocking)
    did, _, _ = await _setup(sm, file_store, "text.pdf")
    task = asyncio.create_task(run_once(sm, ctx, HANDLERS))
    try:
        assert await asyncio.to_thread(started.wait, 5)
        async with sm() as s:
            # The handler's session must not sit idle in a transaction while parsing.
            idle = (
                await s.execute(
                    select(func.count())
                    .select_from(text("pg_stat_activity"))
                    .where(
                        text("datname = current_database()"),
                        text("state = 'idle in transaction'"),
                        text("pid <> pg_backend_pid()"),
                    )
                )
            ).scalar_one()
            assert idle == 0
            await s.execute(text("SET LOCAL lock_timeout = '1s'"))
            await s.execute(
                update(Document).where(Document.id == did).values(original_filename="x.pdf")
            )
            await s.commit()
    finally:
        release.set()
    assert await task is True
    doc = await _doc(sm, did)
    assert doc.status == "ready"
    assert doc.original_filename == "x.pdf"


async def test_document_deleted_while_parsing_is_noop(  # type: ignore[no-untyped-def]
    sm, ctx, file_store, monkeypatch
) -> None:
    parsed = threading.Event()
    deleted = threading.Event()

    def parse_then_wait(*args: Any) -> list[str]:
        texts = _extract_pages(*args)
        parsed.set()
        deleted.wait(timeout=5)
        return texts

    monkeypatch.setattr("feynman_api.jobs.handlers.extract_pdf._extract_pages", parse_then_wait)
    _, jid, ssid = await _setup(sm, file_store, "text.pdf")
    task = asyncio.create_task(run_once(sm, ctx, HANDLERS))
    try:
        assert await asyncio.to_thread(parsed.wait, 5)
        async with sm() as s:
            await s.execute(text("SET LOCAL lock_timeout = '1s'"))
            ss = (await s.execute(select(StudySet).where(StudySet.id == ssid))).scalar_one()
            await s.delete(ss)
            await s.commit()
    finally:
        deleted.set()
    assert await task is True
    job = await _job(sm, jid)
    assert job.status == "succeeded"
    assert job.result == {"skipped": "document_deleted"}
    assert await _maps(sm) == []
    assert await _build_jobs(sm) == []


async def test_failure_creates_no_map(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, _, _ = await _setup(sm, file_store, "corrupt.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    assert (await _doc(sm, did)).status == "failed"
    assert await _maps(sm) == []
    assert await _build_jobs(sm) == []


async def test_reextraction_reuses_map_and_clears_chunks(sm, ctx, file_store) -> None:  # type: ignore[no-untyped-def]
    did, _, _ = await _setup(sm, file_store, "text.pdf")
    assert await run_once(sm, ctx, HANDLERS) is True
    first = (await _maps(sm))[0]
    async with sm() as s:
        await s.execute(
            update(KnowledgeMap)
            .where(KnowledgeMap.id == first.id)
            .values(status="failed", error_message="old")
        )
        s.add(
            KnowledgeMapChunk(
                knowledge_map_id=first.id, chunk_index=0, page_start=1, page_end=3, status="done"
            )
        )
        uid = (await s.execute(select(User.id))).scalar_one()
        second = await enqueue(
            s, kind="extract_pdf", payload={"document_id": str(did)}, user_id=uid
        )
        await s.commit()
    assert await run_once(sm, ctx, HANDLERS) is True  # the first (no-op) build job
    assert await run_once(sm, ctx, HANDLERS) is True  # the re-extraction
    assert (await _job(sm, second.id)).status == "succeeded"
    assert len(await _pages(sm, did)) == 3  # replaced, not appended
    maps = await _maps(sm)
    assert len(maps) == 1
    assert maps[0].id == first.id
    assert maps[0].status == "processing"
    assert maps[0].error_message is None
    async with sm() as s:
        chunks = (await s.execute(select(KnowledgeMapChunk))).scalars().all()
    assert chunks == []
    assert len(await _build_jobs(sm)) == 2
