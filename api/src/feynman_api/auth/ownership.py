import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.errors import not_found
from feynman_api.models import Concept, Document, Flashcard, KnowledgeMap, StudySet

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


async def get_owned_map(
    db: AsyncSession, user_id: uuid.UUID, set_id: uuid.UUID, *, for_update: bool = False
) -> KnowledgeMap:
    stmt = (
        select(KnowledgeMap)
        .join(StudySet, KnowledgeMap.study_set_id == StudySet.id)
        .where(KnowledgeMap.study_set_id == set_id, StudySet.user_id == user_id)
    )
    if for_update:
        stmt = stmt.with_for_update(of=KnowledgeMap).execution_options(populate_existing=True)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise not_found()
    return row


async def get_owned_concept(
    db: AsyncSession, user_id: uuid.UUID, concept_id: uuid.UUID, *, lock_map: bool = False
) -> tuple[Concept, KnowledgeMap]:
    """The concept and its map. With lock_map the MAP row is locked first (lock order: map,
    then concepts, as in the build job's final write) and the concept is re-read under it."""
    if not lock_map:
        found = (
            await db.execute(
                select(Concept, KnowledgeMap)
                .join(KnowledgeMap, Concept.knowledge_map_id == KnowledgeMap.id)
                .join(StudySet, KnowledgeMap.study_set_id == StudySet.id)
                .where(Concept.id == concept_id, StudySet.user_id == user_id)
            )
        ).one_or_none()
        if found is None:
            raise not_found()
        return found[0], found[1]

    map_id = (
        await db.execute(
            select(Concept.knowledge_map_id)
            .join(KnowledgeMap, Concept.knowledge_map_id == KnowledgeMap.id)
            .join(StudySet, KnowledgeMap.study_set_id == StudySet.id)
            .where(Concept.id == concept_id, StudySet.user_id == user_id)
        )
    ).scalar_one_or_none()
    if map_id is None:
        raise not_found()
    kmap = (
        await db.execute(
            select(KnowledgeMap)
            .join(StudySet, KnowledgeMap.study_set_id == StudySet.id)
            .where(KnowledgeMap.id == map_id, StudySet.user_id == user_id)
            .with_for_update(of=KnowledgeMap)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if kmap is None:
        raise not_found()
    # The concept may have been replaced by a build that finished before the lock was granted.
    concept = (
        await db.execute(
            select(Concept)
            .where(Concept.id == concept_id, Concept.knowledge_map_id == kmap.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if concept is None:
        raise not_found()
    return concept, kmap
