"""Pure metric functions for evaluation runner.

README-style quick start:
- Imported by: `src/eval/eval_runner.py`
- Unit-test scaffold: `tests/test_eval_metrics_scaffold.py`
"""
from __future__ import annotations

import math
from statistics import mean
from typing import Iterable


def _safe_lower(value: object) -> str:
    return str(value or "").strip().lower()


def normalize_skill_set(skills: Iterable[object]) -> set[str]:
    normalized: set[str] = set()
    for skill in skills:
        token = _safe_lower(skill)
        if token:
            normalized.add(token)
    return normalized


def recall_at_k(expected_ids: set[str], ranked_ids: list[str], k: int) -> float:
    if not expected_ids or k <= 0:
        return 0.0
    top_k = ranked_ids[:k]
    hits = len(set(top_k).intersection(expected_ids))
    return round(hits / float(len(expected_ids)), 4)


def mrr(expected_ids: set[str], ranked_ids: list[str]) -> float:
    if not expected_ids:
        return 0.0
    for idx, candidate_id in enumerate(ranked_ids, start=1):
        if candidate_id in expected_ids:
            return round(1.0 / float(idx), 4)
    return 0.0


def must_have_coverage(expected_skills: list[str], candidate_skill_lists: list[list[str]]) -> float:
    expected = normalize_skill_set(expected_skills)
    if not expected:
        return 0.0
    union_skills: set[str] = set()
    for candidate_skills in candidate_skill_lists:
        union_skills.update(normalize_skill_set(candidate_skills))
    covered = len(union_skills.intersection(expected))
    return round(covered / float(len(expected)), 4)


def ndcg_at_k(relevance_by_id: dict[str, int], ranked_ids: list[str], k: int) -> float:
    if k <= 0:
        return 0.0

    def _dcg(ids: list[str]) -> float:
        score = 0.0
        for idx, cid in enumerate(ids[:k], start=1):
            rel = max(0, int(relevance_by_id.get(cid, 0)))
            gain = (2**rel - 1) / math.log2(idx + 1)
            score += gain
        return score

    actual_dcg = _dcg(ranked_ids)
    ideal_ids = sorted(relevance_by_id, key=lambda cid: relevance_by_id[cid], reverse=True)
    ideal_dcg = _dcg(ideal_ids)
    if ideal_dcg <= 0:
        return 0.0
    return round(actual_dcg / ideal_dcg, 4)


def top1_improvement(expected_ids: set[str], baseline_ids: list[str], reranked_ids: list[str]) -> int:
    baseline_hit = 1 if baseline_ids and baseline_ids[0] in expected_ids else 0
    reranked_hit = 1 if reranked_ids and reranked_ids[0] in expected_ids else 0
    return reranked_hit - baseline_hit


def query_understanding_alignment(
    *,
    expected_role: str,
    expected_skills: list[str],
    actual_roles: list[str],
    actual_skills: list[str],
    unknown_ratio: float | None,
    fallback_used: bool,
) -> dict[str, float]:
    expected_role_token = _safe_lower(expected_role)
    actual_role_tokens = normalize_skill_set(actual_roles)
    role_accuracy = 1.0 if expected_role_token and expected_role_token in actual_role_tokens else 0.0

    expected_skill_tokens = normalize_skill_set(expected_skills)
    actual_skill_tokens = normalize_skill_set(actual_skills)
    if expected_skill_tokens:
        matched = len(expected_skill_tokens.intersection(actual_skill_tokens))
        skill_accuracy = matched / float(len(expected_skill_tokens))
    else:
        skill_accuracy = 0.0

    normalized_unknown_ratio = float(unknown_ratio) if unknown_ratio is not None else 1.0
    fallback_rate = 1.0 if fallback_used else 0.0
    return {
        "role_extraction_accuracy": round(role_accuracy, 4),
        "skill_extraction_accuracy": round(skill_accuracy, 4),
        "unknown_ratio": round(normalized_unknown_ratio, 4),
        "fallback_rate": round(fallback_rate, 4),
    }


def explanation_groundedness_heuristic(
    *,
    explanation: str | None,
    expected_skills: list[str],
    candidate_skills: list[str],
) -> float:
    text = _safe_lower(explanation)
    if not text:
        return 0.0

    expected = normalize_skill_set(expected_skills)
    candidate = normalize_skill_set(candidate_skills)
    if not expected and not candidate:
        return 0.5

    mention_hits = 0
    mention_space = expected.union(candidate)
    for token in mention_space:
        if token and token in text:
            mention_hits += 1

    coverage = mention_hits / float(len(mention_space)) if mention_space else 0.0
    length_bonus = 0.1 if len(text.split()) >= 12 else 0.0
    score = min(1.0, coverage + length_bonus)
    return round(score, 4)


def dimension_consistency_heuristic(*, agent_scores: dict, final_score: float | None) -> float:
    if not agent_scores:
        return 0.0

    score_keys = ["skill", "experience", "technical", "culture"]
    values: list[float] = []
    for key in score_keys:
        raw = agent_scores.get(key)
        if isinstance(raw, (int, float)):
            values.append(max(0.0, min(1.0, float(raw))))
    if not values:
        return 0.0

    avg_score = mean(values)
    if final_score is None:
        return round(avg_score, 4)

    bounded_final = max(0.0, min(1.0, float(final_score)))
    distance = abs(avg_score - bounded_final)
    consistency = max(0.0, 1.0 - distance)
    return round(consistency, 4)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return round(sorted_values[0], 4)
    rank = (len(sorted_values) - 1) * (p / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return round(sorted_values[int(rank)], 4)
    weight = rank - lower
    value = sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight
    return round(value, 4)


def latency_summary_ms(latencies_ms: list[float]) -> dict[str, float]:
    clean = [max(0.0, float(v)) for v in latencies_ms]
    if not clean:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "mean_ms": 0.0}
    return {
        "p50_ms": percentile(clean, 50),
        "p95_ms": percentile(clean, 95),
        "p99_ms": percentile(clean, 99),
        "mean_ms": round(mean(clean), 4),
    }


def candidates_per_sec(candidate_count: int, latency_ms: float) -> float:
    if candidate_count <= 0 or latency_ms <= 0:
        return 0.0
    return round(candidate_count / (latency_ms / 1000.0), 4)


def estimate_cost_usd(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    price_per_1k_input: float,
    price_per_1k_output: float,
) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    in_tokens = max(0, int(input_tokens or 0))
    out_tokens = max(0, int(output_tokens or 0))
    cost = (in_tokens / 1000.0) * price_per_1k_input + (out_tokens / 1000.0) * price_per_1k_output
    return round(cost, 6)


def estimate_tokens_from_text(text: str | None) -> int:
    if not text:
        return 0
    # Lightweight heuristic: ~4 chars/token for English-heavy technical text.
    return max(1, int(len(text) / 4))


def binary_agreement_rate(predicted: dict[str, bool], reference: dict[str, bool]) -> float | None:
    common_ids = sorted(set(predicted.keys()).intersection(reference.keys()))
    if not common_ids:
        return None
    agree = sum(1 for qid in common_ids if bool(predicted[qid]) == bool(reference[qid]))
    return round(agree / float(len(common_ids)), 4)


def candidate_binary_agreement_rate(
    predicted: dict[tuple[str, str], bool],
    reference: dict[tuple[str, str], bool],
) -> float | None:
    common_keys = sorted(set(predicted.keys()).intersection(reference.keys()))
    if not common_keys:
        return None
    agree = sum(1 for key in common_keys if bool(predicted[key]) == bool(reference[key]))
    return round(agree / float(len(common_keys)), 4)
