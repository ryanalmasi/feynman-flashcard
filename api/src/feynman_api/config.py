from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    environment: Literal["dev", "test", "prod"] = "dev"
    health_db_timeout_seconds: float = 2.0
    upload_dir: Path = Path("var/uploads")
    hibp_enabled: bool = True
    hibp_timeout_seconds: float = 2.0
    session_cookie_secure: bool = True
    login_email_failure_limit: int = 5
    login_ip_limit: int = 20
    login_window_seconds: int = 900
    account_delete_failure_limit: int = 5
    account_delete_window_seconds: int = 900
    register_ip_limit: int = 5
    register_window_seconds: int = 3600
    job_lease_seconds: int = 300
    job_poll_interval_seconds: float = 1.0
    job_backoff_base_seconds: float = 10.0
    max_upload_bytes: int = 20 * 1024 * 1024
    max_pdf_pages: int = 200
    min_document_text_chars: int = 100
    upload_multipart_allowance_bytes: int = 64 * 1024
    llm_enabled: bool = False
    anthropic_api_key: SecretStr | None = None
    llm_model_knowledge_map: str = "claude-sonnet-5-5"
    llm_model_flashcards: str = "claude-haiku-5-5"
    llm_effort: Literal["low", "medium", "high"] = "medium"
    llm_request_timeout_seconds: float = 240.0
    llm_job_lease_seconds: int = 600
    knowledge_map_chunk_chars: int = 120_000
    knowledge_map_parallel_chunks: int = 4
    max_document_text_chars: int = 2_000_000
    map_build_limit: int = 5
    card_generation_limit: int = 20
    llm_limit_window_seconds: int = 86_400

    @model_validator(mode="after")
    def _lease_covers_request_timeout(self) -> Self:
        # One provider call takes at most one request timeout (SDK retries are off), so the
        # lease must outlast it with margin, or a slow call could lose its lease mid-flight.
        if self.llm_job_lease_seconds < self.llm_request_timeout_seconds + 60:
            raise ValueError(
                "llm_job_lease_seconds must be at least llm_request_timeout_seconds + 60"
            )
        return self


class MigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    migration_database_url: SecretStr
