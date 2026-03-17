from __future__ import annotations

from typing import Iterable, Mapping
import re

from backend.services.scoring_policies import DEFAULT_DETERMINISTIC_POLICY_VERSION, get_deterministic_scoring_policy


_WHITESPACE = re.compile(r"\s+")
_SKILL_TOKEN_RE = re.compile(r"[a-z0-9+#.-]+")
_TOKEN_STOPWORDS = {"and", "or", "with", "for", "the", "a", "an", "to", "of", "in"}
# JD 스킬이 많을 때 분모 캡 (스킬 개수 제한으로 과도한 페널티 완화)
_MAX_SKILLS_DENOMINATOR = 10
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


def _skill_tokens(term: str) -> set[str]:
    tokens = {token for token in _SKILL_TOKEN_RE.findall(term.lower()) if token and token not in _TOKEN_STOPWORDS}
    return tokens


def _term_match_score(candidate_set: set[str], target_term: str) -> float:
    if not target_term:
        return 0.0
    if target_term in candidate_set:
        return 1.0

    target_tokens = _skill_tokens(target_term)
    if not target_tokens:
        return 0.0

    best = 0.0
    for candidate_term in candidate_set:
        if not candidate_term:
            continue
        candidate_tokens = _skill_tokens(candidate_term)
        if not candidate_tokens:
            continue

        overlap = len(target_tokens.intersection(candidate_tokens)) / float(len(target_tokens))
        if overlap <= 0.0:
            continue

        # Reward cases like "b2b sales support" vs "sales support".
        if target_term in candidate_term or candidate_term in target_term:
            overlap = max(overlap, min(1.0, overlap + 0.2))

        best = max(best, overlap)
        if best >= 1.0:
            return 1.0
    return best


def _soft_overlap_ratio(candidate_set: set[str], target_set: set[str]) -> float:
    if not target_set:
        return 0.0
    total = 0.0
    for target_term in target_set:
        total += _term_match_score(candidate_set, target_term)
    return total / float(len(target_set))


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

    # Keep slight separation between exact-fit and clearly overqualified profiles,
    # but avoid harshly punishing senior candidates who still cover the JD well.
    over_penalty = min(0.15, (ratio - 1.0) * 0.08)
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
    policy_version: str = DEFAULT_DETERMINISTIC_POLICY_VERSION,
) -> tuple[float, dict[str, float]]:
    policy = get_deterministic_scoring_policy(policy_version)
    semantic_similarity = _normalize_similarity(raw_similarity)
    experience_fit = _experience_fit(candidate_experience_years, required_experience_years)
    seniority_fit = _seniority_fit(candidate_seniority, preferred_seniority)
    category_fit = float(policy.category_bonus) if category_matched else 0.0

    final_score = (
        (float(policy.semantic_weight) * semantic_similarity)
        + (float(policy.skill_overlap_weight) * _clip_01(skill_overlap))
        + (float(policy.experience_weight) * experience_fit)
        + (float(policy.seniority_weight) * seniority_fit)
        + category_fit
    )
    final_score = _clip_01(final_score)

    detail = {
        "policy_version": policy.version,
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
    deterministic_weight: float = 0.30,
    agent_weight: float = 0.70,
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

    required_list = list(job.get("required_skills") or [])[:_MAX_SKILLS_DENOMINATOR]
    expanded_list = list(job.get("expanded_skills") or [])
    job_required = _to_skill_set(required_list)
    # expanded_target도 상위 N개로 제한 (required 먼저, 그다음 expanded)
    seen: set[str] = set()
    expanded_target_list: list[str] = []
    for val in required_list + expanded_list:
        token = _normalize_skill_token(val)
        if token and token not in seen:
            seen.add(token)
            expanded_target_list.append(token)
            if len(expanded_target_list) >= _MAX_SKILLS_DENOMINATOR:
                break
    expanded_target = set(expanded_target_list) if expanded_target_list else set(job_required)

    core_overlap = _soft_overlap_ratio(candidate_core, job_required)
    expanded_overlap = _soft_overlap_ratio(candidate_expanded, expanded_target)
    normalized_overlap = _soft_overlap_ratio(candidate_normalized, job_required)

    # Skill Coverage: core 비중 완화, normalized/expanded 균형 (과도한 페널티 방지)
    # core 없을 때도 동일한 완화 적용 (core_skills 비어 있는 이력서 많음)
    if candidate_core:
        score = (0.45 * core_overlap) + (0.35 * expanded_overlap) + (0.2 * normalized_overlap)
    else:
        score = (0.5 * normalized_overlap) + (0.5 * expanded_overlap)

    detail = {
        "core_overlap": core_overlap,
        "expanded_overlap": expanded_overlap,
        "normalized_overlap": normalized_overlap,
    }
    return score, detail
