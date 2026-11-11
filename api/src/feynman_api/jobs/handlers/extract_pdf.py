import asyncio
import uuid
from datetime import timedelta
from typing import Any

import pypdfium2 as pdfium
from pypdfium2 import PdfiumError
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.auth.rate_limit import hit, map_build_key
from feynman_api.jobs.queue import enqueue
from feynman_api.jobs.registry import PermanentJobError, WorkerContext
from feynman_api.models.document import Document, DocumentPage
from feynman_api.models.job import Job
from feynman_api.models.knowledge_map import KnowledgeMap, KnowledgeMapChunk
from feynman_api.storage import FileStore

MSG_UNREADABLE = "This file couldn't be read as a PDF."
MSG_TOO_MANY_PAGES = "This PDF has more than 200 pages."
MSG_NO_TEXT = "This PDF looks scanned or has no selectable text, so it can't be read yet."
MSG_TOO_MUCH_TEXT = "This PDF has too much text to process yet."
MSG_MAP_LIMIT = "You've reached today's limit for building Knowledge Maps. Use Rebuild later."


def _extract_pages(file_store: FileStore, key: str, max_pages: int) -> list[str]:
    """Blocking: read the file and return the text of each page."""
    try:
        fh = file_store.open(key)
    except FileNotFoundError:
        raise PermanentJobError(MSG_UNREADABLE) from None
    try:
        try:
            pdf = pdfium.PdfDocument(fh)
        except PdfiumError:
            raise PermanentJobError(MSG_UNREADABLE) from None
        try:
            if len(pdf) > max_pages:
                raise PermanentJobError(MSG_TOO_MANY_PAGES)
            texts: list[str] = []
            for index in range(len(pdf)):
                page = pdf[index]
                try:
                    textpage = page.get_textpage()
                    try:
                        # Postgres text cannot store NUL.
                        texts.append(textpage.get_text_range().replace("\x00", ""))
                    finally:
                        textpage.close()
                except PdfiumError:
                    raise PermanentJobError(MSG_UNREADABLE) from None
                finally:
                    page.close()
            return texts
        finally:
            pdf.close()
    finally:
        fh.close()


async def _start_map_build(db: AsyncSession, job: Job, ctx: WorkerContext, doc: Document) -> None:
    """Create or reset the set's map and queue its build, in the caller's transaction."""
    kmap = (
        await db.execute(
            select(KnowledgeMap)
            .where(KnowledgeMap.study_set_id == doc.study_set_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if kmap is None:
        kmap = KnowledgeMap(study_set_id=doc.study_set_id, document_id=doc.id, status="processing")
        db.add(kmap)
    else:
        kmap.document_id = doc.id
        kmap.status = "processing"
    kmap.error_message = None
    await db.flush()
    await db.execute(delete(KnowledgeMapChunk).where(KnowledgeMapChunk.knowledge_map_id == kmap.id))

    settings = ctx.settings
    limit = await hit(
        db,
        map_build_key(job.user_id),
        settings.map_build_limit,
        timedelta(seconds=settings.llm_limit_window_seconds),
        ctx.clock(),
        commit=False,
    )
    if not limit.allowed:
        kmap.status = "failed"
        kmap.error_message = MSG_MAP_LIMIT
        return
    await enqueue(
        db,
        kind="build_knowledge_map",
        payload={"knowledge_map_id": str(kmap.id)},
        user_id=job.user_id,
    )


class ExtractPdfHandler:
    async def run(self, db: AsyncSession, job: Job, ctx: WorkerContext) -> dict[str, Any] | None:
        document_id = uuid.UUID(job.payload["document_id"])
        storage_key = (
            await db.execute(select(Document.storage_key).where(Document.id == document_id))
        ).scalar_one_or_none()
        if storage_key is None:
            return {"skipped": "document_deleted"}
        # End the read transaction: no lock, and no idle transaction, while parsing.
        await db.rollback()

        texts = await asyncio.to_thread(
            _extract_pages, ctx.file_store, storage_key, ctx.settings.max_pdf_pages
        )

        doc = (
            await db.execute(select(Document).where(Document.id == document_id).with_for_update())
        ).scalar_one_or_none()
        if doc is None:
            return {"skipped": "document_deleted"}

        # A reclaimed job may run again: replace, never append.
        await db.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))
        db.add_all(
            DocumentPage(document_id=doc.id, page_number=i, text=text)
            for i, text in enumerate(texts, start=1)
        )
        doc.page_count = len(texts)

        if sum(len("".join(t.split())) for t in texts) < ctx.settings.min_document_text_chars:
            raise PermanentJobError(MSG_NO_TEXT)
        if sum(len(t) for t in texts) > ctx.settings.max_document_text_chars:
            raise PermanentJobError(MSG_TOO_MUCH_TEXT)

        doc.status = "ready"
        doc.error_message = None
        await _start_map_build(db, job, ctx, doc)
        return {"page_count": len(texts)}

    async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None:
        document_id = uuid.UUID(job.payload["document_id"])
        doc = (
            await db.execute(select(Document).where(Document.id == document_id).with_for_update())
        ).scalar_one_or_none()
        if doc is not None:
            doc.status = "failed"
            doc.error_message = user_message

    async def failure_fallback(self, db: AsyncSession, job: Job, user_message: str) -> None:
        """Minimal fallback when on_failed raised: one guarded UPDATE, nothing else."""
        document_id = uuid.UUID(job.payload["document_id"])
        await db.execute(
            update(Document)
            .where(Document.id == document_id, Document.status == "processing")
            .values(status="failed", error_message=user_message)
            .execution_options(synchronize_session=False)
        )
