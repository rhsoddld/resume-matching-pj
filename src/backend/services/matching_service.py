from __future__ import annotations

from backend.core.providers import get_skill_ontology
from backend.repositories.hybrid_retriever import HybridRetriever
from backend.schemas.job import JobMatchCandidate
from backend.services.agent_orchestration_service import agent_orchestration_service
from backend.services.candidate_enricher import enrich_hits
from backend.services.job_profile_extractor import build_job_profile
from backend.services.match_result_builder import build_match_candidate


class MatchingService:
    def __init__(self) -> None:
        self.hybrid_retriever = HybridRetriever()

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

        hits = self.hybrid_retriever.search_candidates(
            job_description=job_description,
            top_k=top_k,
            category=category,
        )
        enriched_hits = enrich_hits(hits, min_experience_years=min_experience_years)

        results: list[JobMatchCandidate] = []
        for hit, candidate_doc in enriched_hits:
            agent_result = agent_orchestration_service.run_for_candidate(
                job_description=job_description,
                job_profile=job_profile,
                hit=hit,
                candidate_doc=candidate_doc,
                category_filter=category,
            )
            results.append(
                build_match_candidate(
                    hit=hit,
                    candidate_doc=candidate_doc,
                    job_profile=job_profile,
                    category=category,
                    agent_result=agent_result,
                )
            )
        results.sort(key=lambda item: item.score, reverse=True)
        return results


matching_service = MatchingService()
