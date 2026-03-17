from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.agents.contracts.orchestrator import CandidateAgentResult
from backend.core.providers import get_skill_ontology
from backend.core.settings import settings
from backend.schemas.job import JobMatchCandidate
from backend.services.job_profile_extractor import JobProfile
from backend.services.scoring_service import (
    compute_deterministic_match_score,
    compute_final_ranking_score,
    compute_skill_overlap,
)
from backend.services.scoring_policies import DEFAULT_DETERMINISTIC_POLICY_VERSION, get_deterministic_scoring_policy


def _normalized_token_list(values: list[Any], *, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        token = value.strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= limit:
            break
    return out


def _build_deterministic_explanation(
    *,
    job_profile: JobProfile,
    parsed: dict[str, Any],
    skill_overlap_score: float,
    final_score_detail: dict[str, float],
    must_have_match_rate: float,
) -> str:
    required_skills = _normalized_token_list(list(job_profile.required_skills or []), limit=6)
    candidate_skill_tokens = _normalized_token_list(
        list(parsed.get("normalized_skills") or []) + list(parsed.get("skills") or []),
        limit=10,
    )
    required_set = set(required_skills)
    candidate_set = set(candidate_skill_tokens)
    matched = [token for token in required_skills if token in candidate_set][:6]
    missing = [token for token in required_skills if token not in candidate_set][:4]
    supporting = [token for token in candidate_skill_tokens if token not in matched and token not in missing][:4]

    matched_text = ", ".join(matched or required_skills[:4] or ["none explicit"])
    supporting_text = ", ".join(supporting or candidate_skill_tokens[:4] or ["none explicit"])
    missing_text = ", ".join(missing or ["none explicit"])

    return (
        f"Matched required skills: {matched_text}. "
        f"Candidate evidence tokens: {supporting_text}; missing or weaker skills: {missing_text}. "
        f"Deterministic signals: semantic={float(final_score_detail['semantic_similarity']):.2f}, "
        f"skill={float(skill_overlap_score):.2f}, experience={float(final_score_detail['experience_fit']):.2f}, "
        f"seniority={float(final_score_detail['seniority_fit']):.2f}; "
        f"must-have match={float(must_have_match_rate):.2f}."
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


def _parse_date_token(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    token = value.strip().lower()
    if token in {"present", "current", "now"}:
        return datetime.utcnow()
    for fmt in ("%Y-%m", "%Y/%m", "%Y"):
        try:
            return datetime.strptime(token, fmt)
        except ValueError:
            continue
    return None


def _build_career_trajectory(parsed: dict[str, Any], *, seniority_level: str | None, experience_years: float | None) -> dict[str, Any]:
    items = parsed.get("experience_items") or []
    if not isinstance(items, list) or not items:
        return {
            "has_trajectory": False,
            "seniority_level": seniority_level,
            "total_experience_years": experience_years,
            "progression": "insufficient-data",
            "moves": [],
        }

    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        company = str(item.get("company") or "").strip()
        start = _parse_date_token(item.get("start_date"))
        end = _parse_date_token(item.get("end_date"))
        normalized.append(
            {
                "title": title or None,
                "company": company or None,
                "start_date": item.get("start_date"),
                "end_date": item.get("end_date"),
                "start_dt": start,
                "end_dt": end,
            }
        )

    normalized.sort(key=lambda row: row.get("start_dt") or datetime.min)
    moves: list[dict[str, Any]] = []
    for idx, row in enumerate(normalized):
        if idx == 0:
            continue
        prev = normalized[idx - 1]
        if row.get("title") == prev.get("title") and row.get("company") == prev.get("company"):
            continue
        moves.append(
            {
                "from_title": prev.get("title"),
                "to_title": row.get("title"),
                "from_company": prev.get("company"),
                "to_company": row.get("company"),
                "at": row.get("start_date"),
            }
        )

    first = normalized[0]
    last = normalized[-1]
    progression = "stable"
    if len(moves) >= 2:
        progression = "growth"
    if moves and any(move.get("from_company") != move.get("to_company") for move in moves):
        progression = "transition"

    return {
        "has_trajectory": True,
        "seniority_level": seniority_level,
        "total_experience_years": experience_years,
        "first_role": {"title": first.get("title"), "company": first.get("company"), "start_date": first.get("start_date")},
        "latest_role": {"title": last.get("title"), "company": last.get("company"), "start_date": last.get("start_date"), "end_date": last.get("end_date")},
        "progression": progression,
        "moves": moves[:6],
    }


def _compute_adjacent_skill_score(*, job_profile: JobProfile, parsed: dict[str, Any]) -> tuple[float, list[str]]:
    related = {skill.strip().lower() for skill in (job_profile.related_skills or []) if isinstance(skill, str) and skill.strip()}
    required = {skill.strip().lower() for skill in (job_profile.required_skills or []) if isinstance(skill, str) and skill.strip()}
    target_adjacent = related.difference(required)
    if not target_adjacent:
        return 0.0, []

    candidate_terms: set[str] = set()
    for key in ("skills", "normalized_skills", "core_skills", "expanded_skills"):
        values = parsed.get(key) or []
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value.strip():
                candidate_terms.add(value.strip().lower())

    ontology = get_skill_ontology()
    if ontology is not None:
        score, matches = ontology.adjacent_match_score(
            job_related_skills=target_adjacent,
            candidate_skills=candidate_terms,
            limit=8,
        )
        return score, matches

    matches = sorted(target_adjacent.intersection(candidate_terms))
    score = round(len(matches) / float(len(target_adjacent)), 4)
    return score, matches[:8]


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


def _compute_parsing_score(parsed: dict[str, Any]) -> float:
    score = 0.0
    if parsed.get("summary"):
        score += 0.25
    if len(parsed.get("normalized_skills") or []) >= 3:
        score += 0.25
    if parsed.get("experience_years") is not None:
        score += 0.2
    if len(parsed.get("experience_items") or []) > 0:
        score += 0.15
    if len(parsed.get("education") or []) > 0:
        score += 0.15
    return round(max(0.0, min(1.0, score)), 4)


def _compute_must_have_penalty(
    *,
    job_profile: JobProfile,
    parsed: dict[str, Any],
    adjacent_skill_score: float = 0.0,
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
    adjacent_credit = max(0.0, min(1.0, float(adjacent_skill_score))) * 0.5
    effective_match_rate = min(1.0, match_rate + ((1.0 - match_rate) * adjacent_credit))
    penalty = min(0.12, (1.0 - effective_match_rate) * 0.12)
    return round(match_rate, 4), round(penalty, 4)


def build_match_candidate(
    *,
    hit: dict[str, Any],
    candidate_doc: dict[str, Any],
    job_profile: JobProfile,
    category: str | None,
    agent_result: CandidateAgentResult | None = None,
    agent_evaluation_applied: bool | None = None,
    agent_evaluation_reason: str | None = None,
) -> JobMatchCandidate:
    parsed = candidate_doc.get("parsed", {})
    parsed = parsed if isinstance(parsed, dict) else {}

    job_skill_profile = {
        "required_skills": job_profile.required_skills,
        "expanded_skills": job_profile.expanded_skills,
    }
    skill_overlap_score, skill_overlap_detail = compute_skill_overlap(candidate_doc, job_skill_profile)
    # If agent evaluation is available, blend deterministic overlap with the agent's skill score.
    # This avoids relying solely on early-stage extraction heuristics when richer evidence is present.
    if agent_result is not None and getattr(agent_result, "skill_output", None) is not None:
        agent_skill = getattr(agent_result.skill_output, "score", None)
        if isinstance(agent_skill, (int, float)):
            skill_overlap_score = max(0.0, min(1.0, 0.5 * float(skill_overlap_score) + 0.5 * float(agent_skill)))
    final_score, final_score_detail = compute_deterministic_match_score(
        raw_similarity=float(hit["score"]),
        skill_overlap=skill_overlap_score,
        candidate_experience_years=hit.get("experience_years"),
        required_experience_years=job_profile.required_experience_years,
        candidate_seniority=hit.get("seniority_level"),
        preferred_seniority=job_profile.preferred_seniority,
        category_matched=bool(category and hit.get("category") == category),
        policy_version=DEFAULT_DETERMINISTIC_POLICY_VERSION,
    )
    agent_weighted_score = agent_result.ranking_output.final_score if agent_result is not None else None
    relevant_experience = _extract_relevant_experience(parsed, experience_years=hit.get("experience_years"))
    possible_gaps = (
        list(agent_result.skill_output.missing_skills[:5])
        if agent_result is not None and agent_result.skill_output.missing_skills
        else []
    )
    weighting_summary = _build_weighting_summary(agent_result)
    adjacent_skill_score, adjacent_skill_matches = _compute_adjacent_skill_score(job_profile=job_profile, parsed=parsed)
    must_have_match_rate, must_have_penalty = _compute_must_have_penalty(
        job_profile=job_profile,
        parsed=parsed,
        adjacent_skill_score=adjacent_skill_score,
    )
    career_trajectory = _build_career_trajectory(
        parsed,
        seniority_level=hit.get("seniority_level"),
        experience_years=hit.get("experience_years"),
    )
    rank_score = compute_final_ranking_score(
        deterministic_score=float(final_score),
        agent_weighted_score=agent_weighted_score,
        deterministic_weight=float(settings.rank_deterministic_weight),
        agent_weight=float(settings.rank_agent_weight),
    )
    rank_score = max(0.0, min(1.0, rank_score * (1.0 - must_have_penalty)))
    parsing_score = _compute_parsing_score(parsed)

    evaluation_applied = bool(agent_result is not None) if agent_evaluation_applied is None else bool(agent_evaluation_applied)

    if agent_result is not None:
        confidence_scores = {
            "parsing": parsing_score,
            "skill": agent_result.skill_output.score,
            "experience": agent_result.experience_output.score,
            "technical": agent_result.technical_output.score,
            "culture": agent_result.culture_output.score,
        }
        evidence_map = {
            "parsing": ["Structured resume sections available." if parsing_score >= 0.6 else "Partial parsing coverage detected."],
            "skill": list(agent_result.skill_output.evidence[:4]),
            "experience": list(agent_result.experience_output.evidence[:4]),
            "technical": list(agent_result.technical_output.evidence[:4]),
            "culture": list(agent_result.culture_output.evidence[:4]),
        }
        agent_scores: dict[str, Any] = {
            **confidence_scores,
            "weighted": agent_result.ranking_output.final_score,
            "runtime_mode": agent_result.runtime_mode or "unknown",
            "runtime_fallback_used": (agent_result.runtime_mode or "") == "heuristic",
            "runtime_reason": agent_result.runtime_reason or "",
            "agent_evaluation_applied": True,
            "weights": agent_result.ranking_input.weights.model_dump(),
            "weight_negotiation": (
                agent_result.weight_negotiation.model_dump()
                if agent_result.weight_negotiation is not None
                else None
            ),
            "confidence": confidence_scores,
            "evidence": evidence_map,
        }
    else:
        deterministic_explanation = _build_deterministic_explanation(
            job_profile=job_profile,
            parsed=parsed,
            skill_overlap_score=float(skill_overlap_score),
            final_score_detail=final_score_detail,
            must_have_match_rate=must_have_match_rate,
        )
        agent_scores = {
            "parsing": parsing_score,
            "skill": round(float(skill_overlap_score), 4),
            "experience": round(float(final_score_detail["experience_fit"]), 4),
            "technical": round(float(final_score_detail["semantic_similarity"]), 4),
            "weighted": round(float(rank_score), 4),
            "runtime_mode": "deterministic_only",
            "runtime_reason": agent_evaluation_reason or "outside_agent_eval_scope",
            "agent_evaluation_applied": evaluation_applied,
            "confidence": {
                "parsing": parsing_score,
                "skill": round(float(skill_overlap_score), 4),
                "experience": round(float(final_score_detail["experience_fit"]), 4),
                "technical": round(float(final_score_detail["semantic_similarity"]), 4),
            },
            "evidence": {
                "parsing": ["No agent outputs available; deterministic-only match."],
                "skill": [f"required_skills={', '.join(job_profile.required_skills[:4]) or 'none'}"],
                "experience": [f"experience_fit={float(final_score_detail['experience_fit']):.2f}"],
                "technical": [f"semantic_similarity={float(final_score_detail['semantic_similarity']):.2f}"],
            },
        }
        agent_explanation = deterministic_explanation
    if agent_result is not None:
        agent_explanation = agent_result.ranking_output.explanation

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
            "adjacent_skill_score": adjacent_skill_score,
            "agent_weighted": round(float(agent_weighted_score), 4) if agent_weighted_score is not None else None,
            "rank_policy": (
                (
                    "hybrid("
                    f"deterministic:{float(settings.rank_deterministic_weight):.2f},"
                    f"agent:{float(settings.rank_agent_weight):.2f},"
                    f"det_policy:{get_deterministic_scoring_policy(DEFAULT_DETERMINISTIC_POLICY_VERSION).version},"
                    "must-have-penalty:max0.12,adjacent-credit:0.50)"
                )
                if agent_weighted_score is not None
                else (
                    "deterministic-only("
                    f"det_policy:{get_deterministic_scoring_policy(DEFAULT_DETERMINISTIC_POLICY_VERSION).version},"
                    "must-have-penalty:max0.12,adjacent-credit:0.50)"
                )
            ),
        },
        skill_overlap_detail={
            "core_overlap": round(float(skill_overlap_detail["core_overlap"]), 4),
            "expanded_overlap": round(float(skill_overlap_detail["expanded_overlap"]), 4),
            "normalized_overlap": round(float(skill_overlap_detail["normalized_overlap"]), 4),
        },
        agent_scores=agent_scores,
        agent_explanation=agent_explanation,
        relevant_experience=relevant_experience,
        career_trajectory=(
            agent_result.experience_output.career_trajectory
            if agent_result is not None and isinstance(agent_result.experience_output.career_trajectory, dict)
            else career_trajectory
        ),
        adjacent_skill_matches=adjacent_skill_matches,
        possible_gaps=possible_gaps,
        weighting_summary=weighting_summary,
    )
