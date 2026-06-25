from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    supervisor_model: str = "claude-sonnet-4-6"
    specialist_model: str = "gpt-4o-mini"
    reviewer_model: str = "claude-haiku-4-5-20251001"

    # Postgres
    database_url: str = "postgresql://postgres:postgres@localhost:5432/agent_orchestration"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "agent_memory"

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "agent-orchestration"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-me-in-production"
    debug: bool = True

    # HITL
    hitl_confidence_threshold: float = 0.6
    hitl_review_timeout_seconds: int = 300

    # Tools
    web_search_rpm: int = 10
    code_exec_timeout_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
