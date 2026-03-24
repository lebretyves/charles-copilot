"""CHARLES Backend — Configuration."""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    database_url: str = "postgresql+asyncpg://charles:charles_dev_2026@localhost:5432/charles"
    redis_url: str = "redis://localhost:6379/0"
    ws_port: int = 8000
    kb_path: str = "kb"
    vitaldb_metadata: str = "/data/vitaldb/clinical_metadata.csv"
    vitaldb_cases: str = "/data/vitaldb/cases"
    # LLM
    llm_provider: str = "ollama"  # ollama | openai
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "meditron:7b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # Auth
    jwt_secret: str = "charles-dev-secret-2026"
    # CORS : origines autorisées (séparer par virgule en prod, ex: https://charles.monhote.com)
    cors_origins: str = "http://localhost:3000,http://localhost:5173"


settings = Settings()
