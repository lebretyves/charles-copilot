from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "charles-dev-secret-2026"
DEV_DEFAULT_PASSWORD = "charles2026"
DEV_ADMIN_PASSWORD = "admin2026"


def _read_secret_file(path_value: str | None) -> str | None:
    if not path_value:
        return None

    path = Path(path_value)
    if not path.is_file():
        raise ValueError(f"Secret file not found: {path}")

    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"Secret file is empty: {path}")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["dev", "prod"] = "dev"

    database_url: str = "postgresql+asyncpg://charles:charles_dev_2026@localhost:5432/charles"
    database_url_file: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    redis_url_file: str | None = None

    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_user: str = "charles"
    mqtt_password: str = "charles_mqtt_2026"
    mqtt_password_file: str | None = None

    kb_path: str = "kb"
    vitaldb_metadata: str = "vitaldb/clinical_metadata.csv"
    vitaldb_cases: str = "vitaldb/cases"
    vitaldb_waveforms: str = "vitaldb/waveforms"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_secret_file: str | None = None
    charles_default_password: str = DEV_DEFAULT_PASSWORD
    charles_default_password_file: str | None = None
    charles_admin_password: str = DEV_ADMIN_PASSWORD
    charles_admin_password_file: str | None = None
    auth_token_expiry_hours: int = 24

    cors_origins: str = (
        "https://localhost:3000,"
        "https://127.0.0.1:3000,"
        "http://localhost:3080,"
        "http://127.0.0.1:3080,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )
    trusted_hosts: str = "localhost,127.0.0.1"
    frontend_public_url: str = "https://localhost:3000"

    llm_provider: Literal["ollama", "openai"] = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "meditron:7b"
    openai_api_key: str = ""
    openai_api_key_file: str | None = None
    openai_model: str = "gpt-4o-mini"
    llm_analysis_timeout_s: int = 45

    rag_top_k: int = 4
    rag_min_score: float = 0.15
    rag_max_context_chars: int = 3200

    llm_job_stream: str = "charles:llm:jobs"
    llm_job_stream_maxlen: int = 2000
    llm_job_ttl_s: int = 3600
    llm_event_channel: str = "charles:llm:events"
    llm_worker_status_key: str = "charles:llm:worker_status"
    llm_worker_heartbeat_s: int = 10
    llm_worker_poll_block_ms: int = 5000
    llm_worker_max_retries: int = 1
    llm_worker_claim_ttl_s: int = 300

    audit_log_enabled: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def trusted_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @model_validator(mode="after")
    def apply_secret_files_and_validate(self) -> "Settings":
        secret_mappings = (
            ("database_url", "database_url_file"),
            ("redis_url", "redis_url_file"),
            ("mqtt_password", "mqtt_password_file"),
            ("jwt_secret", "jwt_secret_file"),
            ("charles_default_password", "charles_default_password_file"),
            ("charles_admin_password", "charles_admin_password_file"),
            ("openai_api_key", "openai_api_key_file"),
        )

        for target_field, source_field in secret_mappings:
            secret_value = _read_secret_file(getattr(self, source_field))
            if secret_value is not None:
                object.__setattr__(self, target_field, secret_value)

        if self.is_prod:
            issues: list[str] = []
            if self.jwt_secret == DEV_JWT_SECRET:
                issues.append("JWT_SECRET must be replaced in APP_ENV=prod")
            if self.charles_default_password == DEV_DEFAULT_PASSWORD:
                issues.append("CHARLES_DEFAULT_PASSWORD must be replaced in APP_ENV=prod")
            if self.charles_admin_password == DEV_ADMIN_PASSWORD:
                issues.append("CHARLES_ADMIN_PASSWORD must be replaced in APP_ENV=prod")
            if any(origin.startswith("http://") for origin in self.cors_origins_list):
                issues.append("CORS_ORIGINS must use HTTPS only in APP_ENV=prod")
            if self.frontend_public_url.startswith("http://"):
                issues.append("FRONTEND_PUBLIC_URL must use HTTPS in APP_ENV=prod")
            if "*" in self.trusted_hosts_list:
                issues.append("TRUSTED_HOSTS must not contain '*' in APP_ENV=prod")
            if issues:
                raise ValueError("Invalid production configuration: " + "; ".join(issues))

        return self


settings = Settings()
