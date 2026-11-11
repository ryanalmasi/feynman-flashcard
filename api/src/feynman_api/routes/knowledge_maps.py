import uuid
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.auth.dependencies import CurrentUser, current_user
from feynman_api.auth.ownership import get_owned_concept, get_owned_map, get_owned_set
from feynman_api.auth.rate_limit import hit, map_build_key
from feynman_api.clock import Clock, get_clock
from feynman_api.config import Settings
from feynman_api.db import get_session
from feynman_api.errors import (
    CARDS_PROCESSING,
    MAP_FULL,
    MAP_NOT_READY,
    MAP_PROCESSING,
    ErrorResponse,
    conflict,
    not_found,
    rate_limited,
)
from feynman_api.jobs.queue import enqueue
from feynman_api.knowledge.limits import CONCEPTS_MAX
from feynman_api.models import Concept, Document, KnowledgeMap, KnowledgeMapChunk
from feynman_api.routes.schemas import (
    ConceptCreate,
    ConceptOrder,
    ConceptOut,
    ConceptUpdate,
    KnowledgeMapOut,
)

router = APIRouter(tags=["knowledge-maps"])

Db = Annotated[AsyncSession, Depends(get_session)]
Current = Annotated[CurrentUser, Depends(current_user)]
Now = Annotated[Clock, Depends(get_clock)]
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}
_MUTATION_ERRORS: dict[int | str, dict[str, Any]] = _ERRORS | {409: {"model": ErrorResponse}}
_REBUILD_ERRORS: dict[int | str, dict[str, Any]] = _MUTATION_ERRORS | {
    429: {"model": ErrorResponse}
}
_PAGES_MSG = "page numbers must be within the document"
_ORDER_MSG = "must list each of the map's concepts exactly once"

# Check order in every mutating route (design §7.3): owned lookup (404), map row FOR UPDATE,
# state checks (409), DB-dependent validation (422), rebuild's non-committing rate-limit count
# (429), writes and enqueue, then ONE commit. So a 404/409/422 never uses up a build.


def _concept_out(concept: Concept) -> ConceptOut:
    return ConceptOut.model_validate(concept, from_attributes=True)


async def map_out(db: AsyncSession, km: KnowledgeMap) -> KnowledgeMapOut:
    """Explicit queries only: async lazy loading raises MissingGreenlet."""
    concepts = (
        await db.execute(
            select(Concept).where(Concept.knowledge_map_id == km.id).order_by(Concept.position)
        )
    ).scalars()
    filename = (
        await db.execute(select(Document.original_filename).where(Document.id == km.document_id))
    ).scalar_one()
    return KnowledgeMapOut(
        id=km.id,
        status=km.status,
        error_message=km.error_message,
        model_id=km.model_id,
        revision=km.revision,
        cards_status=km.cards_status,
        cards_error_message=km.cards_error_message,
        source_filename=filename,
        concepts=[_concept_out(c) for c in concepts],
    )


def _require_editable(km: KnowledgeMap) -> None:
    if km.status == "processing":
        raise conflict(MAP_PROCESSING)
    if km.status != "ready":
        raise conflict(MAP_NOT_READY)
    if km.cards_status == "processing":
        raise conflict(CARDS_PROCESSING)


async def _check_pages(db: AsyncSession, km: KnowledgeMap, pages: list[int] | None) -> None:
    if not pages:
        return
    page_count = (
        await db.execute(select(Document.page_count).where(Document.id == km.document_id))
    ).scalar_one()
    if page_count is not None and pages[-1] > page_count:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "source_pages"),
                    "msg": _PAGES_MSG,
                    "input": pages,
                }
            ]
        )


async def _commit(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError:
        # e.g. the deferred (map, position) constraint racing a build's final write.
        await db.rollback()
        raise conflict(MAP_PROCESSING) from None


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.get("/study-sets/{set_id}/knowledge-map", response_model=KnowledgeMapOut, responses=_ERRORS)
async def get_knowledge_map(set_id: uuid.UUID, db: Db, current: Current) -> KnowledgeMapOut:
    km = await get_owned_map(db, current.user.id, set_id)
    return await map_out(db, km)


@router.post(
    "/study-sets/{set_id}/knowledge-map/rebuild",
    status_code=202,
    response_model=KnowledgeMapOut,
    responses=_REBUILD_ERRORS,
)
async def rebuild_knowledge_map(
    set_id: uuid.UUID, request: Request, db: Db, current: Current, now: Now
) -> KnowledgeMapOut:
    study_set = await get_owned_set(db, current.user.id, set_id)
    km = (
        await db.execute(
            select(KnowledgeMap)
            .where(KnowledgeMap.study_set_id == study_set.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    new_map_document: uuid.UUID | None = None  # set exactly when km is None past here
    if km is None:
        # A set uploaded in 2a: a ready document and no map. Rebuild creates the map.
        doc = (
            await db.execute(select(Document).where(Document.study_set_id == study_set.id))
        ).scalar_one_or_none()
        if doc is None or doc.status == "failed":
            raise not_found()
        new_map_document = doc.id
        if doc.status == "processing":
            raise conflict(MAP_PROCESSING)  # extract_pdf creates the map when it finishes
    elif km.status == "processing":
        raise conflict(MAP_PROCESSING)
    elif km.cards_status == "processing":
        raise conflict(CARDS_PROCESSING)

    settings = _settings(request)
    limit = await hit(
        db,
        map_build_key(current.user.id),
        settings.map_build_limit,
        timedelta(seconds=settings.llm_limit_window_seconds),
        now(),
        commit=False,
    )
    if not limit.allowed:
        raise rate_limited(limit.retry_after)  # nothing committed: the session rolls back

    if km is None:
        km = KnowledgeMap(
            study_set_id=study_set.id, document_id=new_map_document, status="processing"
        )
        db.add(km)
        await db.flush()
    else:
        km.status = "processing"
        km.error_message = None
        # The concepts stay until the job succeeds and replaces them.
        await db.execute(
            delete(KnowledgeMapChunk).where(KnowledgeMapChunk.knowledge_map_id == km.id)
        )
    await enqueue(
        db,
        kind="build_knowledge_map",
        payload={"knowledge_map_id": str(km.id)},
        user_id=current.user.id,
    )
    await _commit(db)
    return await map_out(db, km)


@router.post(
    "/study-sets/{set_id}/concepts",
    status_code=201,
    response_model=ConceptOut,
    responses=_MUTATION_ERRORS,
)
async def create_concept(
    set_id: uuid.UUID, body: ConceptCreate, db: Db, current: Current
) -> ConceptOut:
    km = await get_owned_map(db, current.user.id, set_id, for_update=True)
    _require_editable(km)
    count, max_position = (
        await db.execute(
            select(func.count(), func.max(Concept.position)).where(
                Concept.knowledge_map_id == km.id
            )
        )
    ).one()
    if count >= CONCEPTS_MAX:
        raise conflict(MAP_FULL)
    await _check_pages(db, km, body.source_pages)
    concept = Concept(
        knowledge_map_id=km.id,
        position=0 if max_position is None else max_position + 1,
        title=body.title,
        explanation=body.explanation,
        importance=body.importance,
        key_terms=[kt.model_dump() for kt in body.key_terms],
        misconceptions=list(body.misconceptions),
        source_pages=list(body.source_pages),
    )
    db.add(concept)
    km.revision += 1
    await _commit(db)
    return _concept_out(concept)


@router.patch("/concepts/{concept_id}", response_model=ConceptOut, responses=_MUTATION_ERRORS)
async def update_concept(
    concept_id: uuid.UUID, body: ConceptUpdate, db: Db, current: Current
) -> ConceptOut:
    concept, km = await get_owned_concept(db, current.user.id, concept_id, lock_map=True)
    _require_editable(km)
    await _check_pages(db, km, body.source_pages)
    if body.title is not None:
        concept.title = body.title
    if body.explanation is not None:
        concept.explanation = body.explanation
    if body.importance is not None:
        concept.importance = body.importance
    if body.key_terms is not None:
        concept.key_terms = [kt.model_dump() for kt in body.key_terms]
    if body.misconceptions is not None:
        concept.misconceptions = list(body.misconceptions)
    if body.source_pages is not None:
        concept.source_pages = list(body.source_pages)
    km.revision += 1
    await _commit(db)
    return _concept_out(concept)


@router.delete("/concepts/{concept_id}", status_code=204, responses=_MUTATION_ERRORS)
async def delete_concept(concept_id: uuid.UUID, db: Db, current: Current) -> Response:
    concept, km = await get_owned_concept(db, current.user.id, concept_id, lock_map=True)
    _require_editable(km)
    # Cards keep their content (concept_id ON DELETE SET NULL); positions are not compacted.
    await db.execute(delete(Concept).where(Concept.id == concept.id))
    km.revision += 1
    await _commit(db)
    return Response(status_code=204)


@router.put(
    "/study-sets/{set_id}/knowledge-map/order",
    response_model=KnowledgeMapOut,
    responses=_MUTATION_ERRORS,
)
async def order_concepts(
    set_id: uuid.UUID, body: ConceptOrder, db: Db, current: Current
) -> KnowledgeMapOut:
    km = await get_owned_map(db, current.user.id, set_id, for_update=True)
    _require_editable(km)
    concepts = {
        c.id: c
        for c in (
            await db.execute(
                select(Concept)
                .where(Concept.knowledge_map_id == km.id)
                .execution_options(populate_existing=True)
            )
        ).scalars()
    }
    ids = body.concept_ids
    if len(ids) != len(set(ids)) or set(ids) != set(concepts):
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "concept_ids"),
                    "msg": _ORDER_MSG,
                    "input": [str(i) for i in ids],
                }
            ]
        )
    for position, cid in enumerate(ids):
        concepts[cid].position = position  # (map, position) is unique DEFERRED: checked at commit
    km.revision += 1
    await _commit(db)
    return await map_out(db, km)
