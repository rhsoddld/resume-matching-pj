from __future__ import annotations

from typing import Any
import logging

from backend.core.exceptions import ExternalDependencyError
from backend.core.providers import get_openai_client
from backend.core.settings import settings
from backend.core.vector_store import search_embeddings


logger = logging.getLogger(__name__)


class RetrievalService:
    def search_candidates(self, *, job_description: str, top_k: int, category: str | None) -> list[dict[str, Any]]:
        try:
            client = get_openai_client()
            response = client.embeddings.create(input=[job_description], model=settings.openai_embedding_model)
            query_vector = response.data[0].embedding
            return search_embeddings(query_vector=query_vector, top_k=top_k, category=category)
        except Exception as exc:
            logger.exception("Candidate retrieval failed.")
            raise ExternalDependencyError("Failed to retrieve candidates for the current request.") from exc
