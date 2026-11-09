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
