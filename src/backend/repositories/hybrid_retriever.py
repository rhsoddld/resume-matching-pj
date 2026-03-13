from __future__ import annotations

import logging
import re
from typing import Any

from backend.core.database import get_collection
from backend.core.exceptions import ExternalDependencyError, RepositoryError
from backend.services.retrieval_service import RetrievalService


logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9+.#-]{1,}")
_STOPWORDS = {
    "and",
    "or",
    "the",
    "with",
    "for",
    "from",
    "into",
    "years",
    "year",
    "experience",
    "required",
    "preferred",
    "plus",
    "role",
    "looking",
    "senior",
    "junior",
}


class HybridRetriever:
    """
    Phase 2 retrieval adapter:
    1) primary path: embedding + Milvus vector retrieval
    2) fallback path: Mongo query + deterministic lexical scoring
    """

    def __init__(self) -> None:
        self.retrieval_service = RetrievalService()

    def search_candidates(self, *, job_description: str, top_k: int, category: str | None) -> list[dict[str, Any]]:
        try:
            return self.retrieval_service.search_candidates(
                job_description=job_description,
                top_k=top_k,
                category=category,
            )
        except ExternalDependencyError:
            logger.warning("Vector retrieval unavailable. Falling back to Mongo lexical retrieval.")
            return self._search_mongo_fallback(
                job_description=job_description,
                top_k=top_k,
                category=category,
            )

    def _search_mongo_fallback(self, *, job_description: str, top_k: int, category: str | None) -> list[dict[str, Any]]:
        try:
            terms = self._extract_terms(job_description)
            query = self._build_query(terms=terms, category=category)
            projection = {
                "_id": 0,
                "candidate_id": 1,
                "source_dataset": 1,
                "category": 1,
                "parsed.summary": 1,
                "parsed.skills": 1,
                "parsed.normalized_skills": 1,
                "parsed.core_skills": 1,
                "parsed.expanded_skills": 1,
                "parsed.experience_years": 1,
                "parsed.seniority_level": 1,
            }
            scan_limit = max(50, top_k * 25)
            docs = list(get_collection("candidates").find(query, projection).limit(scan_limit))
            scored_hits = [self._doc_to_hit(doc=doc, terms=terms, category=category) for doc in docs]
            scored_hits = [hit for hit in scored_hits if hit["candidate_id"]]
            scored_hits.sort(key=lambda item: item["score"], reverse=True)
            return scored_hits[:top_k]
        except Exception as exc:
            logger.exception("Mongo fallback retrieval failed.")
            if isinstance(exc, RepositoryError):
                raise ExternalDependencyError("Both vector retrieval and Mongo fallback failed.") from exc
            raise ExternalDependencyError("Both vector retrieval and Mongo fallback failed.") from exc

    @staticmethod
    def _extract_terms(job_description: str) -> list[str]:
        tokens = [token.lower() for token in _TOKEN_RE.findall(job_description or "")]
        deduped: list[str] = []
        for token in tokens:
            if token in _STOPWORDS:
                continue
            if len(token) < 2:
                continue
            if token not in deduped:
                deduped.append(token)
        return deduped[:24]

    @staticmethod
    def _build_query(*, terms: list[str], category: str | None) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if category:
            query["category"] = category
        if not terms:
            return query
        regex = "|".join(re.escape(term) for term in terms[:8])
        query["$or"] = [
            {"parsed.normalized_skills": {"$in": terms}},
            {"parsed.core_skills": {"$in": terms}},
            {"parsed.expanded_skills": {"$in": terms}},
            {"parsed.skills": {"$in": terms}},
            {"parsed.summary": {"$regex": regex, "$options": "i"}},
        ]
        return query

    @staticmethod
    def _doc_to_hit(*, doc: dict[str, Any], terms: list[str], category: str | None) -> dict[str, Any]:
        parsed = doc.get("parsed", {})
        parsed = parsed if isinstance(parsed, dict) else {}
        token_pool = set()
        for key in ("skills", "normalized_skills", "core_skills", "expanded_skills"):
            values = parsed.get(key) or []
            for value in values:
                if isinstance(value, str) and value.strip():
                    token_pool.add(value.strip().lower())

        if terms:
            overlap = len(set(terms).intersection(token_pool)) / len(set(terms))
        else:
            overlap = 0.0
        category_bonus = 0.15 if category and doc.get("category") == category else 0.0
        experience_years = parsed.get("experience_years")
        experience_signal = 0.0
        if isinstance(experience_years, (int, float)):
            experience_signal = min(1.0, float(experience_years) / 20.0)
        score = round(min(1.0, overlap * 0.75 + category_bonus + experience_signal * 0.1), 4)

        return {
            "candidate_id": doc.get("candidate_id"),
            "source_dataset": doc.get("source_dataset"),
            "category": doc.get("category"),
            "experience_years": parsed.get("experience_years"),
            "seniority_level": parsed.get("seniority_level"),
            "score": score,
        }

