from __future__ import annotations

import logging
import re
import time
from typing import Any

from backend.core.database import get_collection
from backend.core.exceptions import ExternalDependencyError, RepositoryError
from backend.core.observability import traceable_op
from backend.core.providers import get_skill_ontology
from backend.core.settings import settings
from backend.services.retrieval_service import RetrievalService
from backend.services.job_profile_extractor import JobProfile
from backend.services.retrieval.hybrid_scoring import (
    INDUSTRY_CATEGORY_MAP,
    compute_keyword_score,
    fusion_score,
    industry_key,
    metadata_score,
    normalize_token,
    normalize_vector_similarity,
)
from backend.services.skill_ontology.normalization import clean_token, dedupe_preserve


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
def _compute_candidates_per_sec(*, candidates: int, elapsed_sec: float) -> float:
    if elapsed_sec <= 0:
        return 0.0
    return float(candidates) / elapsed_sec


class HybridRetriever:
    """
    Phase 2 retrieval adapter:
    1) primary path: embedding + Milvus vector retrieval
    2) fallback path: Mongo query + deterministic lexical scoring
    """

    def __init__(self) -> None:
        self.retrieval_service = RetrievalService()

    @traceable_op(name="retrieval.hybrid_search", run_type="retriever", tags=["retrieval", "hybrid"])
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
        terms = self._build_query_terms(job_description=job_description, job_profile=job_profile)
        keyword_hits = self._search_keyword_candidates(
            job_description=job_description,
            job_profile=job_profile,
            terms=terms,
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
                terms=terms,
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
            for hit in merged_hits:
                hit["retrieval_stage_signal"] = "hybrid"
                hit["retrieval_fallback_triggered"] = False
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
                fallback_hits = keyword_hits[:top_k]
                for hit in fallback_hits:
                    hit["retrieval_stage_signal"] = "keyword_only"
                    hit["retrieval_fallback_triggered"] = True
                return fallback_hits
            raise

    @traceable_op(name="retrieval.keyword_search", run_type="retriever", tags=["retrieval", "mongo"])
    def _search_keyword_candidates(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        terms: list[str],
        top_k: int,
        category: str | None,
        min_experience_years: float | None,
    ) -> list[dict[str, Any]]:
        started_at = time.perf_counter()
        try:
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

    @traceable_op(name="retrieval.merge_fusion_hits", run_type="tool", tags=["retrieval", "fusion"])
    def _merge_fusion_hits(
        self,
        *,
        vector_hits: list[dict[str, Any]],
        keyword_hits: list[dict[str, Any]],
        terms: list[str],
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

            doc = get_collection("candidates").find_one(
                {"candidate_id": candidate_id, "source_dataset": hit.get("source_dataset")},
                {
                    "_id": 0,
                    "candidate_id": 1,
                    "source_dataset": 1,
                    "category": 1,
                    "parsed.skills": 1,
                    "parsed.normalized_skills": 1,
                    "parsed.core_skills": 1,
                    "parsed.expanded_skills": 1,
                    "parsed.experience_years": 1,
                    "parsed.seniority_level": 1,
                },
            )
            parsed = (doc or {}).get("parsed", {})
            parsed = parsed if isinstance(parsed, dict) else {}

            keyword_score = self._compute_keyword_score(parsed=parsed, terms=terms)

            candidate_category = (doc or {}).get("category", hit.get("category"))
            candidate_experience_years = parsed.get("experience_years", hit.get("experience_years"))
            candidate_seniority_level = parsed.get("seniority_level", hit.get("seniority_level"))

            metadata_score = self._metadata_score(
                category=category,
                industry=job_profile.metadata_filters.get("industry") if isinstance(job_profile.metadata_filters, dict) else None,
                min_experience_years=min_experience_years,
                preferred_seniority=job_profile.preferred_seniority,
                candidate_category=candidate_category,
                candidate_experience_years=candidate_experience_years,
                candidate_seniority_level=candidate_seniority_level,
            )
            fusion_score = self._fusion_score(
                vector_score=vector_score,
                keyword_score=keyword_score,
                metadata_score=metadata_score,
            )
            merged[candidate_id] = {
                "candidate_id": candidate_id,
                "source_dataset": hit.get("source_dataset"),
                "category": candidate_category,
                "experience_years": candidate_experience_years,
                "seniority_level": candidate_seniority_level,
                "score": raw_vector_score,
                "vector_score": round(vector_score, 4),
                "keyword_score": round(keyword_score, 4),
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
        seeds: list[str] = []
        for role in job_profile.roles:
            seeds.append(role)
        for signal in sorted(
            job_profile.skill_signals,
            key=lambda s: {"must have": 4, "main focus": 3, "nice to have": 2, "familiarity": 1, "unknown": 0}.get(
                s.strength, 0
            ),
            reverse=True,
        ):
            seeds.append(signal.name)
        for signal in job_profile.capability_signals:
            seeds.append(signal.name)
        for term in [*job_profile.required_skills, *job_profile.related_skills]:
            seeds.append(term)
        for term in job_profile.semantic_query_expansion:
            seeds.append(term)
        for token in self._extract_terms(query_text):
            seeds.append(token)

        normalized = [
            clean_token(seed) or normalize_token(seed)
            for seed in seeds
            if isinstance(seed, str) and seed.strip()
        ]
        normalized = [token for token in normalized if token]
        canonicalized = dedupe_preserve(normalized)

        ontology = get_skill_ontology()
        if ontology is not None:
            canonicalized = dedupe_preserve([ontology.alias_to_canonical.get(token, token) for token in canonicalized])
            target_canonical = set(canonicalized)
            alias_expansion: list[str] = []
            for alias, canonical in ontology.alias_to_canonical.items():
                if canonical in target_canonical and alias not in target_canonical:
                    alias_expansion.append(alias)
                    if len(alias_expansion) >= 12:
                        break
            canonicalized = dedupe_preserve([*canonicalized, *alias_expansion])

        return canonicalized[:32]

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
        return industry_key(industry)

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
            normalized_industry = cls._industry_key(industry)
            industry_terms = INDUSTRY_CATEGORY_MAP.get(normalized_industry, [])
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
        regex = "|".join(re.escape(term) for term in terms[:12])
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
        keyword_score = HybridRetriever._compute_keyword_score(parsed=parsed, terms=terms)
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
    def _compute_keyword_score(*, parsed: dict[str, Any], terms: list[str]) -> float:
        return compute_keyword_score(parsed=parsed, terms=terms)

    @staticmethod
    def _normalize_vector_similarity(raw_similarity: float) -> float:
        return normalize_vector_similarity(raw_similarity)

    @staticmethod
    def _fusion_score(*, vector_score: float, keyword_score: float, metadata_score: float) -> float:
        return fusion_score(
            vector_score=vector_score,
            keyword_score=keyword_score,
            metadata_score=metadata_score,
            vector_weight=settings.retrieval_vector_weight,
            keyword_weight=settings.retrieval_keyword_weight,
            metadata_weight=settings.retrieval_metadata_weight,
        )

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
        return metadata_score(
            category=category,
            industry=industry,
            min_experience_years=min_experience_years,
            preferred_seniority=preferred_seniority,
            candidate_category=candidate_category,
            candidate_experience_years=candidate_experience_years,
            candidate_seniority_level=candidate_seniority_level,
        )

    @traceable_op(name="retrieval.search_within_candidate", run_type="tool")
    def search_within_candidate(self, candidate_id: str, query: str) -> str:
        """Search for specific information within a candidate's structured parsed data."""
        doc = get_collection("candidates").find_one(
            {"candidate_id": candidate_id},
            {
                "parsed.experience_items": 1,
                "parsed.capability_phrases": 1,
                "parsed.abilities": 1,
                "parsed.summary": 1,
                "_id": 0
            }
        )
        if not doc:
            return f"Candidate {candidate_id} not found."
            
        parsed = doc.get("parsed") or {}
        query_terms = [t.lower() for t in re.findall(r'\b\w+\b', query) if len(t) > 2]
        
        if not query_terms:
            return "Query is empty or contains only short stop words."
            
        evidence = []
        
        phrases = parsed.get("capability_phrases", []) + parsed.get("abilities", [])
        matched_phrases = [p for p in phrases if any(term in p.lower() for term in query_terms)]
        if matched_phrases:
            evidence.append("[Capabilities] Related capabilities / skills")
            for p in matched_phrases[:5]:
                evidence.append(f"- {p}")

        summary = parsed.get("summary", "")
        if summary:
            summary_sentences = [s.strip() for s in re.split(r'(?<=[.!?\n])\s+', summary) if s.strip()]
            matched_summary = [s for s in summary_sentences if any(term in s.lower() for term in query_terms)]
            if matched_summary:
                evidence.append("\n[Summary]")
                for s in matched_summary[:3]:
                    evidence.append(f"- {s}")

        items = parsed.get("experience_items") or []
        for item in items:
            title = item.get("title") or "Unknown Role"
            company = item.get("company") or "Unknown Company"
            desc = item.get("description", "")
            
            role_matched = any(term in title.lower() or term in company.lower() for term in query_terms)
            
            desc_sentences = [s.strip() for s in re.split(r'(?<=[.!?\n])\s+', desc) if s.strip()]
            matched_desc = [s for s in desc_sentences if any(term in s.lower() for term in query_terms)]
            
            if role_matched or matched_desc:
                evidence.append(f"\n[Experience] {title} at {company}")
                for s in matched_desc[:5]:
                    evidence.append(f"- {s}")
                    
        if not evidence:
            return f"No evidence found in candidate's resume for query: '{query}'."
            
        return "\n".join(evidence)
