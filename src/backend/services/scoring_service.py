from __future__ import annotations

from typing import Iterable, Mapping
import re


_WHITESPACE = re.compile(r"\s+")
_SENIORITY_LEVELS = {
    "intern": 0,
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "staff": 5,
    "principal": 6,
}


def _normalize_skill_token(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip().lower()
    if not token:
        return None
    token = token.replace("&", " and ")
    token = _WHITESPACE.sub(" ", token).strip(" ,;:/|")
    return token or None


def _to_skill_set(values: Iterable[object] | None) -> set[str]:
    if not values:
        return set()
    out: set[str] = set()
    for value in values:
        token = _normalize_skill_token(value)
        if token:
            out.add(token)
    return out


def _overlap_ratio(candidate_set: set[str], target_set: set[str]) -> float:
    if not target_set:
        return 0.0
    return len(candidate_set.intersection(target_set)) / float(len(target_set))


def _clip_01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _normalize_similarity(raw_similarity: float) -> float:
    # Milvus IP scores are treated as cosine-like in [-1, 1].
    normalized = (raw_similarity + 1.0) / 2.0
    return _clip_01(normalized)


def _experience_fit(candidate_years: float | None, required_years: float | None) -> float:
    if required_years is None or required_years <= 0:
        return 0.5
    if candidate_years is None:
        return 0.0
    ratio = candidate_years / required_years
    if ratio <= 1.0:
        return _clip_01(ratio)

    # Prevent over-saturating at 1.0 for highly overqualified profiles.
    over_penalty = min(0.35, (ratio - 1.0) * 0.20)
    return _clip_01(1.0 - over_penalty)


def _seniority_fit(candidate_level: str | None, preferred_level: str | None) -> float:
    if not preferred_level:
        return 0.5
    if not candidate_level:
        return 0.0

    candidate_rank = _SENIORITY_LEVELS.get(candidate_level.strip().lower())
    preferred_rank = _SENIORITY_LEVELS.get(preferred_level.strip().lower())
    if candidate_rank is None or preferred_rank is None:
        return 0.5

    max_distance = float(max(_SENIORITY_LEVELS.values()))
    distance = abs(candidate_rank - preferred_rank)
    return _clip_01(1.0 - (distance / max_distance))


def compute_deterministic_match_score(
    *,
    raw_similarity: float,
    skill_overlap: float,
    candidate_experience_years: float | None,
    required_experience_years: float | None,
    candidate_seniority: str | None,
    preferred_seniority: str | None,
    category_matched: bool,
) -> tuple[float, dict[str, float]]:
    semantic_similarity = _normalize_similarity(raw_similarity)
    experience_fit = _experience_fit(candidate_experience_years, required_experience_years)
    seniority_fit = _seniority_fit(candidate_seniority, preferred_seniority)
    category_fit = 0.03 if category_matched else 0.0

    final_score = (
        (0.42 * semantic_similarity)
        + (0.33 * _clip_01(skill_overlap))
        + (0.18 * experience_fit)
        + (0.07 * seniority_fit)
        + category_fit
    )
    final_score = _clip_01(final_score)

    detail = {
        "semantic_similarity": semantic_similarity,
        "skill_overlap": _clip_01(skill_overlap),
        "experience_fit": experience_fit,
        "seniority_fit": seniority_fit,
        "category_fit": category_fit,
    }
    return final_score, detail


def compute_final_ranking_score(
    *,
    deterministic_score: float,
    agent_weighted_score: float | None,
    deterministic_weight: float = 0.55,
    agent_weight: float = 0.45,
) -> float:
    if agent_weighted_score is None:
        return _clip_01(deterministic_score)

    weighted = (deterministic_score * deterministic_weight) + (agent_weighted_score * agent_weight)
    return _clip_01(weighted)


def compute_skill_overlap(candidate: Mapping[str, object], job: Mapping[str, object]) -> tuple[float, dict[str, float]]:
    """
    Ontology-aware skill overlap scoring.

    Priority:
    1) core skill overlap
    2) expanded taxonomy overlap
    3) normalized skill fallback
    """
    parsed = candidate.get("parsed", {})
    parsed = parsed if isinstance(parsed, Mapping) else {}

    candidate_core = _to_skill_set(parsed.get("core_skills"))
    candidate_expanded = _to_skill_set(parsed.get("expanded_skills"))
    candidate_normalized = _to_skill_set(parsed.get("normalized_skills"))

    job_required = _to_skill_set(job.get("required_skills"))
    job_expanded = _to_skill_set(job.get("expanded_skills"))
    expanded_target = set(job_required)
    expanded_target.update(job_expanded)
    if not expanded_target:
        expanded_target = set(job_required)

    core_overlap = _overlap_ratio(candidate_core, job_required)
    expanded_overlap = _overlap_ratio(candidate_expanded, expanded_target)
    normalized_overlap = _overlap_ratio(candidate_normalized, job_required)

    if candidate_core:
        score = (0.6 * core_overlap) + (0.3 * expanded_overlap) + (0.1 * normalized_overlap)
    else:
        score = (0.7 * normalized_overlap) + (0.3 * expanded_overlap)

    detail = {
        "core_overlap": core_overlap,
        "expanded_overlap": expanded_overlap,
        "normalized_overlap": normalized_overlap,
    }
    return score, detail
