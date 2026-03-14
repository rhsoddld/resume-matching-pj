from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central application settings (12-factor style)."""

    # App
    app_name: str = "resume-matching-api"
    environment: str = Field("local", description="Environment name: local/dev/prod")

    # HTTP
    api_prefix: str = "/api"
    ingestion_api_key: str | None = Field(None, env="INGESTION_API_KEY")
    ingestion_rate_limit_per_minute: int = Field(3, env="INGESTION_RATE_LIMIT_PER_MINUTE")
    ingestion_allow_async: bool = Field(True, env="INGESTION_ALLOW_ASYNC")

    # OpenAI / model
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4.1-mini", env="OPENAI_MODEL")
    openai_embedding_model: str = Field("text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL")
    openai_agent_model: str = Field("gpt-4.1-mini", env="OPENAI_AGENT_MODEL")
    openai_agent_live_mode: bool = Field(True, env="OPENAI_AGENT_LIVE_MODE")
    openai_agents_sdk_enabled: bool = Field(True, env="OPENAI_AGENTS_SDK_ENABLED")
    query_fallback_model: str = Field("gpt-4.1-mini", env="QUERY_FALLBACK_MODEL")
    query_fallback_enabled: bool = Field(True, env="QUERY_FALLBACK_ENABLED")
    query_fallback_confidence_threshold: float = Field(0.62, env="QUERY_FALLBACK_CONFIDENCE_THRESHOLD")
    query_fallback_unknown_ratio_threshold: float = Field(0.55, env="QUERY_FALLBACK_UNKNOWN_RATIO_THRESHOLD")
    rerank_enabled: bool = Field(False, env="RERANK_ENABLED")
    rerank_model: str = Field("gpt-4.1-mini", env="RERANK_MODEL")
    rerank_mode: str = Field("embedding", env="RERANK_MODE")
    rerank_embedding_model: str = Field("text-embedding-3-small", env="RERANK_EMBEDDING_MODEL")
    rerank_top_n: int = Field(50, env="RERANK_TOP_N")
    fairness_guardrails_enabled: bool = Field(True, env="FAIRNESS_GUARDRAILS_ENABLED")
    fairness_policy_version: str = Field("v1", env="FAIRNESS_POLICY_VERSION")
    fairness_sensitive_term_enabled: bool = Field(True, env="FAIRNESS_SENSITIVE_TERM_ENABLED")
    fairness_max_culture_weight: float = Field(0.2, env="FAIRNESS_MAX_CULTURE_WEIGHT")
    fairness_min_must_have_match_rate: float = Field(0.5, env="FAIRNESS_MIN_MUST_HAVE_MATCH_RATE")
    fairness_high_culture_confidence: float = Field(0.7, env="FAIRNESS_HIGH_CULTURE_CONFIDENCE")
    fairness_rank_score_floor: float = Field(0.7, env="FAIRNESS_RANK_SCORE_FLOOR")
    fairness_topk_distribution_min: int = Field(5, env="FAIRNESS_TOPK_DISTRIBUTION_MIN")
    fairness_seniority_concentration_threshold: float = Field(0.85, env="FAIRNESS_SENIORITY_CONCENTRATION_THRESHOLD")

    # Mongo
    mongodb_uri: str = Field(..., env="MONGODB_URI")
    mongodb_db: str = Field("resume_matching", env="MONGODB_DB")
    mongodb_max_pool_size: int = Field(100, env="MONGODB_MAX_POOL_SIZE")
    mongodb_min_pool_size: int = Field(0, env="MONGODB_MIN_POOL_SIZE")
    mongodb_server_selection_timeout_ms: int = Field(30_000, env="MONGODB_SERVER_SELECTION_TIMEOUT_MS")
    mongodb_connect_timeout_ms: int = Field(10_000, env="MONGODB_CONNECT_TIMEOUT_MS")
    mongodb_socket_timeout_ms: int = Field(30_000, env="MONGODB_SOCKET_TIMEOUT_MS")
    mongodb_max_idle_time_ms: int | None = Field(60_000, env="MONGODB_MAX_IDLE_TIME_MS")
    mongodb_retry_writes: bool = Field(True, env="MONGODB_RETRY_WRITES")

    # Milvus / vector store
    milvus_uri: str = Field(..., env="MILVUS_URI")
    milvus_user: str | None = Field(None, env="MILVUS_USER")
    milvus_password: str | None = Field(None, env="MILVUS_PASSWORD")
    milvus_collection: str = Field("candidate_embeddings", env="MILVUS_COLLECTION")
    milvus_pool_size: int = Field(4, env="MILVUS_POOL_SIZE")
    milvus_preload_on_startup: bool = Field(True, env="MILVUS_PRELOAD_ON_STARTUP")
    milvus_load_timeout_sec: int = Field(60, env="MILVUS_LOAD_TIMEOUT_SEC")

    # LangSmith (observability for LLM flows)
    langsmith_api_key: str | None = Field(None, env="LANGSMITH_API_KEY")
    langsmith_project: str | None = Field(None, env="LANGSMITH_PROJECT")

    # Misc
    log_level: str = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
