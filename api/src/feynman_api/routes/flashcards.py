import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.auth.dependencies import CurrentUser, current_user
from feynman_api.auth.ownership import get_owned_card, get_owned_set
from feynman_api.db import get_session
from feynman_api.errors import ErrorResponse
from feynman_api.models import Flashcard
from feynman_api.routes.schemas import FlashcardCreate, FlashcardOut, FlashcardUpdate

router = APIRouter(tags=["flashcards"])

Db = Annotated[AsyncSession, Depends(get_session)]
Current = Annotated[CurrentUser, Depends(current_user)]
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


def _out(card: Flashcard) -> FlashcardOut:
    return FlashcardOut.model_validate(card, from_attributes=True)


@router.get("/study-sets/{set_id}/flashcards", response_model=list[FlashcardOut], responses=_ERRORS)
async def list_flashcards(set_id: uuid.UUID, db: Db, current: Current) -> list[FlashcardOut]:
    study_set = await get_owned_set(db, current.user.id, set_id)
    cards = (
        await db.execute(
            select(Flashcard)
            .where(Flashcard.study_set_id == study_set.id)
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
    card = Flashcard(study_set_id=study_set.id, front=body.front, back=body.back, origin="manual")
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return _out(card)


@router.patch("/flashcards/{card_id}", response_model=FlashcardOut, responses=_ERRORS)
async def update_flashcard(
    card_id: uuid.UUID, body: FlashcardUpdate, db: Db, current: Current
) -> FlashcardOut:
    card = await get_owned_card(db, current.user.id, card_id)
    if body.front is not None:
        card.front = body.front
    if body.back is not None:
        card.back = body.back
    await db.commit()
    await db.refresh(card)
    return _out(card)


@router.delete("/flashcards/{card_id}", status_code=204, responses=_ERRORS)
async def delete_flashcard(card_id: uuid.UUID, db: Db, current: Current) -> Response:
    card = await get_owned_card(db, current.user.id, card_id)
    await db.delete(card)
    await db.commit()
    return Response(status_code=204)
