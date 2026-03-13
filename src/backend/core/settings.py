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

    # OpenAI / model
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4.1-mini", env="OPENAI_MODEL")
    openai_embedding_model: str = Field("text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL")
    openai_agent_model: str = Field("gpt-4.1-mini", env="OPENAI_AGENT_MODEL")
    openai_agent_live_mode: bool = Field(True, env="OPENAI_AGENT_LIVE_MODE")

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
