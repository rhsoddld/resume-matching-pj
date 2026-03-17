from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings (12-factor style)."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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
    # Keep rerank OFF by default until measurable A/B gain is proven.
    rerank_enabled: bool = False
    # Legacy single-model field (kept for backward compatibility).
    rerank_model: str = "gpt-4.1-mini"
    # Routed rerank models (default path vs ambiguity/tie-break path).
    rerank_model_default: str = "gpt-4.1-mini"
    rerank_model_default_version: str = "baseline-v1"
    rerank_model_high_quality: str = "gpt-4o"
    rerank_model_high_quality_version: str = "hq-v1"
    rerank_mode: str = "embedding"
    rerank_embedding_model: str = "text-embedding-3-small"
    rerank_top_n: int = 50
    rerank_timeout_sec: float = 5.0
    rerank_gate_max_top_n: int = 8
    rerank_gate_top2_gap_threshold: float = 0.04
    rerank_gate_confidence_threshold: float = 0.65
    rerank_gate_unknown_ratio_threshold: float = 0.5
    rerank_require_ab_proof: bool = True
    rerank_ab_proven: bool = False
    agent_eval_top_n: int = 5
    eval_judge_model: str = "gpt-4o"
    eval_judge_model_version: str = "judge-v1"
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
    langsmith_tracing: bool = True
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str | None = None
    langsmith_project: str | None = None

    # Token Budget & Cache (R2.5)
    token_budget_enabled: bool = False
    token_budget_per_request: int = 20000  # max estimated tokens per match_jobs call
    token_estimated_per_agent_call: int = 800  # estimated tokens per single agent LLM call
    token_cache_enabled: bool = True  # cache match_jobs result by JD hash + params
    token_cache_ttl_sec: int = 300  # in-memory cache TTL (5 minutes)
    token_cache_max_size: int = 128  # LRU cache max entries

    # Retrieval Fusion Weights (R2.2 / HCR.1)
    retrieval_vector_weight: float = 0.48   # Milvus embedding similarity weight
    retrieval_keyword_weight: float = 0.37  # MongoDB lexical keyword score weight
    retrieval_metadata_weight: float = 0.15 # Metadata filter match weight

    # Ranking score blend (Deterministic vs Agent-weighted)
    rank_deterministic_weight: float = 0.30
    rank_agent_weight: float = 0.70

    # Fallback weight negotiation (when LLM negotiation fails/unavailable)
    fallback_recruiter_weights: dict[str, float] = {
        "skill": 0.30,
        "experience": 0.35,
        "technical": 0.20,
        "culture": 0.15,
    }
    fallback_hiring_manager_weights: dict[str, float] = {
        "skill": 0.40,
        "experience": 0.20,
        "technical": 0.30,
        "culture": 0.10,
    }
    fallback_recruiter_experience_years_threshold: float = 5.0
    fallback_recruiter_experience_boost: float = 0.10
    fallback_recruiter_technical_reduction: float = 0.05
    fallback_recruiter_culture_reduction: float = 0.05

    fallback_hm_required_skills_threshold: int = 6
    fallback_hm_technical_boost: float = 0.10
    fallback_hm_experience_reduction: float = 0.05
    fallback_hm_culture_reduction: float = 0.05

    # Misc
    log_level: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
