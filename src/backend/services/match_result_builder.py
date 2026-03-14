from __future__ import annotations

from typing import Any

from agents.orchestrator import CandidateAgentResult
from backend.schemas.job import JobMatchCandidate
from backend.services.job_profile_extractor import JobProfile
from backend.services.scoring_service import (
    compute_deterministic_match_score,
    compute_final_ranking_score,
    compute_skill_overlap,
)


def _extract_relevant_experience(parsed: dict[str, Any], *, experience_years: float | None) -> list[str]:
    items = parsed.get("experience_items") or []
    highlights: list[str] = []
    if isinstance(items, list):
        for item in items[:3]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            company = str(item.get("company") or "").strip()
            if title and company:
                highlights.append(f"{title} at {company}")
            elif title:
                highlights.append(title)
            elif company:
                highlights.append(company)
    if not highlights and isinstance(experience_years, (int, float)):
        highlights.append(f"{round(float(experience_years), 1)} years of relevant experience")
    return highlights


def _build_weighting_summary(agent_result: CandidateAgentResult | None) -> str | None:
    if agent_result is None or agent_result.weight_negotiation is None:
        return None
    recruiter = agent_result.weight_negotiation.recruiter
    hiring = agent_result.weight_negotiation.hiring_manager
    final = agent_result.weight_negotiation.final
    return (
        "Recruiter focus "
        f"(S:{recruiter.skill:.2f}, E:{recruiter.experience:.2f}, T:{recruiter.technical:.2f}, C:{recruiter.culture:.2f}) "
        "| Hiring manager focus "
        f"(S:{hiring.skill:.2f}, E:{hiring.experience:.2f}, T:{hiring.technical:.2f}, C:{hiring.culture:.2f}) "
        "| Final negotiated "
        f"(S:{final.skill:.2f}, E:{final.experience:.2f}, T:{final.technical:.2f}, C:{final.culture:.2f})"
    )


def _compute_must_have_penalty(
    *,
    job_profile: JobProfile,
    parsed: dict[str, Any],
) -> tuple[float, float]:
    must_have_terms = [
        signal.name.strip().lower()
        for signal in job_profile.skill_signals
        if signal.strength == "must have" and signal.name.strip()
    ]
    if not must_have_terms:
        return 1.0, 0.0

    candidate_terms = set()
    for key in ("skills", "normalized_skills", "core_skills", "expanded_skills"):
        values = parsed.get(key) or []
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value.strip():
                candidate_terms.add(value.strip().lower())

    matched = sum(1 for term in must_have_terms if term in candidate_terms)
    match_rate = matched / float(len(must_have_terms))
    penalty = min(0.25, (1.0 - match_rate) * 0.25)
    return round(match_rate, 4), round(penalty, 4)


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
    agent_weighted_score = agent_result.ranking_output.final_score if agent_result is not None else None
    relevant_experience = _extract_relevant_experience(parsed, experience_years=hit.get("experience_years"))
    possible_gaps = (
        list(agent_result.skill_output.missing_skills[:5])
        if agent_result is not None and agent_result.skill_output.missing_skills
        else []
    )
    weighting_summary = _build_weighting_summary(agent_result)
    must_have_match_rate, must_have_penalty = _compute_must_have_penalty(job_profile=job_profile, parsed=parsed)
    rank_score = compute_final_ranking_score(
        deterministic_score=float(final_score),
        agent_weighted_score=agent_weighted_score,
    )
    rank_score = max(0.0, min(1.0, rank_score * (1.0 - must_have_penalty)))

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
        score=round(float(rank_score), 4),
        vector_score=round(float(hit.get("vector_score", hit["score"])), 4),
        skill_overlap=round(float(skill_overlap_score), 4),
        score_detail={
            "semantic_similarity": round(float(final_score_detail["semantic_similarity"]), 4),
            "experience_fit": round(float(final_score_detail["experience_fit"]), 4),
            "seniority_fit": round(float(final_score_detail["seniority_fit"]), 4),
            "category_fit": round(float(final_score_detail["category_fit"]), 4),
            "retrieval_fusion": round(float(hit.get("fusion_score")), 4) if hit.get("fusion_score") is not None else None,
            "retrieval_keyword": round(float(hit.get("keyword_score")), 4) if hit.get("keyword_score") is not None else None,
            "retrieval_metadata": round(float(hit.get("metadata_score")), 4) if hit.get("metadata_score") is not None else None,
            "must_have_match_rate": must_have_match_rate,
            "must_have_penalty": must_have_penalty,
            "agent_weighted": round(float(agent_weighted_score), 4) if agent_weighted_score is not None else None,
            "rank_policy": (
                "hybrid(deterministic:0.55,agent:0.45,must-have-penalty:max0.25)"
                if agent_weighted_score is not None
                else "deterministic-only(must-have-penalty:max0.25)"
            ),
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
                "weights": agent_result.ranking_input.weights.model_dump(),
                "weight_negotiation": (
                    agent_result.weight_negotiation.model_dump()
                    if agent_result.weight_negotiation is not None
                    else None
                ),
            }
            if agent_result is not None
            else {}
        ),
        agent_explanation=agent_result.ranking_output.explanation if agent_result is not None else None,
        relevant_experience=relevant_experience,
        possible_gaps=possible_gaps,
        weighting_summary=weighting_summary,
    )
