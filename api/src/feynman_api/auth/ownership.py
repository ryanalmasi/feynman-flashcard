import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.errors import not_found
from feynman_api.models import Document, Flashcard, StudySet

# The ONLY way routes load owned rows. The WHERE clause carries user_id, so another
# user's id is indistinguishable from a nonexistent one (same 404). Never load by id
# and then compare owners.


async def get_owned_set(db: AsyncSession, user_id: uuid.UUID, set_id: uuid.UUID) -> StudySet:
    row = (
        await db.execute(select(StudySet).where(StudySet.id == set_id, StudySet.user_id == user_id))
    ).scalar_one_or_none()
    if row is None:
        raise not_found()
    return row


async def get_owned_card(db: AsyncSession, user_id: uuid.UUID, card_id: uuid.UUID) -> Flashcard:
    row = (
        await db.execute(
            select(Flashcard)
            .join(StudySet, Flashcard.study_set_id == StudySet.id)
            .where(Flashcard.id == card_id, StudySet.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise not_found()
    return row


async def get_owned_document(
    db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID
) -> Document:
    row = (
        await db.execute(
            select(Document)
            .join(StudySet, Document.study_set_id == StudySet.id)
            .where(Document.id == document_id, StudySet.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise not_found()
    return row
