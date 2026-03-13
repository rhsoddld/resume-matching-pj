from __future__ import annotations

from typing import Any

from agents.orchestrator import CandidateAgentResult
from backend.schemas.job import JobMatchCandidate
from backend.services.job_profile_extractor import JobProfile
from backend.services.scoring_service import compute_deterministic_match_score, compute_skill_overlap


def build_match_candidate(
    *,
    hit: dict[str, Any],
    candidate_doc: dict[str, Any],
    job_profile: JobProfile,
    category: str | None,
    agent_result: CandidateAgentResult | None = None,
) -> JobMatchCandidate:
    parsed = candidate_doc.get("parsed", {})
    parsed = parsed if isinstance(parsed, dict) else {}

    job_skill_profile = {
        "required_skills": job_profile.required_skills,
        "expanded_skills": job_profile.expanded_skills,
    }
    skill_overlap_score, skill_overlap_detail = compute_skill_overlap(candidate_doc, job_skill_profile)
    final_score, final_score_detail = compute_deterministic_match_score(
        raw_similarity=float(hit["score"]),
        skill_overlap=skill_overlap_score,
        candidate_experience_years=hit.get("experience_years"),
        required_experience_years=job_profile.required_experience_years,
        candidate_seniority=hit.get("seniority_level"),
        preferred_seniority=job_profile.preferred_seniority,
        category_matched=bool(category and hit.get("category") == category),
    )

    return JobMatchCandidate(
        candidate_id=hit["candidate_id"],
        category=hit.get("category"),
        summary=parsed.get("summary"),
        skills=parsed.get("skills", []),
        normalized_skills=parsed.get("normalized_skills", []),
        core_skills=parsed.get("core_skills", []),
        expanded_skills=parsed.get("expanded_skills", []),
        experience_years=hit.get("experience_years"),
        seniority_level=hit.get("seniority_level"),
        score=round(float(final_score), 4),
        vector_score=round(float(hit["score"]), 4),
        skill_overlap=round(float(skill_overlap_score), 4),
        score_detail={
            "semantic_similarity": round(float(final_score_detail["semantic_similarity"]), 4),
            "experience_fit": round(float(final_score_detail["experience_fit"]), 4),
            "seniority_fit": round(float(final_score_detail["seniority_fit"]), 4),
            "category_fit": round(float(final_score_detail["category_fit"]), 4),
        },
        skill_overlap_detail={
            "core_overlap": round(float(skill_overlap_detail["core_overlap"]), 4),
            "expanded_overlap": round(float(skill_overlap_detail["expanded_overlap"]), 4),
            "normalized_overlap": round(float(skill_overlap_detail["normalized_overlap"]), 4),
        },
        agent_scores=(
            {
                "skill": agent_result.skill_output.score,
                "experience": agent_result.experience_output.score,
                "technical": agent_result.technical_output.score,
                "culture": agent_result.culture_output.score,
                "weighted": agent_result.ranking_output.final_score,
            }
            if agent_result is not None
            else {}
        ),
        agent_explanation=agent_result.ranking_output.explanation if agent_result is not None else None,
    )
