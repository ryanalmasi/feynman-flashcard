"""Generate suggested flashcards from a set's Knowledge Map (design 7.7)."""

import asyncio
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.jobs.handlers._llm import (
    as_job_error,
    keep_lease,
    require_llm,
    sum_usage,
    usage_dict,
)
from feynman_api.jobs.registry import PermanentJobError, WorkerContext
from feynman_api.knowledge.cards import CardDraft, cap_cards, validate_cards
from feynman_api.knowledge.chunking import render_pages
from feynman_api.knowledge.limits import (
    CARD_BATCH_SIZE,
    CARDS_BY_IMPORTANCE,
    CARDS_PER_SET_MAX,
    PAGE_TEXT_PER_CONCEPT,
)
from feynman_api.knowledge.prompts import (
    CARDS_MAX_TOKENS,
    CARDS_SYSTEM_PROMPT,
    CardPromptItem,
    cards_user_message,
)
from feynman_api.knowledge.schemas import CardBatch
from feynman_api.llm import ChatMessage, LLMError, LLMProvider, PromptBlock, StructuredResult
from feynman_api.models.document import DocumentPage
from feynman_api.models.flashcard import Flashcard
from feynman_api.models.job import Job
from feynman_api.models.knowledge_map import Concept, KnowledgeMap

MSG_CARDS_FAILED = "We couldn't generate flashcards. Try again."
MSG_CARDS_GENERIC = "Something went wrong while generating flashcards. Try again."

Batch = list[tuple[CardPromptItem, uuid.UUID]]


def _map_id(job: Job) -> uuid.UUID:
    return uuid.UUID(job.payload["knowledge_map_id"])


def _concept_id(job: Job) -> uuid.UUID | None:
    raw = job.payload.get("concept_id")
    return None if raw is None else uuid.UUID(raw)


def _source_text(pages: dict[int, str], source_pages: Sequence[int]) -> str:
    """The concept's source pages, in page order, cut to PAGE_TEXT_PER_CONCEPT raw characters
    in total. The cut is made before escaping and tagging, so it never splits a tag."""
    budget = PAGE_TEXT_PER_CONCEPT
    kept: list[tuple[int, str]] = []
    for number in sorted(set(source_pages)):
        if budget <= 0:
            break
        text = pages.get(number)
        if text is None:
            continue
        kept.append((number, text[:budget]))
        budget -= len(kept[-1][1])
    return render_pages(kept)


async def _generate(llm: LLMProvider, model: str, batch: Batch) -> StructuredResult[CardBatch]:
    """One provider call. Does no database work (it runs as a parallel task)."""
    return await llm.generate_structured(
        model=model,
        system=[PromptBlock(text=CARDS_SYSTEM_PROMPT)],
        messages=[ChatMessage(role="user", content=cards_user_message([i for i, _ in batch]))],
        schema=CardBatch,
        max_tokens=CARDS_MAX_TOKENS,
    )


class GenerateFlashcardsHandler:
    generic_failure = MSG_CARDS_GENERIC

    async def run(self, db: AsyncSession, job: Job, ctx: WorkerContext) -> dict[str, Any] | None:
        settings = ctx.settings
        map_id = _map_id(job)
        only = _concept_id(job)

        # 1. Read the map, the concepts in scope and their page text; then end the read
        #    transaction (keep_lease commits) before any provider call.
        kmap = (
            await db.execute(select(KnowledgeMap).where(KnowledgeMap.id == map_id))
        ).scalar_one_or_none()
        if kmap is None:
            return {"skipped": "map_deleted"}
        set_id = kmap.study_set_id
        stmt = select(Concept).where(Concept.knowledge_map_id == map_id)
        if only is not None:
            stmt = stmt.where(Concept.id == only)
        concepts = list((await db.execute(stmt.order_by(Concept.position))).scalars())
        skipped = None
        if kmap.status != "ready":
            skipped = "map_not_ready"
        elif only is not None and not concepts:
            skipped = "concept_deleted"
        elif not concepts:
            skipped = "no_concepts"
        if skipped is not None:
            kmap.cards_status = "idle"
            kmap.cards_error_message = None
            await db.flush()
            return {"skipped": skipped}
        llm = require_llm(ctx)
        wanted = {n for c in concepts for n in c.source_pages}
        pages: dict[int, str] = {
            number: text
            for number, text in (
                await db.execute(
                    select(DocumentPage.page_number, DocumentPage.text).where(
                        DocumentPage.document_id == kmap.document_id,
                        DocumentPage.page_number.in_(wanted),
                    )
                )
            ).all()
        }

        # 2. Local ids k1... in position order, in batches.
        items: Batch = [
            (
                CardPromptItem(
                    local_id=f"k{n}",
                    title=c.title,
                    explanation=c.explanation,
                    importance=c.importance,
                    key_terms=list(c.key_terms),
                    misconceptions=list(c.misconceptions),
                    page_text=_source_text(pages, c.source_pages),
                    required=CARDS_BY_IMPORTANCE[c.importance],
                ),
                c.id,
            )
            for n, c in enumerate(concepts, start=1)
        ]
        batches = [items[i : i + CARD_BATCH_SIZE] for i in range(0, len(items), CARD_BATCH_SIZE)]
        await keep_lease(db, job, ctx)

        # 3. Provider calls, a bounded group at a time, results kept in memory only. Every
        #    call in a group finishes before the first error is raised.
        model = settings.llm_model_flashcards
        step = max(settings.knowledge_map_parallel_chunks, 1)
        results: list[tuple[Batch, StructuredResult[CardBatch]]] = []
        for start in range(0, len(batches), step):
            group = batches[start : start + step]
            await keep_lease(db, job, ctx)
            outcomes = await asyncio.gather(
                *(_generate(llm, model, b) for b in group), return_exceptions=True
            )
            first_error: BaseException | None = None
            for b, outcome in zip(group, outcomes, strict=True):
                if isinstance(outcome, BaseException):
                    if first_error is None:
                        first_error = outcome
                    continue
                results.append((b, outcome))
            if first_error is not None:
                if isinstance(first_error, LLMError):
                    raise as_job_error(first_error, MSG_CARDS_FAILED)
                raise first_error

        # 4. Validate (pure). Batches are in position order, so the drafts are too.
        drafts: list[CardDraft] = []
        dropped = 0
        calls: list[dict[str, Any]] = []
        for index, (b, outcome) in enumerate(results):
            scope = {item.local_id: (cid, item.required) for item, cid in b}
            kept, lost = validate_cards(outcome.value, scope)
            drafts.extend(kept)
            dropped += lost
            calls.append({"step": "batch", "index": index, **usage_dict(outcome.usage)})
        if not drafts:
            raise PermanentJobError(MSG_CARDS_FAILED)

        # 5. Final writes: no keep_lease from here on. They commit with mark_succeeded, so a
        #    run that lost its lease rolls them back. Lock order: the map row, then cards.
        kmap = (
            await db.execute(
                select(KnowledgeMap)
                .where(KnowledgeMap.id == map_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if kmap is None:
            return {"skipped": "map_deleted"}
        live_stmt = select(Concept.id).where(Concept.knowledge_map_id == map_id)
        if only is not None:
            live_stmt = live_stmt.where(Concept.id == only)
        live = set((await db.execute(live_stmt)).scalars())
        drafts = [d for d in drafts if d.concept_id in live]

        stale = delete(Flashcard).where(
            Flashcard.study_set_id == set_id,
            Flashcard.origin == "generated",
            Flashcard.edited.is_(False),
        )
        if only is not None:
            stale = stale.where(Flashcard.concept_id == only)
        # A whole-set run: every unedited generated card of the set, linked or unlinked.
        await db.execute(stale.execution_options(synchronize_session=False))

        remaining = (
            await db.execute(
                select(func.count())
                .select_from(Flashcard)
                .where(Flashcard.study_set_id == set_id, Flashcard.origin == "generated")
            )
        ).scalar_one()
        new = cap_cards(drafts, CARDS_PER_SET_MAX - remaining)
        db.add_all(
            Flashcard(
                study_set_id=set_id,
                concept_id=d.concept_id,
                kind=d.kind,
                front=d.front,
                back=d.back,
                origin="generated",
                status="suggested",
                edited=False,
            )
            for d in new
        )
        kmap.cards_status = "idle"
        kmap.cards_error_message = None
        await db.flush()
        return {
            "cards": len(new),
            "dropped_invalid": dropped,
            "usage": {"calls": calls, "total": sum_usage(calls)},
        }

    async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None:
        """Mark the card run failed. Existing cards are untouched."""
        kmap = (
            await db.execute(
                select(KnowledgeMap).where(KnowledgeMap.id == _map_id(job)).with_for_update()
            )
        ).scalar_one_or_none()
        if kmap is not None:
            kmap.cards_status = "failed"
            kmap.cards_error_message = user_message

    async def failure_fallback(self, db: AsyncSession, job: Job, user_message: str) -> None:
        """Minimal fallback when on_failed raised: one guarded UPDATE, nothing else."""
        await db.execute(
            update(KnowledgeMap)
            .where(KnowledgeMap.id == _map_id(job), KnowledgeMap.cards_status == "processing")
            .values(cards_status="failed", cards_error_message=user_message)
            .execution_options(synchronize_session=False)
        )
