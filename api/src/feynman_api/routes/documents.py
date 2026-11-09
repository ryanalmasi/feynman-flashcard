import asyncio
import re
import unicodedata
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.auth.dependencies import CurrentUser, current_user
from feynman_api.auth.ownership import get_owned_document
from feynman_api.db import get_session
from feynman_api.errors import ErrorResponse, file_too_large, unsupported_file_type
from feynman_api.jobs.queue import enqueue
from feynman_api.models import Document, StudySet
from feynman_api.routes.schemas import DocumentOut, DocumentSummary, StudySetOut, UploadOut
from feynman_api.storage import FileStore, get_file_store, new_storage_key

router = APIRouter(prefix="/documents", tags=["documents"])

Db = Annotated[AsyncSession, Depends(get_session)]
Current = Annotated[CurrentUser, Depends(current_user)]
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}
_UPLOAD_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    415: {"model": ErrorResponse},
}
_PDF_MAGIC = b"%PDF-"
_READ_SIZE = 64 * 1024
_DEFAULT_NAME = "document.pdf"
_FILENAME_MAX = 255
_TITLE_MAX = 120


def display_name(raw: str | None) -> str:
    """Sanitised display-only filename. Never used to build a path."""
    name = re.split(r"[/\\]", raw or "")[-1]
    # Drop control (Cc) and format (Cf, e.g. bidi overrides, zero-width) characters first.
    name = "".join(c for c in name if unicodedata.category(c) not in ("Cc", "Cf"))
    name = " ".join(name.split())
    return name[:_FILENAME_MAX].strip() or _DEFAULT_NAME


def title_from_filename(name: str) -> str:
    base = re.sub(r"\.pdf$", "", display_name(name), flags=re.IGNORECASE)
    return base[:_TITLE_MAX].strip() or "Untitled PDF"


def _validated_title(title: str | None) -> str | None:
    """Same constraints as StudySetCreate.title: strip, then 1-120 chars, no NUL."""
    stripped = (title or "").strip()
    if not stripped:
        return None
    if len(stripped) > _TITLE_MAX or "\x00" in stripped:
        raise RequestValidationError(
            [{"type": "value_error", "loc": ("body", "title"), "msg": "invalid title", "input": ""}]
        )
    return stripped


def _to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        study_set_id=doc.study_set_id,
        status=doc.status,
        page_count=doc.page_count,
        error_message=doc.error_message,
        original_filename=doc.original_filename,
    )


@router.post("", status_code=202, response_model=UploadOut, responses=_UPLOAD_ERRORS)
async def upload_document(
    request: Request,
    file: UploadFile,
    db: Db,
    current: Current,
    file_store: Annotated[FileStore, Depends(get_file_store)],
    title: Annotated[str | None, Form()] = None,
) -> UploadOut:
    max_bytes = request.app.state.settings.max_upload_bytes
    given_title = _validated_title(title)
    head = await file.read(len(_PDF_MAGIC))
    if head != _PDF_MAGIC:
        raise unsupported_file_type()

    async def chunks() -> AsyncIterator[bytes]:
        total = len(head)
        yield head
        while chunk := await file.read(_READ_SIZE):
            total += len(chunk)
            if total > max_bytes:
                raise file_too_large()
            yield chunk

    key = new_storage_key()
    size = await file_store.put(key, chunks())
    try:
        name = display_name(file.filename)
        study_set = StudySet(
            id=uuid.uuid4(),
            user_id=current.user.id,
            title=given_title or title_from_filename(name),
        )
        doc = Document(
            id=uuid.uuid4(),
            study_set_id=study_set.id,
            storage_key=key,
            original_filename=name,
            size_bytes=size,
            status="processing",
        )
        db.add(study_set)
        db.add(doc)
        await db.flush()
        await enqueue(
            db, kind="extract_pdf", payload={"document_id": str(doc.id)}, user_id=current.user.id
        )
        await db.refresh(study_set)  # load server-default timestamps before committing
        await db.commit()
    except BaseException:
        await asyncio.shield(file_store.delete(key))
        raise
    return UploadOut(
        study_set=StudySetOut(
            id=study_set.id,
            title=study_set.title,
            description=study_set.description,
            card_count=0,
            document=DocumentSummary(
                id=doc.id,
                status="processing",
                page_count=None,
                original_filename=doc.original_filename,
                error_message=None,
            ),
            created_at=study_set.created_at,
            updated_at=study_set.updated_at,
        ),
        document=_to_out(doc),
    )


@router.get("/{document_id}", response_model=DocumentOut, responses=_ERRORS)
async def get_document(document_id: uuid.UUID, db: Db, current: Current) -> DocumentOut:
    return _to_out(await get_owned_document(db, current.user.id, document_id))
