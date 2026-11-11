"""Build a set's Knowledge Map from its document pages (design 7.6)."""

import asyncio
import uuid
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from feynman_api.jobs.handlers._llm import (
    as_job_error,
    keep_lease,
    require_llm,
    sum_usage,
    usage_dict,
)
from feynman_api.jobs.registry import PermanentJobError, WorkerContext
from feynman_api.knowledge.chunking import Chunk, chunk_pages
from feynman_api.knowledge.clean import clean_extraction
from feynman_api.knowledge.merge import merge_concepts, merge_listing
from feynman_api.knowledge.prompts import (
    MAP_MAX_TOKENS,
    MAP_SYSTEM_PROMPT,
    MERGE_MAX_TOKENS,
    MERGE_SYSTEM_PROMPT,
    chunk_user_message,
    merge_user_message,
)
from feynman_api.knowledge.schemas import ChunkExtraction, ConceptDraft, MergeGroups
from feynman_api.llm import (
    ChatMessage,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
    PromptBlock,
    StructuredResult,
)
from feynman_api.models.document import DocumentPage
from feynman_api.models.job import Job
from feynman_api.models.knowledge_map import Concept, KnowledgeMap, KnowledgeMapChunk

MSG_MAP_FAILED = "We couldn't build a Knowledge Map from this PDF. Try Rebuild."
MSG_MAP_GENERIC = "Something went wrong while building the Knowledge Map. Try Rebuild."


async def _extract(llm: LLMProvider, model: str, chunk: Chunk) -> StructuredResult[ChunkExtraction]:
    """One provider call. Does no database work (it runs as a parallel task)."""
    return await llm.generate_structured(
        model=model,
        system=[PromptBlock(text=MAP_SYSTEM_PROMPT)],
        messages=[ChatMessage(role="user", content=chunk_user_message(chunk))],
        schema=ChunkExtraction,
        max_tokens=MAP_MAX_TOKENS,
    )


def _map_id(job: Job) -> uuid.UUID:
    return uuid.UUID(job.payload["knowledge_map_id"])


class BuildKnowledgeMapHandler:
    generic_failure = MSG_MAP_GENERIC

    async def run(self, db: AsyncSession, job: Job, ctx: WorkerContext) -> dict[str, Any] | None:
        settings = ctx.settings
        map_id = _map_id(job)

        # 1. Read what we need, then end the read transaction (keep_lease commits).
        kmap = (
            await db.execute(select(KnowledgeMap).where(KnowledgeMap.id == map_id))
        ).scalar_one_or_none()
        if kmap is None:
            return {"skipped": "map_deleted"}
        if kmap.status != "processing":
            return {"skipped": "map_not_processing"}
        llm = require_llm(ctx)
        pages = [
            (number, text)
            for number, text in (
                await db.execute(
                    select(DocumentPage.page_number, DocumentPage.text)
                    .where(DocumentPage.document_id == kmap.document_id)
                    .order_by(DocumentPage.page_number)
                )
            ).all()
        ]
        await keep_lease(db, job, ctx)

        # 2. Chunk, and create the missing chunk rows idempotently (a re-run after a
        #    partial attempt keeps the rows, and the results, it already has).
        chunks = chunk_pages(pages, settings.knowledge_map_chunk_chars)
        if chunks:
            await db.execute(
                pg_insert(KnowledgeMapChunk)
                .values(
                    [
                        {
                            "knowledge_map_id": map_id,
                            "chunk_index": c.index,
                            "page_start": c.page_start,
                            "page_end": c.page_end,
                            "status": "pending",
                        }
                        for c in chunks
                    ]
                )
                .on_conflict_do_nothing(index_elements=["knowledge_map_id", "chunk_index"])
            )
        await db.commit()
        rows = {
            row.chunk_index: row
            for row in (
                await db.execute(
                    select(KnowledgeMapChunk)
                    .where(KnowledgeMapChunk.knowledge_map_id == map_id)
                    .execution_options(populate_existing=True)
                )
            ).scalars()
        }

        # 3. Extract the pending chunks, a bounded batch at a time. Done chunks are never
        #    re-sent. The provider calls run as tasks that do no DB work; results are
        #    stored one at a time on this session.
        pending = [c for c in chunks if rows[c.index].status == "pending"]
        model = settings.llm_model_knowledge_map
        step = max(settings.knowledge_map_parallel_chunks, 1)
        for start in range(0, len(pending), step):
            batch = pending[start : start + step]
            await keep_lease(db, job, ctx)
            results = await asyncio.gather(
                *(_extract(llm, model, c) for c in batch), return_exceptions=True
            )
            first_error: BaseException | None = None
            for chunk, outcome in zip(batch, results, strict=True):
                if isinstance(outcome, BaseException):
                    if first_error is None:
                        first_error = outcome
                    continue
                drafts = clean_extraction(outcome.value, chunk.page_start, chunk.page_end)
                row = rows[chunk.index]
                row.result = {"concepts": [d.model_dump() for d in drafts]}
                row.usage = usage_dict(outcome.usage)
                row.status = "done"
                # Commits this chunk; on a lost lease rolls it back and raises LeaseLost.
                await keep_lease(db, job, ctx)
            if first_error is not None:
                # Siblings are stored above, so a retry never pays for them again.
                if isinstance(first_error, LLMError):
                    raise as_job_error(first_error, MSG_MAP_FAILED)
                raise first_error

        # 4. Every chunk's cleaned concepts (from this attempt or earlier ones).
        per_chunk: list[list[ConceptDraft]] = []
        calls: list[dict[str, Any]] = []
        for c in chunks:
            row = rows[c.index]
            stored = (row.result or {}).get("concepts", [])
            per_chunk.append([ConceptDraft.model_validate(d) for d in stored])
            calls.append({"step": "chunk", "index": c.index, **(row.usage or {})})
        if not any(per_chunk):
            raise PermanentJobError(MSG_MAP_FAILED)

        # 5. Merge duplicates across chunks; a permanent merge failure keeps them all.
        groups: MergeGroups | None = None
        if len(chunks) >= 2:
            await keep_lease(db, job, ctx)
            try:
                merged = await llm.generate_structured(
                    model=model,
                    system=[PromptBlock(text=MERGE_SYSTEM_PROMPT)],
                    messages=[
                        ChatMessage(
                            role="user", content=merge_user_message(merge_listing(per_chunk))
                        )
                    ],
                    schema=MergeGroups,
                    max_tokens=MERGE_MAX_TOKENS,
                )
            except (LLMRateLimitError, LLMUnavailableError):
                raise  # transient: the queue retries (done chunks are kept)
            except LLMError:
                groups = None  # permanent: fall back to no merge
            else:
                groups = merged.value
                calls.append({"step": "merge", **usage_dict(merged.usage)})
        concepts = merge_concepts(per_chunk, groups)

        # 6. Final writes: no keep_lease from here on. They commit with mark_succeeded,
        #    so a run that lost its lease rolls them back.
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
        await db.execute(
            delete(Concept)
            .where(Concept.knowledge_map_id == map_id)
            .execution_options(synchronize_session=False)
        )
        db.add_all(
            Concept(
                knowledge_map_id=map_id,
                position=position,
                title=d.title,
                explanation=d.explanation,
                importance=d.importance,
                key_terms=d.key_terms,
                misconceptions=d.misconceptions,
                source_pages=d.source_pages,
            )
            for position, d in enumerate(concepts)
        )
        kmap.status = "ready"
        kmap.model_id = model
        kmap.revision += 1
        kmap.error_message = None
        await db.flush()
        return {
            "chunks": len(chunks),
            "concepts": len(concepts),
            "usage": {"calls": calls, "total": sum_usage(calls)},
        }

    async def on_failed(self, db: AsyncSession, job: Job, user_message: str) -> None:
        """Mark the map failed. Its concepts are untouched (a rebuild keeps the old ones)."""
        kmap = (
            await db.execute(
                select(KnowledgeMap).where(KnowledgeMap.id == _map_id(job)).with_for_update()
            )
        ).scalar_one_or_none()
        if kmap is not None:
            kmap.status = "failed"
            kmap.error_message = user_message

    async def failure_fallback(self, db: AsyncSession, job: Job, user_message: str) -> None:
        """Minimal fallback when on_failed raised: one guarded UPDATE, nothing else."""
        await db.execute(
            update(KnowledgeMap)
            .where(KnowledgeMap.id == _map_id(job), KnowledgeMap.status == "processing")
            .values(status="failed", error_message=user_message)
            .execution_options(synchronize_session=False)
        )
