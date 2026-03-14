from __future__ import annotations

from typing import Any
import logging
import time

from backend.core.exceptions import ExternalDependencyError
from backend.core.providers import get_openai_client
from backend.core.settings import settings
from backend.core.vector_store import search_embeddings


logger = logging.getLogger(__name__)


def _compute_candidates_per_sec(*, candidates: int, elapsed_sec: float) -> float:
    if elapsed_sec <= 0:
        return 0.0
    return float(candidates) / elapsed_sec


class RetrievalService:
    def search_candidates(
        self,
        *,
        query_text: str,
        top_k: int,
        category: str | None,
        min_experience_years: float | None = None,
    ) -> list[dict[str, Any]]:
        started_at = time.perf_counter()
        try:
            client = get_openai_client()
            response = client.embeddings.create(input=[query_text], model=settings.openai_embedding_model)
            query_vector = response.data[0].embedding
            hits = search_embeddings(
                query_vector=query_vector,
                top_k=top_k,
                category=category,
                min_experience_years=min_experience_years,
            )
            elapsed_sec = time.perf_counter() - started_at
            logger.info(
                "vector_retrieval_metrics top_k=%s returned=%s elapsed_ms=%.2f candidates_per_sec=%.2f",
                top_k,
                len(hits),
                elapsed_sec * 1000.0,
                _compute_candidates_per_sec(candidates=len(hits), elapsed_sec=elapsed_sec),
            )
            return hits
        except Exception as exc:
            logger.exception("Candidate retrieval failed.")
            raise ExternalDependencyError("Failed to retrieve candidates for the current request.") from exc
