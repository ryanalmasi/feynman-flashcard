import uuid
from datetime import timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.auth.dependencies import CurrentUser, current_user
from feynman_api.auth.ownership import get_owned_card, get_owned_map, get_owned_set
from feynman_api.auth.rate_limit import card_generation_key, hit
from feynman_api.clock import Clock, get_clock
from feynman_api.config import Settings
from feynman_api.db import get_session
from feynman_api.errors import (
    CARDS_PROCESSING,
    MAP_NOT_READY,
    MAP_PROCESSING,
    ErrorResponse,
    conflict,
    not_found,
    rate_limited,
)
from feynman_api.jobs.queue import enqueue
from feynman_api.models import Concept, Flashcard
from feynman_api.routes.knowledge_maps import map_out
from feynman_api.routes.schemas import (
    AcceptOut,
    CardIdsRequest,
    FlashcardCreate,
    FlashcardOut,
    FlashcardUpdate,
    GenerateCardsRequest,
    KnowledgeMapOut,
    RejectOut,
    card_rule_error,
)

router = APIRouter(tags=["flashcards"])

Db = Annotated[AsyncSession, Depends(get_session)]
Current = Annotated[CurrentUser, Depends(current_user)]
Now = Annotated[Clock, Depends(get_clock)]
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}
_GENERATE_ERRORS: dict[int | str, dict[str, Any]] = _ERRORS | {
    409: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


def _out(card: Flashcard) -> FlashcardOut:
    return FlashcardOut.model_validate(card, from_attributes=True)


@router.get("/study-sets/{set_id}/flashcards", response_model=list[FlashcardOut], responses=_ERRORS)
async def list_flashcards(
    set_id: uuid.UUID,
    db: Db,
    current: Current,
    card_status: Literal["accepted", "suggested"] = Query("accepted", alias="status"),
) -> list[FlashcardOut]:
    study_set = await get_owned_set(db, current.user.id, set_id)
    cards = (
        await db.execute(
            select(Flashcard)
            .where(Flashcard.study_set_id == study_set.id, Flashcard.status == card_status)
            .order_by(Flashcard.created_at, Flashcard.id)
        )
    ).scalars()
    return [_out(c) for c in cards]


@router.post(
    "/study-sets/{set_id}/flashcards",
    status_code=201,
    response_model=FlashcardOut,
    responses=_ERRORS,
)
async def create_flashcard(
    set_id: uuid.UUID, body: FlashcardCreate, db: Db, current: Current
) -> FlashcardOut:
    study_set = await get_owned_set(db, current.user.id, set_id)
    card = Flashcard(
        study_set_id=study_set.id,
        kind=body.kind,
        front=body.front,
        back=body.back,
        origin="manual",
        status="accepted",
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return _out(card)


@router.patch("/flashcards/{card_id}", response_model=FlashcardOut, responses=_ERRORS)
async def update_flashcard(
    card_id: uuid.UUID, body: FlashcardUpdate, db: Db, current: Current
) -> FlashcardOut:
    card = await get_owned_card(db, current.user.id, card_id)
    kind = body.kind if body.kind is not None else card.kind
    front = body.front if body.front is not None else card.front
    back = body.back if body.back is not None else card.back
    error = card_rule_error(kind, front, back)  # the merged row, against the (new) kind's rules
    if error is not None:
        field, message = error
        raise RequestValidationError(
            [{"type": "cloze", "loc": ("body", field), "msg": message, "input": None}]
        )
    changed = (kind, front, back) != (card.kind, card.front, card.back)
    if changed and card.origin == "generated":
        card.edited = True  # regeneration keeps it
    card.kind, card.front, card.back = kind, front, back
    if body.status is not None:
        card.status = body.status  # only "accepted"; accepted -> accepted is a no-op
    await db.commit()
    await db.refresh(card)
    return _out(card)


@router.delete("/flashcards/{card_id}", status_code=204, responses=_ERRORS)
async def delete_flashcard(card_id: uuid.UUID, db: Db, current: Current) -> Response:
    card = await get_owned_card(db, current.user.id, card_id)
    await db.delete(card)
    await db.commit()
    return Response(status_code=204)


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.post(
    "/study-sets/{set_id}/flashcards/generate",
    status_code=202,
    response_model=KnowledgeMapOut,
    responses=_GENERATE_ERRORS,
)
async def generate_flashcards(
    set_id: uuid.UUID,
    body: GenerateCardsRequest,
    request: Request,
    db: Db,
    current: Current,
    now: Now,
) -> KnowledgeMapOut:
    # Check order (design 7.3): owned lookups (404), the map row locked FOR UPDATE, state
    # (409), the concept (404), the non-committing rate-limit count (429), writes, ONE commit.
    # So a refused request never uses up a card run.
    study_set = await get_owned_set(db, current.user.id, set_id)
    km = await get_owned_map(db, current.user.id, study_set.id, for_update=True)
    if km.status == "processing":
        raise conflict(MAP_PROCESSING)
    if km.status != "ready":
        raise conflict(MAP_NOT_READY)
    if km.cards_status == "processing":
        raise conflict(CARDS_PROCESSING)
    if body.concept_id is not None:
        found = (
            await db.execute(
                select(Concept.id).where(
                    Concept.id == body.concept_id, Concept.knowledge_map_id == km.id
                )
            )
        ).scalar_one_or_none()
        if found is None:
            raise not_found()

    settings = _settings(request)
    limit = await hit(
        db,
        card_generation_key(current.user.id),
        settings.card_generation_limit,
        timedelta(seconds=settings.llm_limit_window_seconds),
        now(),
        commit=False,
    )
    if not limit.allowed:
        raise rate_limited(limit.retry_after)  # nothing committed: the session rolls back

    km.cards_status = "processing"
    km.cards_error_message = None
    await enqueue(
        db,
        kind="generate_flashcards",
        payload={
            "knowledge_map_id": str(km.id),
            "concept_id": None if body.concept_id is None else str(body.concept_id),
        },
        user_id=current.user.id,
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise conflict(CARDS_PROCESSING) from None
    return await map_out(db, km)


async def _suggested_ids(
    db: AsyncSession, current: CurrentUser, set_id: uuid.UUID, body: CardIdsRequest
) -> list[uuid.UUID]:
    """The suggested cards the request names, locked. All or nothing: any id that is not a
    suggested card of this (owned) set is a 404, and nothing changes."""
    study_set = await get_owned_set(db, current.user.id, set_id)
    stmt = (
        select(Flashcard.id)
        .where(Flashcard.study_set_id == study_set.id, Flashcard.status == "suggested")
        .order_by(Flashcard.id)
        .with_for_update()
    )
    if body.card_ids is None:
        return list((await db.execute(stmt)).scalars())
    wanted = set(body.card_ids)
    if not wanted:
        return []
    found = list((await db.execute(stmt.where(Flashcard.id.in_(wanted)))).scalars())
    if len(found) != len(wanted):
        raise not_found()
    return found


@router.post(
    "/study-sets/{set_id}/suggested-cards/accept", response_model=AcceptOut, responses=_ERRORS
)
async def accept_suggested_cards(
    set_id: uuid.UUID, body: CardIdsRequest, db: Db, current: Current
) -> AcceptOut:
    ids = await _suggested_ids(db, current, set_id, body)
    if ids:
        await db.execute(
            update(Flashcard)
            .where(Flashcard.id.in_(ids), Flashcard.status == "suggested")
            .values(status="accepted", updated_at=func.now())
        )
    await db.commit()
    return AcceptOut(accepted=len(ids))


@router.post(
    "/study-sets/{set_id}/suggested-cards/reject", response_model=RejectOut, responses=_ERRORS
)
async def reject_suggested_cards(
    set_id: uuid.UUID, body: CardIdsRequest, db: Db, current: Current
) -> RejectOut:
    ids = await _suggested_ids(db, current, set_id, body)
    if ids:
        await db.execute(
            delete(Flashcard).where(Flashcard.id.in_(ids), Flashcard.status == "suggested")
        )
    await db.commit()
    return RejectOut(rejected=len(ids))
