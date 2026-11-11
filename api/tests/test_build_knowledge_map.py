import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from conftest import FrozenClock
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from feynman_api.config import Settings
from feynman_api.db import create_sessionmaker
from feynman_api.jobs.handlers.build_knowledge_map import (
    MSG_MAP_FAILED,
    MSG_MAP_GENERIC,
    BuildKnowledgeMapHandler,
)
from feynman_api.jobs.queue import enqueue
from feynman_api.jobs.registry import MSG_LLM_DISABLED, JobHandler, WorkerContext
from feynman_api.jobs.worker import run_once
from feynman_api.knowledge.schemas import ChunkExtraction, MergeGroups
from feynman_api.llm import (
    FakeLLMProvider,
    LLMOutputValidationError,
    LLMRefusalError,
    LLMUnavailableError,
)
from feynman_api.llm.fake import FakeCall
from feynman_api.models import (
    Concept,
    Document,
    DocumentPage,
    Job,
    KnowledgeMap,
    KnowledgeMapChunk,
    StudySet,
    User,
)
from feynman_api.storage import FileStore

KIND = "build_knowledge_map"
HANDLERS: dict[str, JobHandler] = {KIND: BuildKnowledgeMapHandler()}
PAGE_CHARS = 50
SMALL_CHUNKS = 60  # one page per chunk

Responder = Callable[[FakeCall], dict[str, Any] | Awaitable[dict[str, Any]]]


@pytest.fixture
async def sm(
    clean_db: None, test_settings: Settings
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine: AsyncEngine = create_async_engine(test_settings.database_url.get_secret_value())
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


def _ctx(
    test_settings: Settings,
    file_store: FileStore,
    responder: Responder | None,
    *,
    llm: bool = True,
    **update: Any,
) -> tuple[WorkerContext, FakeLLMProvider]:
    fake = FakeLLMProvider(responder=responder)
    ctx = WorkerContext(
        settings=test_settings.model_copy(update=update),
        file_store=file_store,
        llm=fake if llm else None,
        clock=FrozenClock(),
    )
    return ctx, fake


def _concept(title: str, page: int, importance: str = "core") -> dict[str, Any]:
    return {
        "title": title,
        "explanation": f"{title} explained.",
        "importance": importance,
        "key_terms": [{"term": title, "synonyms": []}],
        "misconceptions": [],
        "source_pages": [page],
    }


def _is_merge(call: FakeCall) -> bool:
    return call.schema is MergeGroups


def _chunk_index(call: FakeCall) -> int:
    """Chunks are numbered from 0; chunk i holds page i + 1 (one page per chunk)."""
    assert call.schema is ChunkExtraction
    match = re.search(r'number="(\d+)"', call.messages[0].content)
    assert match is not None
    return int(match.group(1)) - 1


def _chunk_calls(fake: FakeLLMProvider) -> list[int]:
    return [_chunk_index(c) for c in fake.calls if not _is_merge(c)]


def _merge_calls(fake: FakeLLMProvider) -> int:
    return sum(1 for c in fake.calls if _is_merge(c))


def _one_concept_per_chunk(call: FakeCall) -> dict[str, Any]:
    if _is_merge(call):
        return {"groups": []}
    i = _chunk_index(call)
    return {"concepts": [_concept(f"Concept {i}", i + 1)]}


async def _setup(
    sm: async_sessionmaker[AsyncSession], pages: int, *, old_concepts: int = 0
) -> tuple[UUID, UUID]:
    """User, set, ready document with `pages` pages, a processing map, and the job."""
    async with sm() as s:
        user = User(email="km@example.com")
        s.add(user)
        await s.flush()
        ss = StudySet(user_id=user.id, title="T")
        s.add(ss)
        await s.flush()
        doc = Document(
            study_set_id=ss.id,
            storage_key=f"key-{ss.id}",
            original_filename="a.pdf",
            size_bytes=1,
            status="ready",
            page_count=pages,
        )
        s.add(doc)
        await s.flush()
        s.add_all(
            DocumentPage(
                document_id=doc.id,
                page_number=n,
                text=f"Page {n} text.".ljust(PAGE_CHARS, "x"),
            )
            for n in range(1, pages + 1)
        )
        kmap = KnowledgeMap(study_set_id=ss.id, document_id=doc.id, status="processing")
        s.add(kmap)
        await s.flush()
        s.add_all(
            Concept(
                knowledge_map_id=kmap.id,
                position=i,
                title=f"Old {i}",
                explanation="Old explanation.",
                importance="core",
            )
            for i in range(old_concepts)
        )
        job = await enqueue(
            s, kind=KIND, payload={"knowledge_map_id": str(kmap.id)}, user_id=user.id
        )
        await s.commit()
        return kmap.id, job.id


async def _map(sm: async_sessionmaker[AsyncSession], mid: UUID) -> KnowledgeMap:
    async with sm() as s:
        return (await s.execute(select(KnowledgeMap).where(KnowledgeMap.id == mid))).scalar_one()


async def _concepts(sm: async_sessionmaker[AsyncSession], mid: UUID) -> list[Concept]:
    async with sm() as s:
        res = await s.execute(
            select(Concept).where(Concept.knowledge_map_id == mid).order_by(Concept.position)
        )
        return list(res.scalars())


async def _chunks(sm: async_sessionmaker[AsyncSession], mid: UUID) -> list[KnowledgeMapChunk]:
    async with sm() as s:
        res = await s.execute(
            select(KnowledgeMapChunk)
            .where(KnowledgeMapChunk.knowledge_map_id == mid)
            .order_by(KnowledgeMapChunk.chunk_index)
        )
        return list(res.scalars())


async def _job(sm: async_sessionmaker[AsyncSession], jid: UUID) -> Job:
    async with sm() as s:
        return (await s.execute(select(Job).where(Job.id == jid))).scalar_one()


async def _make_due(sm: async_sessionmaker[AsyncSession], jid: UUID) -> None:
    async with sm() as s:
        await s.execute(
            update(Job)
            .where(Job.id == jid)
            .values(run_after=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()


async def _bump_attempts(sm: async_sessionmaker[AsyncSession], jid: UUID) -> None:
    """Simulate another worker reclaiming the job."""
    async with sm() as s:
        await s.execute(update(Job).where(Job.id == jid).values(attempts=Job.attempts + 1))
        await s.commit()


async def test_single_chunk_no_merge_call(sm, test_settings, file_store) -> None:  # type: ignore[no-untyped-def]
    def responder(call: FakeCall) -> dict[str, Any]:
        return {"concepts": [_concept("Alpha", 1), _concept("Beta", 2), _concept("Gamma", 3)]}

    ctx, fake = _ctx(test_settings, file_store, responder)
    mid, jid = await _setup(sm, 3)
    assert await run_once(sm, ctx, HANDLERS) is True

    assert len(fake.calls) == 1
    assert fake.calls[0].schema is ChunkExtraction
    assert fake.calls[0].model == ctx.settings.llm_model_knowledge_map
    kmap = await _map(sm, mid)
    assert kmap.status == "ready"
    assert kmap.revision == 1
    assert kmap.error_message is None
    assert kmap.model_id == ctx.settings.llm_model_knowledge_map
    concepts = await _concepts(sm, mid)
    assert [c.position for c in concepts] == [0, 1, 2]
    assert [c.title for c in concepts] == ["Alpha", "Beta", "Gamma"]
    assert concepts[1].source_pages == [2]
    job = await _job(sm, jid)
    assert job.status == "succeeded"
    assert job.result is not None
    assert job.result["chunks"] == 1
    assert job.result["concepts"] == 3


async def test_multi_chunk_extract_then_merge(sm, test_settings, file_store) -> None:  # type: ignore[no-untyped-def]
    def responder(call: FakeCall) -> dict[str, Any]:
        if _is_merge(call):
            assert "c0-0" in call.messages[0].content
            return {"groups": [{"keep": "c0-0", "merge": ["c2-0"]}]}
        i = _chunk_index(call)
        return {"concepts": [_concept(f"Concept {i}", i + 1)]}

    ctx, fake = _ctx(test_settings, file_store, responder, knowledge_map_chunk_chars=SMALL_CHUNKS)
    mid, jid = await _setup(sm, 3)
    assert await run_once(sm, ctx, HANDLERS) is True

    assert sorted(_chunk_calls(fake)) == [0, 1, 2]
    assert _merge_calls(fake) == 1
    assert _is_merge(fake.calls[-1])
    concepts = await _concepts(sm, mid)
    assert [c.title for c in concepts] == ["Concept 0", "Concept 1"]
    assert concepts[0].source_pages == [1, 3]
    assert (await _map(sm, mid)).status == "ready"
    assert all(c.status == "done" for c in await _chunks(sm, mid))
    assert (await _job(sm, jid)).status == "succeeded"


async def test_resume_skips_done_chunks(sm, test_settings, file_store) -> None:  # type: ignore[no-untyped-def]
    failed: list[int] = []

    def responder(call: FakeCall) -> dict[str, Any]:
        if not _is_merge(call) and _chunk_index(call) == 1 and not failed:
            failed.append(1)
            raise LLMUnavailableError("down")
        return _one_concept_per_chunk(call)

    ctx, fake = _ctx(
        test_settings,
        file_store,
        responder,
        knowledge_map_chunk_chars=SMALL_CHUNKS,
        knowledge_map_parallel_chunks=1,
    )
    mid, jid = await _setup(sm, 2)
    assert await run_once(sm, ctx, HANDLERS) is True
    job = await _job(sm, jid)
    assert job.status == "queued"
    assert job.last_error == "LLMUnavailableError"
    assert [c.status for c in await _chunks(sm, mid)] == ["done", "pending"]
    assert (await _map(sm, mid)).status == "processing"

    await _make_due(sm, jid)
    assert await run_once(sm, ctx, HANDLERS) is True
    assert (await _job(sm, jid)).status == "succeeded"
    assert _chunk_calls(fake).count(0) == 1
    assert _chunk_calls(fake) == [0, 1, 1]
    assert [c.title for c in await _concepts(sm, mid)] == ["Concept 0", "Concept 1"]


async def test_parallel_siblings_stored_on_transient_failure(  # type: ignore[no-untyped-def]
    sm, test_settings, file_store
) -> None:
    failed: list[int] = []

    def responder(call: FakeCall) -> dict[str, Any]:
        if not _is_merge(call) and _chunk_index(call) == 1 and not failed:
            failed.append(1)
            raise LLMUnavailableError("down")
        return _one_concept_per_chunk(call)

    ctx, fake = _ctx(
        test_settings,
        file_store,
        responder,
        knowledge_map_chunk_chars=SMALL_CHUNKS,
        knowledge_map_parallel_chunks=4,
    )
    mid, jid = await _setup(sm, 3)
    assert await run_once(sm, ctx, HANDLERS) is True
    assert (await _job(sm, jid)).status == "queued"
    assert sorted(_chunk_calls(fake)) == [0, 1, 2]
    assert [c.status for c in await _chunks(sm, mid)] == ["done", "pending", "done"]

    first_attempt_calls = len(fake.calls)
    await _make_due(sm, jid)
    assert await run_once(sm, ctx, HANDLERS) is True
    retry_calls = fake.calls[first_attempt_calls:]
    assert [_chunk_index(c) for c in retry_calls if not _is_merge(c)] == [1]
    assert sum(1 for c in retry_calls if _is_merge(c)) == 1
    assert (await _job(sm, jid)).status == "succeeded"
    assert len(await _concepts(sm, mid)) == 3


async def test_stale_lease_writes_no_concepts(  # type: ignore[no-untyped-def]
    sm, test_settings, file_store, monkeypatch, caplog
) -> None:
    failed_calls: list[str] = []

    async def recording_on_failed(self, db, job, user_message) -> None:  # type: ignore[no-untyped-def]
        failed_calls.append(user_message)

    monkeypatch.setattr(BuildKnowledgeMapHandler, "on_failed", recording_on_failed)
    jid_box: list[UUID] = []

    async def responder(call: FakeCall) -> dict[str, Any]:
        if len([c for c in fake.calls if not _is_merge(c)]) == 1:
            await _bump_attempts(sm, jid_box[0])
        return _one_concept_per_chunk(call)

    ctx, fake = _ctx(test_settings, file_store, responder)
    mid, jid = await _setup(sm, 1)
    jid_box.append(jid)
    with caplog.at_level(logging.WARNING, logger="feynman_api.jobs.worker"):
        assert await run_once(sm, ctx, HANDLERS) is True

    # LeaseLost came from the keep_lease after storing the chunk, not from mark_succeeded.
    assert "lease lost during run" in caplog.text
    assert "discarding result" not in caplog.text
    assert len(fake.calls) == 1
    kmap = await _map(sm, mid)
    assert kmap.status == "processing"
    assert kmap.revision == 0
    assert await _concepts(sm, mid) == []
    assert [c.status for c in await _chunks(sm, mid)] == ["pending"]
    job = await _job(sm, jid)
    assert job.status == "running"
    assert job.attempts == 2
    assert job.result is None
    assert job.last_error is None
    assert failed_calls == []


async def test_lost_lease_final_write_rolls_back(sm, test_settings, file_store) -> None:  # type: ignore[no-untyped-def]
    jid_box: list[UUID] = []

    async def responder(call: FakeCall) -> dict[str, Any]:
        if _is_merge(call):
            await _bump_attempts(sm, jid_box[0])
        return _one_concept_per_chunk(call)

    ctx, fake = _ctx(test_settings, file_store, responder, knowledge_map_chunk_chars=SMALL_CHUNKS)
    mid, jid = await _setup(sm, 2, old_concepts=1)
    jid_box.append(jid)
    assert await run_once(sm, ctx, HANDLERS) is True

    assert _merge_calls(fake) == 1
    kmap = await _map(sm, mid)
    assert kmap.status == "processing"
    assert kmap.revision == 0
    assert [c.title for c in await _concepts(sm, mid)] == ["Old 0"]
    job = await _job(sm, jid)
    assert job.status == "running"
    assert job.result is None


async def test_refusal_fails_with_message(sm, test_settings, file_store) -> None:  # type: ignore[no-untyped-def]
    def responder(call: FakeCall) -> dict[str, Any]:
        raise LLMRefusalError("refused")

    ctx, _ = _ctx(test_settings, file_store, responder)
    mid, jid = await _setup(sm, 1)
    assert await run_once(sm, ctx, HANDLERS) is True

    kmap = await _map(sm, mid)
    assert kmap.status == "failed"
    assert kmap.error_message == MSG_MAP_FAILED
    job = await _job(sm, jid)
    assert job.status == "failed"
    assert job.attempts == 1
    assert job.last_error == MSG_MAP_FAILED


async def test_merge_failure_falls_back(sm, test_settings, file_store) -> None:  # type: ignore[no-untyped-def]
    def responder(call: FakeCall) -> dict[str, Any]:
        if _is_merge(call):
            raise LLMOutputValidationError("bad merge")
        return _one_concept_per_chunk(call)

    ctx, fake = _ctx(test_settings, file_store, responder, knowledge_map_chunk_chars=SMALL_CHUNKS)
    mid, jid = await _setup(sm, 3)
    assert await run_once(sm, ctx, HANDLERS) is True

    assert _merge_calls(fake) == 1
    kmap = await _map(sm, mid)
    assert kmap.status == "ready"
    assert [c.title for c in await _concepts(sm, mid)] == ["Concept 0", "Concept 1", "Concept 2"]
    job = await _job(sm, jid)
    assert job.status == "succeeded"
    assert job.result is not None
    assert [c["step"] for c in job.result["usage"]["calls"]] == ["chunk"] * 3


async def test_llm_disabled_message(sm, test_settings, file_store) -> None:  # type: ignore[no-untyped-def]
    ctx, fake = _ctx(test_settings, file_store, None, llm=False)
    mid, jid = await _setup(sm, 1)
    assert await run_once(sm, ctx, HANDLERS) is True

    kmap = await _map(sm, mid)
    assert kmap.status == "failed"
    assert kmap.error_message == MSG_LLM_DISABLED
    assert (await _job(sm, jid)).status == "failed"
    assert fake.calls == []


async def test_usage_summed_into_result(sm, test_settings, file_store) -> None:  # type: ignore[no-untyped-def]
    ctx, _ = _ctx(
        test_settings, file_store, _one_concept_per_chunk, knowledge_map_chunk_chars=SMALL_CHUNKS
    )
    _, jid = await _setup(sm, 3)
    assert await run_once(sm, ctx, HANDLERS) is True

    job = await _job(sm, jid)
    assert job.result is not None
    usage = job.result["usage"]
    calls = usage["calls"]
    assert [(c["step"], c.get("index")) for c in calls] == [
        ("chunk", 0),
        ("chunk", 1),
        ("chunk", 2),
        ("merge", None),
    ]
    for name in ("input_tokens", "output_tokens", "cached_input_tokens"):
        assert usage["total"][name] == sum(c[name] for c in calls)
    assert usage["total"]["input_tokens"] > 0
    assert all(c["model_id"] == ctx.settings.llm_model_knowledge_map for c in calls)
    assert job.result["chunks"] == 3
    assert job.result["concepts"] == 3


async def test_rebuild_keeps_old_concepts_until_success(  # type: ignore[no-untyped-def]
    sm, test_settings, file_store
) -> None:
    def responder(call: FakeCall) -> dict[str, Any]:
        raise LLMRefusalError("refused")

    ctx, _ = _ctx(test_settings, file_store, responder)
    mid, jid = await _setup(sm, 1, old_concepts=2)
    before = [(c.id, c.title, c.position) for c in await _concepts(sm, mid)]
    assert await run_once(sm, ctx, HANDLERS) is True

    assert (await _job(sm, jid)).status == "failed"
    assert (await _map(sm, mid)).status == "failed"
    assert [(c.id, c.title, c.position) for c in await _concepts(sm, mid)] == before
    assert len(before) == 2


async def test_exhausted_retries_generic_message(sm, test_settings, file_store) -> None:  # type: ignore[no-untyped-def]
    def responder(call: FakeCall) -> dict[str, Any]:
        raise LLMUnavailableError("down")

    ctx, fake = _ctx(test_settings, file_store, responder)
    mid, jid = await _setup(sm, 1)
    for _ in range(3):
        await _make_due(sm, jid)
        assert await run_once(sm, ctx, HANDLERS) is True

    assert len(fake.calls) == 3
    kmap = await _map(sm, mid)
    assert kmap.status == "failed"
    assert kmap.error_message == MSG_MAP_GENERIC
    assert BuildKnowledgeMapHandler.generic_failure == MSG_MAP_GENERIC
    job = await _job(sm, jid)
    assert job.status == "failed"
    assert job.attempts == 3


async def test_broken_on_failed_still_fails_map(  # type: ignore[no-untyped-def]
    sm, test_settings, file_store, monkeypatch
) -> None:
    async def broken_on_failed(self, db, job, user_message) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("on_failed broke")

    def responder(call: FakeCall) -> dict[str, Any]:
        raise LLMUnavailableError("down")

    monkeypatch.setattr(BuildKnowledgeMapHandler, "on_failed", broken_on_failed)
    ctx, _ = _ctx(test_settings, file_store, responder)
    mid, jid = await _setup(sm, 1)
    for _ in range(3):
        await _make_due(sm, jid)
        assert await run_once(sm, ctx, HANDLERS) is True

    kmap = await _map(sm, mid)
    assert kmap.status == "failed"
    assert kmap.error_message == MSG_MAP_GENERIC
    job = await _job(sm, jid)
    assert job.status == "failed"
    assert job.locked_until is None


async def test_no_concepts_fails(sm, test_settings, file_store) -> None:  # type: ignore[no-untyped-def]
    def responder(call: FakeCall) -> dict[str, Any]:
        if _is_merge(call):
            return {"groups": []}
        return {"concepts": []}

    ctx, fake = _ctx(test_settings, file_store, responder, knowledge_map_chunk_chars=SMALL_CHUNKS)
    mid, jid = await _setup(sm, 2)
    assert await run_once(sm, ctx, HANDLERS) is True

    assert _merge_calls(fake) == 0
    kmap = await _map(sm, mid)
    assert kmap.status == "failed"
    assert kmap.error_message == MSG_MAP_FAILED
    assert (await _job(sm, jid)).status == "failed"
    assert await _concepts(sm, mid) == []
