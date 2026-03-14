from __future__ import annotations

import logging
import re
import time
from typing import Any

from backend.core.database import get_collection
from backend.core.exceptions import ExternalDependencyError, RepositoryError
from backend.schemas.job import INDUSTRY_STANDARD_DICTIONARY, normalize_industry_label
from backend.services.retrieval_service import RetrievalService
from backend.services.job_profile_extractor import JobProfile


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
_INDUSTRY_CATEGORY_MAP = {
    canonical: [term.strip().lower() for term in payload.get("category_terms", []) if isinstance(term, str)]
    for canonical, payload in INDUSTRY_STANDARD_DICTIONARY.items()
}


def _compute_candidates_per_sec(*, candidates: int, elapsed_sec: float) -> float:
    if elapsed_sec <= 0:
        return 0.0
    return float(candidates) / elapsed_sec


def _normalize_token(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    token = value.strip().lower()
    token = re.sub(r"[-_]+", " ", token)
    token = re.sub(r"\s+", " ", token)
    return token


class HybridRetriever:
    """
    Phase 2 retrieval adapter:
    1) primary path: embedding + Milvus vector retrieval
    2) fallback path: Mongo query + deterministic lexical scoring
    """

    def __init__(self) -> None:
        self.retrieval_service = RetrievalService()

    def search_candidates(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        top_k: int,
        category: str | None,
        min_experience_years: float | None = None,
    ) -> list[dict[str, Any]]:
        started_at = time.perf_counter()
        keyword_hits = self._search_keyword_candidates(
            job_description=job_description,
            job_profile=job_profile,
            top_k=max(top_k * 3, 30),
            category=category,
            min_experience_years=min_experience_years,
        )
        try:
            vector_hits = self.retrieval_service.search_candidates(
                query_text=job_profile.query_text_for_embedding or job_description,
                top_k=max(top_k * 3, 30),
                category=category,
                min_experience_years=min_experience_years,
            )
            merged_hits = self._merge_fusion_hits(
                vector_hits=vector_hits,
                keyword_hits=keyword_hits,
                job_profile=job_profile,
                category=category,
                min_experience_years=min_experience_years,
                top_k=top_k,
            )
            elapsed_sec = time.perf_counter() - started_at
            candidates_processed = len(vector_hits) + len(keyword_hits)
            logger.info(
                "hybrid_retrieval_metrics processed=%s vector_hits=%s keyword_hits=%s returned=%s elapsed_ms=%.2f candidates_per_sec=%.2f",
                candidates_processed,
                len(vector_hits),
                len(keyword_hits),
                len(merged_hits),
                elapsed_sec * 1000.0,
                _compute_candidates_per_sec(candidates=candidates_processed, elapsed_sec=elapsed_sec),
            )
            return merged_hits
        except ExternalDependencyError:
            logger.warning("Vector retrieval unavailable. Falling back to Mongo lexical retrieval.")
            if keyword_hits:
                elapsed_sec = time.perf_counter() - started_at
                logger.info(
                    "hybrid_retrieval_metrics processed=%s vector_hits=%s keyword_hits=%s returned=%s elapsed_ms=%.2f candidates_per_sec=%.2f fallback=keyword_only",
                    len(keyword_hits),
                    0,
                    len(keyword_hits),
                    min(len(keyword_hits), top_k),
                    elapsed_sec * 1000.0,
                    _compute_candidates_per_sec(candidates=len(keyword_hits), elapsed_sec=elapsed_sec),
                )
                return keyword_hits[:top_k]
            raise

    def _search_keyword_candidates(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        top_k: int,
        category: str | None,
        min_experience_years: float | None,
    ) -> list[dict[str, Any]]:
        started_at = time.perf_counter()
        try:
            terms = self._build_query_terms(job_description=job_description, job_profile=job_profile)
            query = self._build_query(
                terms=terms,
                category=category,
                min_experience_years=min_experience_years,
                industry=job_profile.metadata_filters.get("industry") if isinstance(job_profile.metadata_filters, dict) else None,
            )
            projection = {
                "_id": 0,
                "candidate_id": 1,
                "source_dataset": 1,
                "category": 1,
                "metadata.location": 1,
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
            scored_hits = [
                self._doc_to_hit(
                    doc=doc,
                    terms=terms,
                    category=category,
                    industry=job_profile.metadata_filters.get("industry") if isinstance(job_profile.metadata_filters, dict) else None,
                    min_experience_years=min_experience_years,
                    preferred_seniority=job_profile.preferred_seniority,
                )
                for doc in docs
            ]
            scored_hits = [hit for hit in scored_hits if hit["candidate_id"]]
            scored_hits.sort(key=lambda item: item["fusion_score"], reverse=True)
            limited_hits = scored_hits[:top_k]
            elapsed_sec = time.perf_counter() - started_at
            logger.info(
                "keyword_retrieval_metrics scanned=%s returned=%s elapsed_ms=%.2f candidates_per_sec=%.2f",
                len(docs),
                len(limited_hits),
                elapsed_sec * 1000.0,
                _compute_candidates_per_sec(candidates=len(docs), elapsed_sec=elapsed_sec),
            )
            return limited_hits
        except Exception as exc:
            logger.exception("Mongo fallback retrieval failed.")
            if isinstance(exc, RepositoryError):
                raise ExternalDependencyError("Both vector retrieval and Mongo fallback failed.") from exc
            raise ExternalDependencyError("Both vector retrieval and Mongo fallback failed.") from exc

    def _merge_fusion_hits(
        self,
        *,
        vector_hits: list[dict[str, Any]],
        keyword_hits: list[dict[str, Any]],
        job_profile: JobProfile,
        category: str | None,
        min_experience_years: float | None,
        top_k: int,
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}

        for hit in vector_hits:
            candidate_id = hit.get("candidate_id")
            if not candidate_id:
                continue
            raw_vector_score = float(hit.get("score", 0.0))
            vector_score = self._normalize_vector_similarity(raw_vector_score)
            metadata_score = self._metadata_score(
                category=category,
                industry=job_profile.metadata_filters.get("industry") if isinstance(job_profile.metadata_filters, dict) else None,
                min_experience_years=min_experience_years,
                preferred_seniority=job_profile.preferred_seniority,
                candidate_category=hit.get("category"),
                candidate_experience_years=hit.get("experience_years"),
                candidate_seniority_level=hit.get("seniority_level"),
            )
            fusion_score = self._fusion_score(
                vector_score=vector_score,
                keyword_score=0.0,
                metadata_score=metadata_score,
            )
            merged[candidate_id] = {
                "candidate_id": candidate_id,
                "source_dataset": hit.get("source_dataset"),
                "category": hit.get("category"),
                "experience_years": hit.get("experience_years"),
                "seniority_level": hit.get("seniority_level"),
                "score": raw_vector_score,
                "vector_score": round(vector_score, 4),
                "keyword_score": 0.0,
                "metadata_score": round(metadata_score, 4),
                "fusion_score": round(fusion_score, 4),
            }

        for hit in keyword_hits:
            candidate_id = hit.get("candidate_id")
            if not candidate_id:
                continue
            existing = merged.get(candidate_id)
            keyword_score = float(hit.get("keyword_score", hit.get("fusion_score", 0.0)))
            metadata_score = float(hit.get("metadata_score", 0.0))
            if existing is None:
                pseudo_raw_vector_score = (keyword_score * 2.0) - 1.0
                fusion_score = self._fusion_score(
                    vector_score=0.0,
                    keyword_score=keyword_score,
                    metadata_score=metadata_score,
                )
                merged[candidate_id] = {
                    "candidate_id": candidate_id,
                    "source_dataset": hit.get("source_dataset"),
                    "category": hit.get("category"),
                    "experience_years": hit.get("experience_years"),
                    "seniority_level": hit.get("seniority_level"),
                    "score": round(pseudo_raw_vector_score, 4),
                    "vector_score": 0.0,
                    "keyword_score": round(keyword_score, 4),
                    "metadata_score": round(metadata_score, 4),
                    "fusion_score": round(fusion_score, 4),
                }
                continue

            existing["keyword_score"] = round(max(float(existing.get("keyword_score", 0.0)), keyword_score), 4)
            existing["metadata_score"] = round(max(float(existing.get("metadata_score", 0.0)), metadata_score), 4)
            existing["fusion_score"] = round(
                self._fusion_score(
                    vector_score=float(existing.get("vector_score", 0.0)),
                    keyword_score=float(existing.get("keyword_score", 0.0)),
                    metadata_score=float(existing.get("metadata_score", 0.0)),
                ),
                4,
            )

        ranked = sorted(merged.values(), key=lambda item: float(item.get("fusion_score", 0.0)), reverse=True)
        return ranked[:top_k]

    def _build_query_terms(self, *, job_description: str, job_profile: JobProfile) -> list[str]:
        query_text = job_profile.lexical_query or job_profile.query_text_for_embedding or job_description
        deduped: list[str] = []
        for role in job_profile.roles:
            role_token = role.strip().lower()
            if role_token and role_token not in deduped:
                deduped.append(role_token)
        for signal in sorted(job_profile.skill_signals, key=lambda s: {"must have": 4, "main focus": 3, "nice to have": 2, "familiarity": 1, "unknown": 0}.get(s.strength, 0), reverse=True):
            token = signal.name.strip().lower()
            if token and token not in deduped:
                deduped.append(token)
        for signal in job_profile.capability_signals:
            token = signal.name.strip().lower()
            if token and token not in deduped:
                deduped.append(token)
        for term in [*job_profile.required_skills, *job_profile.related_skills]:
            normalized = term.strip().lower() if isinstance(term, str) else ""
            if normalized and normalized not in deduped:
                deduped.append(normalized)
        for token in self._extract_terms(query_text):
            if token not in deduped:
                deduped.append(token)
        return deduped[:24]

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
    def _industry_key(industry: str | None) -> str:
        return normalize_industry_label(industry) or _normalize_token(industry)

    @classmethod
    def _build_query(
        cls,
        *,
        terms: list[str],
        category: str | None,
        min_experience_years: float | None,
        industry: str | None = None,
    ) -> dict[str, Any]:
        clauses: list[dict[str, Any]] = []
        if category:
            clauses.append({"category": {"$regex": f"^{re.escape(str(category).strip())}$", "$options": "i"}})
        else:
            industry_key = cls._industry_key(industry)
            industry_terms = _INDUSTRY_CATEGORY_MAP.get(industry_key, [])
            if industry_terms:
                clauses.append(
                    {
                        "$or": [
                            {"category": {"$regex": re.escape(term), "$options": "i"}}
                            for term in industry_terms
                        ]
                    }
                )
        if min_experience_years is not None:
            clauses.append({"parsed.experience_years": {"$gte": float(min_experience_years)}})
        if not terms:
            if not clauses:
                return {}
            if len(clauses) == 1:
                return clauses[0]
            return {"$and": clauses}
        regex = "|".join(re.escape(term) for term in terms[:8])
        clauses.append(
            {
                "$or": [
                    {"parsed.normalized_skills": {"$in": terms}},
                    {"parsed.core_skills": {"$in": terms}},
                    {"parsed.expanded_skills": {"$in": terms}},
                    {"parsed.skills": {"$in": terms}},
                    {"parsed.summary": {"$regex": regex, "$options": "i"}},
                ]
            }
        )
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    @staticmethod
    def _doc_to_hit(
        *,
        doc: dict[str, Any],
        terms: list[str],
        category: str | None,
        industry: str | None,
        min_experience_years: float | None,
        preferred_seniority: str | None,
    ) -> dict[str, Any]:
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
        keyword_score = round(min(1.0, overlap), 4)
        metadata_score = round(
            HybridRetriever._metadata_score(
                category=category,
                industry=industry,
                min_experience_years=min_experience_years,
                preferred_seniority=preferred_seniority,
                candidate_category=doc.get("category"),
                candidate_experience_years=parsed.get("experience_years"),
                candidate_seniority_level=parsed.get("seniority_level"),
            ),
            4,
        )
        fusion_score = round(
            HybridRetriever._fusion_score(
                vector_score=0.0,
                keyword_score=keyword_score,
                metadata_score=metadata_score,
            ),
            4,
        )

        return {
            "candidate_id": doc.get("candidate_id"),
            "source_dataset": doc.get("source_dataset"),
            "category": doc.get("category"),
            "experience_years": parsed.get("experience_years"),
            "seniority_level": parsed.get("seniority_level"),
            "score": round((keyword_score * 2.0) - 1.0, 4),
            "vector_score": 0.0,
            "keyword_score": keyword_score,
            "metadata_score": metadata_score,
            "fusion_score": fusion_score,
        }

    @staticmethod
    def _normalize_vector_similarity(raw_similarity: float) -> float:
        normalized = (raw_similarity + 1.0) / 2.0
        return max(0.0, min(1.0, normalized))

    @staticmethod
    def _fusion_score(*, vector_score: float, keyword_score: float, metadata_score: float) -> float:
        return max(0.0, min(1.0, (vector_score * 0.55) + (keyword_score * 0.30) + (metadata_score * 0.15)))

    @staticmethod
    def _metadata_score(
        *,
        category: str | None,
        industry: str | None,
        min_experience_years: float | None,
        preferred_seniority: str | None,
        candidate_category: str | None,
        candidate_experience_years: float | None,
        candidate_seniority_level: str | None,
    ) -> float:
        normalized_candidate_category = _normalize_token(candidate_category)
        category_score = 0.5
        if category:
            category_score = 1.0 if normalized_candidate_category == _normalize_token(category) else 0.0

        industry_score = 0.5
        normalized_industry = HybridRetriever._industry_key(industry)
        if normalized_industry:
            industry_terms = {_normalize_token(term) for term in _INDUSTRY_CATEGORY_MAP.get(normalized_industry, [])}
            industry_terms = {term for term in industry_terms if term}
            if not industry_terms:
                industry_score = 0.5
            else:
                industry_score = (
                    1.0
                    if any(term in normalized_candidate_category for term in industry_terms)
                    else 0.0
                )

        experience_score = 0.5
        if min_experience_years is not None:
            if candidate_experience_years is None:
                experience_score = 0.0
            elif min_experience_years <= 0:
                experience_score = 1.0
            else:
                experience_score = max(0.0, min(1.0, float(candidate_experience_years) / float(min_experience_years)))

        seniority_score = 0.5
        if preferred_seniority:
            if not candidate_seniority_level:
                seniority_score = 0.2
            elif candidate_seniority_level.strip().lower() == preferred_seniority.strip().lower():
                seniority_score = 1.0
            else:
                seniority_score = 0.4

        if normalized_industry:
            return (category_score * 0.4) + (industry_score * 0.15) + (experience_score * 0.3) + (seniority_score * 0.15)
        return (category_score * 0.5) + (experience_score * 0.35) + (seniority_score * 0.15)
