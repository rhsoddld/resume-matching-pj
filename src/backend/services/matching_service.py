from __future__ import annotations

from backend.core.providers import get_skill_ontology
from backend.schemas.job import JobMatchCandidate
from backend.services.candidate_enricher import enrich_hits
from backend.services.job_profile_extractor import build_job_profile
from backend.services.match_result_builder import build_match_candidate
from backend.services.retrieval_service import RetrievalService


class MatchingService:
    def __init__(self) -> None:
        self.retrieval_service = RetrievalService()

    def match_jobs(
        self,
        *,
        job_description: str,
        top_k: int = 10,
        category: str | None = None,
        min_experience_years: float | None = None,
    ) -> list[JobMatchCandidate]:
        ontology = get_skill_ontology()
        job_profile = build_job_profile(job_description=job_description, ontology=ontology)

        hits = self.retrieval_service.search_candidates(
            job_description=job_description,
            top_k=top_k,
            category=category,
        )
        enriched_hits = enrich_hits(hits, min_experience_years=min_experience_years)

        results = [
            build_match_candidate(hit=hit, candidate_doc=candidate_doc, job_profile=job_profile, category=category)
            for hit, candidate_doc in enriched_hits
        ]
        results.sort(key=lambda item: item.score, reverse=True)
        return results


matching_service = MatchingService()
