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
    tie_like = top_gap <= float(settings.rerank_gate_top2_gap_threshold)

    unknown_ratio = float(job_profile.signal_quality.get("unknown_ratio", 0.0))
    low_confidence = float(job_profile.confidence) < float(settings.rerank_gate_confidence_threshold)
    noisy_query = unknown_ratio > float(settings.rerank_gate_unknown_ratio_threshold)
    ambiguous_query = low_confidence or noisy_query

    if tie_like:
        return True, "tight_top_scores"
    if ambiguous_query:
        return True, "ambiguous_query_profile"
    return False, "clear_top_scores_and_confident_query"

