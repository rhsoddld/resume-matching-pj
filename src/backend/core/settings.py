from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings (12-factor style)."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    app_name: str = "resume-matching-api"
    environment: str = Field("local", description="Environment name: local/dev/prod")

    # HTTP
    api_prefix: str = "/api"
    ingestion_api_key: str | None = None
    ingestion_rate_limit_per_minute: int = 3
    ingestion_allow_async: bool = True

    # OpenAI / model
    openai_api_key: str
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_agent_model: str = "gpt-4.1-mini"
    openai_agent_live_mode: bool = True
    openai_agents_sdk_enabled: bool = True
    query_fallback_model: str = "gpt-4.1-mini"
    query_fallback_enabled: bool = True
    query_fallback_confidence_threshold: float = 0.62
    query_fallback_unknown_ratio_threshold: float = 0.55
    rerank_enabled: bool = False
    rerank_model: str = "gpt-4.1-mini"
    rerank_mode: str = "embedding"
    rerank_embedding_model: str = "text-embedding-3-small"
    rerank_top_n: int = 50
    fairness_guardrails_enabled: bool = True
    fairness_policy_version: str = "v1"
    fairness_sensitive_term_enabled: bool = True
    fairness_max_culture_weight: float = 0.2
    fairness_min_must_have_match_rate: float = 0.5
    fairness_high_culture_confidence: float = 0.7
    fairness_rank_score_floor: float = 0.7
    fairness_topk_distribution_min: int = 5
    fairness_seniority_concentration_threshold: float = 0.85

    # Mongo
    mongodb_uri: str
    mongodb_db: str = "resume_matching"
    mongodb_max_pool_size: int = 100
    mongodb_min_pool_size: int = 0
    mongodb_server_selection_timeout_ms: int = 30_000
    mongodb_connect_timeout_ms: int = 10_000
    mongodb_socket_timeout_ms: int = 30_000
    mongodb_max_idle_time_ms: int | None = 60_000
    mongodb_retry_writes: bool = True

    # Milvus / vector store
    milvus_uri: str
    milvus_user: str | None = None
    milvus_password: str | None = None
    milvus_collection: str = "candidate_embeddings"
    milvus_pool_size: int = 4
    milvus_preload_on_startup: bool = True
    milvus_load_timeout_sec: int = 60

    # LangSmith (observability for LLM flows)
    langsmith_api_key: str | None = None
    langsmith_project: str | None = None

    # Misc
    log_level: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
