from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class IngestionRunRequest(BaseModel):
    source: Literal["sneha", "suri", "all"] = "all"
    target: Literal["all", "mongo", "milvus"] = "all"
    milvus_from_mongo: bool = False
    force_mongo_upsert: bool = False
    force_reembed: bool = False
    dry_run: bool = False
    parser_mode: Literal["rule", "spacy", "hybrid"] = "hybrid"
    csv_chunk_size: int = Field(2000, ge=1, le=100_000)
    batch_size: int = Field(32, ge=1, le=2000)
    sneha_limit: int | None = Field(default=None, ge=1, le=2_000_000)
    suri_limit: int | None = Field(default=3000, ge=1, le=2_000_000)
    async_mode: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_options(self) -> "IngestionRunRequest":
        if self.milvus_from_mongo and self.target != "milvus":
            raise ValueError("milvus_from_mongo=true requires target='milvus'.")
        return self


class IngestionRunResponse(BaseModel):
    request_id: UUID
    status: Literal["accepted", "completed"]
    message: str
    source: Literal["sneha", "suri", "all"]
    target: Literal["all", "mongo", "milvus"]
    dry_run: bool
    accepted_at: datetime
    completed_at: datetime | None = None
