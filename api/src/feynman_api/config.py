from pathlib import Path
from typing import Literal

from pydantic import SecretStr
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
    register_ip_limit: int = 5
    register_window_seconds: int = 3600
    job_lease_seconds: int = 300
    job_poll_interval_seconds: float = 1.0
    job_backoff_base_seconds: float = 10.0
    max_upload_bytes: int = 20 * 1024 * 1024
    upload_multipart_allowance_bytes: int = 64 * 1024


class MigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    migration_database_url: SecretStr
