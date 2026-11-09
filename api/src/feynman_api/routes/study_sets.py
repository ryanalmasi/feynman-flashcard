import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.auth.dependencies import CurrentUser, current_user
from feynman_api.auth.ownership import get_owned_set
from feynman_api.db import get_session
from feynman_api.errors import ErrorResponse
from feynman_api.models import Document, Flashcard, StudySet
from feynman_api.routes.schemas import (
    DocumentSummary,
    StudySetCreate,
    StudySetOut,
    StudySetUpdate,
)
from feynman_api.storage import FileStore, get_file_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/study-sets", tags=["study-sets"])

Db = Annotated[AsyncSession, Depends(get_session)]
Current = Annotated[CurrentUser, Depends(current_user)]
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


async def _outs(
    db: AsyncSession, user_id: uuid.UUID, set_id: uuid.UUID | None
) -> list[StudySetOut]:
    """Owner-scoped sets with card_count and document in ONE query (no N+1)."""
    counts = (
        select(Flashcard.study_set_id, func.count().label("n"))
        .group_by(Flashcard.study_set_id)
        .subquery()
    )
    stmt = (
        select(StudySet, func.coalesce(counts.c.n, 0), Document)
        .outerjoin(counts, counts.c.study_set_id == StudySet.id)
        .outerjoin(Document, Document.study_set_id == StudySet.id)
        .where(StudySet.user_id == user_id)
        .order_by(StudySet.created_at.desc(), StudySet.id.desc())
    )
    if set_id is not None:
        stmt = stmt.where(StudySet.id == set_id)
    result: list[StudySetOut] = []
    for s, n, doc in (await db.execute(stmt)).all():
        result.append(
            StudySetOut(
                id=s.id,
                title=s.title,
                description=s.description,
                card_count=n,
                document=(
                    DocumentSummary(
                        id=doc.id,
                        status=doc.status,
                        page_count=doc.page_count,
                        original_filename=doc.original_filename,
                        error_message=doc.error_message,
                    )
                    if doc is not None
                    else None
                ),
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return result


async def _out(db: AsyncSession, user_id: uuid.UUID, set_id: uuid.UUID) -> StudySetOut:
    (out,) = await _outs(db, user_id, set_id)
    return out


@router.get("", response_model=list[StudySetOut], responses={401: {"model": ErrorResponse}})
async def list_study_sets(db: Db, current: Current) -> list[StudySetOut]:
    return await _outs(db, current.user.id, None)


@router.post("", status_code=201, response_model=StudySetOut, responses=_ERRORS)
async def create_study_set(body: StudySetCreate, db: Db, current: Current) -> StudySetOut:
    study_set = StudySet(user_id=current.user.id, title=body.title, description=body.description)
    db.add(study_set)
    await db.commit()
    return await _out(db, current.user.id, study_set.id)


@router.get("/{set_id}", response_model=StudySetOut, responses=_ERRORS)
async def get_study_set(set_id: uuid.UUID, db: Db, current: Current) -> StudySetOut:
    study_set = await get_owned_set(db, current.user.id, set_id)
    return await _out(db, current.user.id, study_set.id)


@router.patch("/{set_id}", response_model=StudySetOut, responses=_ERRORS)
async def update_study_set(
    set_id: uuid.UUID, body: StudySetUpdate, db: Db, current: Current
) -> StudySetOut:
    study_set = await get_owned_set(db, current.user.id, set_id)
    if "title" in body.model_fields_set and body.title is not None:
        study_set.title = body.title
    if "description" in body.model_fields_set:
        study_set.description = body.description
    await db.commit()
    return await _out(db, current.user.id, study_set.id)


@router.delete("/{set_id}", status_code=204, responses=_ERRORS)
async def delete_study_set(
    set_id: uuid.UUID,
    db: Db,
    current: Current,
    file_store: Annotated[FileStore, Depends(get_file_store)],
) -> Response:
    study_set = await get_owned_set(db, current.user.id, set_id)
    key = (
        await db.execute(select(Document.storage_key).where(Document.study_set_id == study_set.id))
    ).scalar_one_or_none()
    await db.execute(
        delete(StudySet).where(StudySet.id == study_set.id, StudySet.user_id == current.user.id)
    )
    await db.commit()
    if key is not None:
        try:
            await file_store.delete(key)
        except Exception as exc:
            logger.warning("failed to delete stored file %s (%s)", key, type(exc).__name__)
    return Response(status_code=204)
