import pytest
from pydantic import ValidationError

from feynman_api.config import Settings


def test_missing_database_url_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_secret_not_in_repr() -> None:
    s = Settings(
        database_url="postgresql+asyncpg://u:hunter2@h/db",
        _env_file=None,
    )
    assert "hunter2" not in repr(s)
    assert "hunter2" not in str(s.model_dump())


def test_llm_defaults() -> None:
    s = Settings(database_url="postgresql+asyncpg://u:p@h/db", _env_file=None)
    assert s.llm_enabled is False
    assert s.anthropic_api_key is None
    assert s.llm_model_knowledge_map == "claude-sonnet-5-5"
    assert s.llm_model_flashcards == "claude-haiku-5-5"
    assert s.llm_effort == "medium"
    assert s.llm_request_timeout_seconds == 240.0
    assert s.llm_job_lease_seconds == 600
    assert s.knowledge_map_chunk_chars == 120_000
    assert s.knowledge_map_parallel_chunks == 4
    assert s.max_document_text_chars == 2_000_000
    assert s.map_build_limit == 5
    assert s.card_generation_limit == 20
    assert s.llm_limit_window_seconds == 86_400


def test_lease_validator_rejects_short_lease() -> None:
    with pytest.raises(ValidationError, match="llm_job_lease_seconds must be at least"):
        Settings(
            database_url="postgresql+asyncpg://u:p@h/db",
            llm_job_lease_seconds=200,
            llm_request_timeout_seconds=240,
            _env_file=None,
        )
    ok = Settings(
        database_url="postgresql+asyncpg://u:p@h/db",
        llm_job_lease_seconds=300,
        llm_request_timeout_seconds=240,
        _env_file=None,
    )
    assert ok.llm_job_lease_seconds == 300


def test_api_key_not_in_repr() -> None:
    s = Settings(
        database_url="postgresql+asyncpg://u:p@h/db",
        anthropic_api_key="sk-ant-SECRET-123",
        _env_file=None,
    )
    assert "SECRET-123" not in repr(s)
    assert "SECRET-123" not in str(s.model_dump())
