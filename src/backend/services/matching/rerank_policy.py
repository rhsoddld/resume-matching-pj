from __future__ import annotations

from backend.core.settings import settings
from backend.services.job_profile_extractor import JobProfile


def is_rerank_runtime_enabled() -> tuple[bool, str]:
    if not settings.rerank_enabled:
        return False, "disabled_by_config"
    if settings.rerank_require_ab_proof and not settings.rerank_ab_proven:
        return False, "blocked_until_ab_proven"
    return True, "enabled"


def resolve_rerank_pool_n(top_k: int) -> int:
    max_pool = max(1, int(settings.rerank_gate_max_top_n))
    requested = max(1, int(settings.rerank_top_n))
    return max(top_k, min(requested, max_pool))


def resolve_retrieval_top_n(top_k: int) -> int:
    enabled, _ = is_rerank_runtime_enabled()
    if not enabled:
        return top_k
    rerank_pool_n = resolve_rerank_pool_n(top_k)
    return max(top_k, rerank_pool_n)


def resolve_agent_eval_top_n(top_k: int) -> int:
    requested = max(0, int(settings.agent_eval_top_n))
    capped = min(top_k, requested)
    if not settings.token_budget_enabled:
        return capped
    budget = max(0, int(settings.token_budget_per_request))
    cost_per_candidate = max(1, int(settings.token_estimated_per_agent_call))
    available_for_agents = int(budget * 0.70)
    budget_cap = max(0, available_for_agents // cost_per_candidate)
    return min(capped, budget_cap)


def _candidate_skill_coverage(job_profile: JobProfile, candidate_doc: dict[str, object]) -> float:
    required = {
        str(skill).strip().lower()
        for skill in (job_profile.required_skills or [])
        if isinstance(skill, str) and skill.strip()
    }
    if not required:
        return 0.0

    parsed = candidate_doc.get("parsed") if isinstance(candidate_doc.get("parsed"), dict) else {}
    candidate_terms: set[str] = set()
    for key in ("normalized_skills", "core_skills", "expanded_skills", "skills"):
        values = parsed.get(key) if isinstance(parsed, dict) else []
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value.strip():
                candidate_terms.add(value.strip().lower())
    if not candidate_terms:
        return 0.0
    return len(required.intersection(candidate_terms)) / float(len(required))


def should_apply_rerank(
    *,
    job_profile: JobProfile,
    enriched_hits: list[tuple[dict[str, object], dict[str, object]]],
    top_k: int,
) -> tuple[bool, str]:
    if len(enriched_hits) < 2:
        return False, "insufficient_candidates"

    pool_n = min(len(enriched_hits), resolve_rerank_pool_n(top_k))
    if pool_n < 2:
        return False, "insufficient_pool"

    score_rows: list[float] = []
    for hit, _ in enriched_hits[:pool_n]:
        score = hit.get("fusion_score", hit.get("score", 0.0))
        if isinstance(score, (int, float)):
            score_rows.append(float(score))
    if len(score_rows) < 2:
        return False, "score_missing"

    score_rows.sort(reverse=True)
    top_gap = score_rows[0] - score_rows[1]
    strict_gap_threshold = min(float(settings.rerank_gate_top2_gap_threshold), 0.015)
    tie_like = top_gap <= strict_gap_threshold

    unknown_ratio = float(job_profile.signal_quality.get("unknown_ratio", 0.0))
    low_confidence = float(job_profile.confidence) < float(settings.rerank_gate_confidence_threshold)
    noisy_query = unknown_ratio > float(settings.rerank_gate_unknown_ratio_threshold)
    ambiguous_query = low_confidence or noisy_query
    top_hit, top_doc = enriched_hits[0]
    top_skill_coverage = _candidate_skill_coverage(job_profile, top_doc)
    top_fusion_score = top_hit.get("fusion_score", top_hit.get("score", 0.0))
    top_fusion_score = float(top_fusion_score) if isinstance(top_fusion_score, (int, float)) else 0.0
    strong_top_hit = top_skill_coverage >= 0.6 and top_fusion_score >= 0.45

    if strong_top_hit and not ambiguous_query:
        return False, "strong_top_hit_without_query_ambiguity"
    if not tie_like:
        return False, "top_gap_too_wide_for_safe_rerank"
    if not ambiguous_query:
        return False, "tight_top_scores_but_query_is_confident"
    if strong_top_hit:
        return False, "ambiguous_query_but_top_hit_skill_overlap_is_strong"
    return True, "tight_top_scores_and_ambiguous_query"
