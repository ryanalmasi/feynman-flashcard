import asyncio
import uuid
from typing import Any

import pypdfium2 as pdfium
from pypdfium2 import PdfiumError
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.jobs.registry import PermanentJobError, WorkerContext
from feynman_api.models.document import Document, DocumentPage
from feynman_api.models.job import Job
from feynman_api.storage import FileStore

MSG_UNREADABLE = "This file couldn't be read as a PDF."
MSG_TOO_MANY_PAGES = "This PDF has more than 200 pages."
MSG_NO_TEXT = "This PDF looks scanned or has no selectable text, so it can't be read yet."


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


class ExtractPdfHandler:
    async def run(self, db: AsyncSession, job: Job, ctx: WorkerContext) -> dict[str, Any] | None:
        document_id = uuid.UUID(job.payload["document_id"])
        doc = (
            await db.execute(select(Document).where(Document.id == document_id).with_for_update())
        ).scalar_one_or_none()
        if doc is None:
            return {"skipped": "document_deleted"}

        texts = await asyncio.to_thread(
            _extract_pages, ctx.file_store, doc.storage_key, ctx.settings.max_pdf_pages
        )

        # A reclaimed job may run again: replace, never append.
        await db.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))
        db.add_all(
            DocumentPage(document_id=doc.id, page_number=i, text=text)
            for i, text in enumerate(texts, start=1)
        )
        doc.page_count = len(texts)

        if sum(len("".join(t.split())) for t in texts) < ctx.settings.min_document_text_chars:
            raise PermanentJobError(MSG_NO_TEXT)

        doc.status = "ready"
        doc.error_message = None
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
