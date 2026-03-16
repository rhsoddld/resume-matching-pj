"""Canonical evaluation runner for resume matching.

README-style quick start:
1) Entry point
   - `python3 -m eval.eval_runner --golden-set src/eval/golden_set.jsonl`
2) Generated outputs (default)
   - `src/eval/outputs/retrieval_eval.json`
   - `src/eval/outputs/rerank_eval.json`
   - `src/eval/outputs/agent_eval.json`
   - `src/eval/outputs/performance_eval.json`
   - `src/eval/outputs/final_eval_report.md`
3) Core modules
   - `src/eval/metrics.py`
   - `src/eval/reporting.py`
   - `src/eval/config.py`
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import statistics
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval.config import EvalConfig, build_default_config
from eval.metrics import (
    binary_agreement_rate,
    candidate_binary_agreement_rate,
    candidates_per_sec,
    dimension_consistency_heuristic,
    estimate_cost_usd,
    estimate_tokens_from_text,
    explanation_groundedness_heuristic,
    latency_summary_ms,
    mrr,
    must_have_coverage,
    ndcg_at_k,
    query_understanding_alignment,
    recall_at_k,
    top1_improvement,
)
from eval.reporting import build_final_report_markdown, write_final_report, write_json
from backend.services.eval_adapter import MatchPipelineAdapter


logger = logging.getLogger(__name__)


class EvalRunnerError(RuntimeError):
    """Raised when canonical evaluation cannot proceed."""


@contextmanager
def _eval_runtime_context(*, eval_mode: str):
    previous = os.environ.get("RESUME_MATCHING_EVAL_MODE")
    os.environ["RESUME_MATCHING_EVAL_MODE"] = (eval_mode or "full").strip().lower()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("RESUME_MATCHING_EVAL_MODE", None)
        else:
            os.environ["RESUME_MATCHING_EVAL_MODE"] = previous


@dataclass
class QueryEvalRow:
    query_id: str
    status: str
    recall_at_10: float = 0.0
    recall_at_20: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    end_to_end_latency_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "status": self.status,
            "recall_at_10": self.recall_at_10,
            "recall_at_20": self.recall_at_20,
            "mrr": self.mrr,
            "ndcg_at_5": self.ndcg_at_5,
            "end_to_end_latency_ms": self.end_to_end_latency_ms,
            "error": self.error,
        }


def _configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    else:
        root.setLevel(logging.INFO)


def _load_golden_set(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise EvalRunnerError(f"Golden set file not found: {path}")

    rows: list[dict[str, Any]] = []
    required = {
        "query_id",
        "job_description",
        "expected_role",
        "expected_skills",
        "expected_optional_skills",
        "expected_seniority",
        "relevant_candidates",
    }

    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EvalRunnerError(f"Malformed JSONL at line {line_no}: {exc}") from exc

        # Soft-golden entries are kept in the file for documentation
        # but excluded from canonical metric computation.
        if bool(row.get("soft_golden", False)):
            continue

        missing = required.difference(row.keys())
        if missing:
            raise EvalRunnerError(f"Golden set line {line_no} missing required keys: {sorted(missing)}")

        rel = row.get("relevant_candidates")
        if not isinstance(rel, list) or not rel:
            raise EvalRunnerError(f"Golden set line {line_no} has invalid relevant_candidates")
        rows.append(row)

    if not rows:
        raise EvalRunnerError("Golden set is empty after parsing.")
    return rows


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(statistics.mean(values), 4)


def _safe_error_code(exc: Exception) -> str:
    token = str(exc).lower()
    if "timeout" in token or isinstance(exc, TimeoutError):
        return "timeout"
    return "error"


def _load_binary_reference(path: Path | None, *, field_name: str) -> dict[str, bool]:
    if path is None or not path.exists():
        return {}
    refs: dict[str, bool] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("reference_file_malformed path=%s line=%s", path, line_no)
            continue
        query_id = str(row.get("query_id") or "").strip()
        if not query_id:
            continue
        value = row.get(field_name)
        if isinstance(value, bool):
            refs[query_id] = value
            continue
        if isinstance(value, (int, float)):
            refs[query_id] = bool(int(value))
            continue
        if isinstance(value, str):
            refs[query_id] = value.strip().lower() in {"1", "true", "yes", "relevant"}
    return refs


def _load_candidate_binary_reference(path: Path | None, *, field_name: str) -> dict[tuple[str, str], bool]:
    if path is None or not path.exists():
        return {}
    refs: dict[tuple[str, str], bool] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("candidate_reference_file_malformed path=%s line=%s", path, line_no)
            continue
        query_id = str(row.get("query_id") or "").strip()
        candidate_id = str(row.get("candidate_id") or "").strip()
        if not query_id or not candidate_id:
            continue
        value = row.get(field_name)
        if isinstance(value, bool):
            refs[(query_id, candidate_id)] = value
            continue
        if isinstance(value, (int, float)):
            refs[(query_id, candidate_id)] = bool(int(value))
            continue
        if isinstance(value, str):
            refs[(query_id, candidate_id)] = value.strip().lower() in {"1", "true", "yes", "relevant"}
    return refs


def _lookup_nested_float(payload: dict[str, Any], *path: str) -> float | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if isinstance(current, (int, float)):
        return round(float(current), 4)
    return None


def _load_candidate_float_reference(path: Path | None, *, field_path: tuple[str, ...]) -> dict[tuple[str, str], float]:
    if path is None or not path.exists():
        return {}
    refs: dict[tuple[str, str], float] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("candidate_reference_file_malformed path=%s line=%s", path, line_no)
            continue
        query_id = str(row.get("query_id") or "").strip()
        candidate_id = str(row.get("candidate_id") or "").strip()
        if not query_id or not candidate_id:
            continue
        value = _lookup_nested_float(row, *field_path)
        if value is not None:
            refs[(query_id, candidate_id)] = value
    return refs


def _load_rerank_gate_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("rerank_gate_state_malformed path=%s", path)
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _resolve_rerank_execution(
    *,
    config: EvalConfig,
    output_paths: Any,
) -> tuple[bool, dict[str, Any]]:
    gate_state = _load_rerank_gate_state(output_paths.rerank_gate_state_json)
    last_mrr_delta = gate_state.get("last_mrr_delta")
    if config.enable_rerank_eval and config.rerank_auto_bypass_on_negative_delta:
        if isinstance(last_mrr_delta, (int, float)) and float(last_mrr_delta) < 0.0:
            decision = {
                "enabled_this_run": False,
                "reason": "auto_bypass_previous_negative_mrr_delta",
                "last_mrr_delta": round(float(last_mrr_delta), 4),
                "last_run_id": gate_state.get("last_run_id"),
            }
            return False, decision

    decision = {
        "enabled_this_run": bool(config.enable_rerank_eval),
        "reason": "enabled" if config.enable_rerank_eval else "disabled_by_config",
        "last_mrr_delta": round(float(last_mrr_delta), 4) if isinstance(last_mrr_delta, (int, float)) else None,
        "last_run_id": gate_state.get("last_run_id"),
    }
    return bool(config.enable_rerank_eval), decision


def run_evaluation(config: EvalConfig, adapter: MatchPipelineAdapter | None = None) -> dict[str, Any]:
    run_started = dt.datetime.utcnow()
    run_id = f"eval-{run_started.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    adapter = adapter or MatchPipelineAdapter()

    rows = _load_golden_set(config.golden_set_path)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    human_reference = _load_binary_reference(config.human_annotations_path, field_name="top1_is_relevant")
    llm_reference = _load_binary_reference(config.llm_judge_path, field_name="top1_is_relevant")
    llm_candidate_reference = _load_candidate_binary_reference(config.llm_judge_path, field_name="top1_is_relevant")
    llm_explanation_quality_reference = _load_candidate_float_reference(
        config.llm_judge_path,
        field_path=("explanation_quality", "overall_score"),
    )
    llm_explanation_groundedness_reference = _load_candidate_float_reference(
        config.llm_judge_path,
        field_path=("explanation_quality", "groundedness_score"),
    )
    rerank_enabled_this_run, rerank_gate_decision = _resolve_rerank_execution(
        config=config,
        output_paths=config.output_paths,
    )
    predicted_top1_relevance: dict[str, bool] = {}
    predicted_agent_top1_relevance: dict[tuple[str, str], bool] = {}

    query_role_acc: list[float] = []
    query_skill_acc: list[float] = []
    query_unknown: list[float] = []
    query_fallback: list[float] = []

    retrieval_recall10: list[float] = []
    retrieval_recall20: list[float] = []
    retrieval_mrr: list[float] = []
    retrieval_must_have: list[float] = []

    rerank_ndcg5: list[float] = []
    rerank_mrr_delta: list[float] = []
    rerank_top1_imp: list[int] = []
    rerank_added_latency_ms: list[float] = []

    agent_expl_presence: list[float] = []
    agent_groundedness: list[float] = []
    agent_consistency: list[float] = []
    llm_explanation_quality_scores: list[float] = []
    llm_explanation_groundedness_scores: list[float] = []

    e2e_latency_ms: list[float] = []
    qu_latency_ms: list[float] = []
    retrieval_latency_ms: list[float] = []
    rerank_latency_ms: list[float] = []
    agent_latency_ms: list[float] = []
    candidates_per_sec_values: list[float] = []

    total_tokens: list[int] = []
    rerank_extra_tokens: list[int] = []
    agent_extra_tokens: list[int] = []
    estimated_costs: list[float] = []

    fallback_trigger_count = 0
    timeout_count = 0
    error_count = 0
    degraded_mode_success = 0
    stage_reliability_counts: dict[str, int] = {
        "query_understanding_fallback_count": 0,
        "retrieval_fallback_count": 0,
        "agent_fallback_count": 0,
        "agent_runtime_fallback_candidate_count": 0,
        "query_understanding_error_count": 0,
        "retrieval_error_count": 0,
        "rerank_error_count": 0,
        "agent_error_count": 0,
        "agent_runtime_error_candidate_count": 0,
    }

    per_query_summary: list[QueryEvalRow] = []
    retrieval_per_query: list[dict[str, Any]] = []
    rerank_per_query: list[dict[str, Any]] = []
    agent_per_query: list[dict[str, Any]] = []
    perf_per_query: list[dict[str, Any]] = []

    for row in rows:
        query_id = str(row.get("query_id"))
        job_description = str(row.get("job_description", ""))
        expected_role = str(row.get("expected_role", ""))
        expected_skills = [str(skill) for skill in (row.get("expected_skills") or [])]
        relevant_candidates = row.get("relevant_candidates") or []
        relevance_by_id = {
            str(item.get("candidate_id")): int(item.get("grade", 0))
            for item in relevant_candidates
            if item.get("candidate_id")
        }
        expected_ids = set(relevance_by_id.keys())

        query_start = time.perf_counter()
        status = "ok"
        query_error: str | None = None
        query_has_fallback = False
        query_has_timeout = False
        query_has_error = False

        current_recall10 = 0.0
        current_recall20 = 0.0
        current_mrr = 0.0
        current_ndcg5 = 0.0

        try:
            if config.enable_query_understanding:
                try:
                    qu = adapter.query_understanding(job_description=job_description)
                    qu_latency_ms.append(float(qu.get("latency_ms", 0.0)))
                    alignment = query_understanding_alignment(
                        expected_role=expected_role,
                        expected_skills=expected_skills,
                        actual_roles=list(qu.get("roles") or []),
                        actual_skills=list(qu.get("required_skills") or []),
                        unknown_ratio=float(qu.get("unknown_ratio", 1.0)),
                        fallback_used=bool(qu.get("fallback_used", False)),
                    )
                    query_role_acc.append(alignment["role_extraction_accuracy"])
                    query_skill_acc.append(alignment["skill_extraction_accuracy"])
                    query_unknown.append(alignment["unknown_ratio"])
                    query_fallback.append(alignment["fallback_rate"])
                    if alignment["fallback_rate"] > 0:
                        query_has_fallback = True
                        stage_reliability_counts["query_understanding_fallback_count"] += 1
                except Exception as exc:
                    logger.exception("query_understanding_failed query_id=%s", query_id)
                    status = "degraded"
                    if _safe_error_code(exc) == "timeout":
                        query_has_timeout = True
                    else:
                        query_has_error = True
                    stage_reliability_counts["query_understanding_error_count"] += 1

            retrieval = adapter.retrieve(job_description=job_description, top_k=max(config.retrieval_top_k))
            retrieval_latency = float(retrieval.get("latency_ms", 0.0))
            retrieval_latency_ms.append(retrieval_latency)

            retrieved_ids = [str(cid) for cid in retrieval.get("ranked_ids") or []]
            predicted_top1_relevance[query_id] = bool(retrieved_ids and retrieved_ids[0] in expected_ids)
            current_recall10 = recall_at_k(expected_ids, retrieved_ids, config.retrieval_top_k[0])
            current_recall20 = recall_at_k(expected_ids, retrieved_ids, config.retrieval_top_k[1])
            current_mrr = mrr(expected_ids, retrieved_ids)

            skills_map = retrieval.get("candidate_skills") or {}
            candidate_skill_lists = [
                list(skills_map.get(cid) or [])
                for cid in retrieved_ids[: config.retrieval_top_k[0]]
            ]
            must_have = must_have_coverage(expected_skills, candidate_skill_lists)

            retrieval_recall10.append(current_recall10)
            retrieval_recall20.append(current_recall20)
            retrieval_mrr.append(current_mrr)
            retrieval_must_have.append(must_have)

            if bool(retrieval.get("fallback_triggered", False)):
                query_has_fallback = True
                stage_reliability_counts["retrieval_fallback_count"] += 1

            retrieval_tokens = retrieval.get("token_usage")
            if isinstance(retrieval_tokens, dict):
                total = retrieval_tokens.get("total_tokens")
                if isinstance(total, int):
                    total_tokens.append(total)

            retrieval_per_query.append(
                {
                    "query_id": query_id,
                    "recall_at_10": current_recall10,
                    "recall_at_20": current_recall20,
                    "mrr": current_mrr,
                    "must_have_coverage": must_have,
                    "retrieved_count": len(retrieved_ids),
                    "retrieval_stage_signal": str(retrieval.get("retrieval_stage_signal", "unknown")),
                }
            )

            cps = candidates_per_sec(len(retrieved_ids), retrieval_latency)
            candidates_per_sec_values.append(cps)

            if rerank_enabled_this_run and retrieved_ids:
                try:
                    baseline_ids = retrieved_ids[: config.rerank_pool_k]
                    baseline_mrr = mrr(expected_ids, baseline_ids)
                    baseline_ndcg5 = ndcg_at_k(relevance_by_id, baseline_ids, config.rerank_eval_k)

                    reranked = adapter.rerank(
                        job_description=job_description,
                        baseline_hits=list(retrieval.get("hits") or []),
                        top_k=config.rerank_pool_k,
                    )
                    reranked_ids = [str(cid) for cid in (reranked.get("ranked_ids") or [])]
                    rerank_latency = float(reranked.get("latency_ms", 0.0))
                    rerank_latency_ms.append(rerank_latency)
                    rerank_added_latency_ms.append(rerank_latency)

                    reranked_mrr = mrr(expected_ids, reranked_ids)
                    reranked_ndcg5 = ndcg_at_k(relevance_by_id, reranked_ids, config.rerank_eval_k)
                    delta_mrr = round(reranked_mrr - baseline_mrr, 4)
                    top1_delta = top1_improvement(expected_ids, baseline_ids, reranked_ids)

                    current_ndcg5 = reranked_ndcg5
                    rerank_ndcg5.append(reranked_ndcg5)
                    rerank_mrr_delta.append(delta_mrr)
                    rerank_top1_imp.append(top1_delta)

                    rerank_per_query.append(
                        {
                            "query_id": query_id,
                            "baseline_mrr": baseline_mrr,
                            "reranked_mrr": reranked_mrr,
                            "mrr_delta": delta_mrr,
                            "baseline_ndcg_at_5": baseline_ndcg5,
                            "reranked_ndcg_at_5": reranked_ndcg5,
                            "top1_improvement": top1_delta,
                            "added_latency_ms": rerank_latency,
                        }
                    )
                    rerank_tokens_payload = reranked.get("token_usage")
                    if isinstance(rerank_tokens_payload, dict):
                        total = rerank_tokens_payload.get("total_tokens")
                        if isinstance(total, int):
                            rerank_extra_tokens.append(total)
                except Exception as exc:
                    logger.exception("rerank_eval_failed query_id=%s", query_id)
                    status = "degraded"
                    if _safe_error_code(exc) == "timeout":
                        query_has_timeout = True
                    else:
                        query_has_error = True
                    stage_reliability_counts["rerank_error_count"] += 1
            elif config.enable_rerank_eval and retrieved_ids:
                baseline_ids = retrieved_ids[: config.rerank_pool_k]
                baseline_mrr = mrr(expected_ids, baseline_ids)
                baseline_ndcg5 = ndcg_at_k(relevance_by_id, baseline_ids, config.rerank_eval_k)
                current_ndcg5 = baseline_ndcg5
                rerank_per_query.append(
                    {
                        "query_id": query_id,
                        "baseline_mrr": baseline_mrr,
                        "reranked_mrr": baseline_mrr,
                        "mrr_delta": 0.0,
                        "baseline_ndcg_at_5": baseline_ndcg5,
                        "reranked_ndcg_at_5": baseline_ndcg5,
                        "top1_improvement": 0,
                        "added_latency_ms": 0.0,
                        "skipped_reason": str(rerank_gate_decision.get("reason", "disabled")),
                    }
                )

            if config.enable_agent_eval:
                try:
                    agent_res = adapter.agent_evaluate(job_description=job_description, top_k=config.final_match_top_k)
                    agent_latency = float(agent_res.get("latency_ms", 0.0))
                    agent_latency_ms.append(agent_latency)

                    matches = list(agent_res.get("matches") or [])
                    if matches:
                        present_count = 0
                        grounded_scores: list[float] = []
                        consistency_scores: list[float] = []
                        top_match = matches[0] if matches else {}
                        top_candidate_id = str(top_match.get("candidate_id") or "").strip()
                        if top_candidate_id:
                            predicted_agent_top1_relevance[(query_id, top_candidate_id)] = top_candidate_id in expected_ids
                            llm_quality = llm_explanation_quality_reference.get((query_id, top_candidate_id))
                            if llm_quality is not None:
                                llm_explanation_quality_scores.append(llm_quality)
                            llm_groundedness = llm_explanation_groundedness_reference.get((query_id, top_candidate_id))
                            if llm_groundedness is not None:
                                llm_explanation_groundedness_scores.append(llm_groundedness)

                        for match in matches:
                            explanation = match.get("agent_explanation")
                            if explanation:
                                present_count += 1
                            grounded_scores.append(
                                explanation_groundedness_heuristic(
                                    explanation=explanation,
                                    expected_skills=expected_skills,
                                    candidate_skills=list(match.get("skills") or []),
                                )
                            )
                            consistency_scores.append(
                                dimension_consistency_heuristic(
                                    agent_scores=dict(match.get("agent_scores") or {}),
                                    final_score=float(match.get("score")) if match.get("score") is not None else None,
                                )
                            )

                        presence_rate = round(present_count / float(len(matches)), 4)
                        grounded_avg = _avg(grounded_scores)
                        consistency_avg = _avg(consistency_scores)

                        agent_expl_presence.append(presence_rate)
                        agent_groundedness.append(grounded_avg)
                        agent_consistency.append(consistency_avg)

                        agent_per_query.append(
                            {
                                "query_id": query_id,
                                "explanation_presence_rate": presence_rate,
                                "groundedness_score": grounded_avg,
                                "dimension_consistency_score": consistency_avg,
                            }
                        )

                    if bool(agent_res.get("fallback_used", False)):
                        query_has_fallback = True
                        stage_reliability_counts["agent_fallback_count"] += 1

                    runtime_fallback_candidates = int(agent_res.get("agent_runtime_fallback_count", 0) or 0)
                    runtime_error_candidates = int(agent_res.get("agent_runtime_error_count", 0) or 0)
                    if runtime_fallback_candidates > 0:
                        query_has_fallback = True
                        stage_reliability_counts["agent_runtime_fallback_candidate_count"] += runtime_fallback_candidates
                    if runtime_error_candidates > 0:
                        query_has_error = True
                        stage_reliability_counts["agent_runtime_error_candidate_count"] += runtime_error_candidates

                    token_usage = agent_res.get("token_usage")
                    if isinstance(token_usage, dict):
                        total = token_usage.get("total_tokens")
                        agent_tokens = token_usage.get("total_tokens")
                        if isinstance(total, int):
                            total_tokens.append(total)
                        if isinstance(agent_tokens, int):
                            agent_extra_tokens.append(agent_tokens)

                except Exception as exc:
                    logger.exception("agent_eval_failed query_id=%s", query_id)
                    status = "degraded"
                    if _safe_error_code(exc) == "timeout":
                        query_has_timeout = True
                    else:
                        query_has_error = True
                    stage_reliability_counts["agent_error_count"] += 1

        except Exception as exc:
            logger.exception("query_eval_failed query_id=%s", query_id)
            status = "error"
            query_error = str(exc)
            if _safe_error_code(exc) == "timeout":
                query_has_timeout = True
            else:
                query_has_error = True
            stage_reliability_counts["retrieval_error_count"] += 1

        end_to_end_ms = (time.perf_counter() - query_start) * 1000.0
        e2e_latency_ms.append(end_to_end_ms)

        if status == "degraded":
            degraded_mode_success += 1
        if query_has_fallback:
            fallback_trigger_count += 1
        if query_has_timeout:
            timeout_count += 1
        if query_has_error:
            error_count += 1

        perf_per_query.append(
            {
                "query_id": query_id,
                "end_to_end_latency_ms": round(end_to_end_ms, 4),
                "retrieval_latency_ms": round(retrieval_latency_ms[-1], 4) if retrieval_latency_ms else 0.0,
                "rerank_latency_ms": round(rerank_latency_ms[-1], 4) if rerank_latency_ms else 0.0,
                "agent_latency_ms": round(agent_latency_ms[-1], 4) if agent_latency_ms else 0.0,
                "candidates_per_sec": candidates_per_sec_values[-1] if candidates_per_sec_values else 0.0,
            }
        )

        row_out = QueryEvalRow(
            query_id=query_id,
            status=status,
            recall_at_10=current_recall10,
            recall_at_20=current_recall20,
            mrr=current_mrr,
            ndcg_at_5=current_ndcg5,
            end_to_end_latency_ms=round(end_to_end_ms, 4),
            error=query_error,
        )
        per_query_summary.append(row_out)

    run_finished = dt.datetime.utcnow()
    total_queries = len(rows)
    successful_queries = len([row for row in per_query_summary if row.status != "error"])
    human_agreement = binary_agreement_rate(predicted_top1_relevance, human_reference) if config.enable_human_agreement else None
    llm_judge_agreement: float | None = None
    if config.enable_llm_judge_agreement:
        if llm_candidate_reference and predicted_agent_top1_relevance:
            llm_judge_agreement = candidate_binary_agreement_rate(predicted_agent_top1_relevance, llm_candidate_reference)
        else:
            llm_judge_agreement = binary_agreement_rate(predicted_top1_relevance, llm_reference)
    est_cost = estimate_cost_usd(
        input_tokens=int(_avg([float(v) for v in total_tokens])) if total_tokens else None,
        output_tokens=int(_avg([float(v) for v in agent_extra_tokens])) if agent_extra_tokens else None,
        price_per_1k_input=config.est_price_per_1k_input_usd,
        price_per_1k_output=config.est_price_per_1k_output_usd,
    )
    if est_cost is not None:
        estimated_costs.append(est_cost)

    query_eval_payload = {
        "run_id": run_id,
        "role_extraction_accuracy": _avg(query_role_acc),
        "skill_extraction_accuracy": _avg(query_skill_acc),
        "unknown_ratio": _avg(query_unknown),
        "fallback_rate": _avg(query_fallback),
        "per_query": [
            {
                "query_id": row.query_id,
                "status": row.status,
            }
            for row in per_query_summary
        ],
    }

    retrieval_eval_payload = {
        "run_id": run_id,
        "query_understanding": query_eval_payload,
        "recall_at_10": _avg(retrieval_recall10),
        "recall_at_20": _avg(retrieval_recall20),
        "mrr": _avg(retrieval_mrr),
        "must_have_coverage": _avg(retrieval_must_have),
        "per_query": retrieval_per_query,
    }

    rerank_eval_payload = {
        "run_id": run_id,
        "gate": rerank_gate_decision,
        "ndcg_at_5": _avg(rerank_ndcg5),
        "mrr_delta": _avg(rerank_mrr_delta),
        "top1_improvement": round(sum(rerank_top1_imp), 4) if rerank_top1_imp else 0.0,
        "top1_improvement_rate": round(
            len([v for v in rerank_top1_imp if v > 0]) / float(len(rerank_top1_imp)),
            4,
        )
        if rerank_top1_imp
        else 0.0,
        "added_latency_ms": _avg(rerank_added_latency_ms),
        "per_query": rerank_per_query,
    }

    agent_eval_payload = {
        "run_id": run_id,
        "human_agreement": human_agreement,
        "llm_as_judge_agreement": llm_judge_agreement,
        "llm_explanation_quality_score": _avg(llm_explanation_quality_scores) if llm_explanation_quality_scores else None,
        "llm_explanation_groundedness_score": _avg(llm_explanation_groundedness_scores) if llm_explanation_groundedness_scores else None,
        "explanation_presence_rate": _avg(agent_expl_presence),
        "groundedness_score": _avg(agent_groundedness),
        "dimension_consistency_score": _avg(agent_consistency),
        "per_query": agent_per_query,
    }

    performance_eval_payload = {
        "run_id": run_id,
        "end_to_end_latency": latency_summary_ms(e2e_latency_ms),
        "stage_latency": {
            "query_understanding_ms": latency_summary_ms(qu_latency_ms),
            "retrieval_ms": latency_summary_ms(retrieval_latency_ms),
            "rerank_ms": latency_summary_ms(rerank_latency_ms),
            "agent_eval_ms": latency_summary_ms(agent_latency_ms),
        },
        "total_tokens_per_request": _avg([float(v) for v in total_tokens]),
        "rerank_extra_tokens": _avg([float(v) for v in rerank_extra_tokens]),
        "agent_eval_extra_tokens": _avg([float(v) for v in agent_extra_tokens]),
        "estimated_cost_per_request_usd": _avg(estimated_costs),
        "candidates_per_sec": _avg(candidates_per_sec_values),
        "per_query": perf_per_query,
    }

    reliability_eval = {
        "run_id": run_id,
        "fallback_trigger_rate": round(fallback_trigger_count / float(max(1, total_queries)), 4),
        "timeout_rate": round(timeout_count / float(max(1, total_queries)), 4),
        "error_rate": round(error_count / float(max(1, total_queries)), 4),
        "degraded_mode_success_rate": round(degraded_mode_success / float(max(1, total_queries)), 4),
        "counts": {
            "fallback_trigger_count": fallback_trigger_count,
            "timeout_count": timeout_count,
            "error_count": error_count,
            "degraded_mode_success": degraded_mode_success,
            **stage_reliability_counts,
        },
    }

    run_metadata = {
        "run_id": run_id,
        "started_at_utc": run_started.isoformat(timespec="seconds") + "Z",
        "finished_at_utc": run_finished.isoformat(timespec="seconds") + "Z",
        "golden_set_path": str(config.golden_set_path),
        "run_label": config.run_label,
        "total_queries": total_queries,
        "successful_queries": successful_queries,
        "rerank_enabled_this_run": rerank_enabled_this_run,
        "rerank_gate_reason": rerank_gate_decision.get("reason"),
    }

    write_json(config.output_paths.retrieval_eval_json, retrieval_eval_payload)
    write_json(config.output_paths.rerank_eval_json, rerank_eval_payload)
    write_json(config.output_paths.agent_eval_json, agent_eval_payload)
    write_json(config.output_paths.performance_eval_json, {**performance_eval_payload, "reliability": reliability_eval})
    persisted_mrr_delta = _avg(rerank_mrr_delta)
    if not rerank_enabled_this_run:
        previous_delta = rerank_gate_decision.get("last_mrr_delta")
        if isinstance(previous_delta, (int, float)):
            persisted_mrr_delta = round(float(previous_delta), 4)
    write_json(
        config.output_paths.rerank_gate_state_json,
        {
            "last_run_id": run_id,
            "last_mrr_delta": persisted_mrr_delta,
            "next_run_rerank_enabled": not (
                config.rerank_auto_bypass_on_negative_delta and persisted_mrr_delta < 0.0
            ),
            "auto_bypass_enabled": bool(config.rerank_auto_bypass_on_negative_delta),
        },
    )

    known_limitations = [
        "Human/LLM agreement requires JSONL reference files with query_id + top1_is_relevant.",
        "Token/cost fields are currently heuristic estimates until exact provider usage telemetry is exposed per stage.",
        "Fallback/error counts are query-level rates; candidate-level runtime fallback/error counts are reported in reliability.counts.",
    ]
    next_actions = [
        "Wire explicit query-understanding extractor hook to production endpoint for exact parser parity.",
        "Attach token usage instrumentation from retrieval/rerank/agent calls into adapter token_usage payload.",
        "Run eval_runner on a schedule and enforce calibrated thresholds for Recall@20, NDCG@5, and degraded-mode success rate.",
    ]

    report_md = build_final_report_markdown(
        run_metadata=run_metadata,
        query_understanding_eval=query_eval_payload,
        retrieval_eval=retrieval_eval_payload,
        rerank_eval=rerank_eval_payload,
        agent_eval=agent_eval_payload,
        performance_eval=performance_eval_payload,
        reliability_eval=reliability_eval,
        per_query_summary=[row.to_dict() for row in per_query_summary],
        known_limitations=known_limitations,
        next_actions=next_actions,
    )
    write_final_report(config.output_paths.final_eval_report_md, report_md)

    return {
        "run_metadata": run_metadata,
        "retrieval_eval": retrieval_eval_payload,
        "rerank_eval": rerank_eval_payload,
        "agent_eval": agent_eval_payload,
        "performance_eval": performance_eval_payload,
        "reliability_eval": reliability_eval,
        "per_query_summary": [row.to_dict() for row in per_query_summary],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run canonical evaluation over golden set")
    parser.add_argument("--golden-set", default="src/eval/golden_set.jsonl", help="Path to golden set JSONL")
    parser.add_argument("--outputs-dir", default="src/eval/outputs", help="Directory for output artifacts")
    parser.add_argument(
        "--human-annotations",
        default="src/eval/human_annotations.jsonl",
        help="Optional JSONL with query_id + top1_is_relevant",
    )
    parser.add_argument(
        "--llm-judge-annotations",
        default="src/eval/llm_judge_annotations.jsonl",
        help="Optional JSONL with query_id + top1_is_relevant",
    )
    parser.add_argument("--run-label", default="manual", help="Run label for metadata")
    parser.add_argument(
        "--mode",
        choices=["full", "hybrid", "rerank", "agent"],
        default="full",
        help=(
            "Evaluation mode: "
            "'full' (default, all stages), "
            "'hybrid' (query understanding + retrieval only), "
            "'rerank' (retrieval + rerank delta), "
            "'agent' (multi-agent evaluation + performance)"
        ),
    )
    return parser.parse_args()


def main() -> int:
    _configure_logging()
    args = _parse_args()

    root = Path(__file__).resolve().parents[2]
    config = build_default_config(
        root_dir=root,
        golden_set_path=(root / args.golden_set),
        outputs_dir=(root / args.outputs_dir),
        human_annotations_path=(root / args.human_annotations),
        llm_judge_path=(root / args.llm_judge_annotations),
        run_label=args.run_label,
        eval_mode=args.mode,
    )

    try:
        with _eval_runtime_context(eval_mode=args.mode):
            result = run_evaluation(config)
            logger.info(
                "eval_runner_completed run_id=%s total_queries=%s successful_queries=%s",
                result["run_metadata"]["run_id"],
                result["run_metadata"]["total_queries"],
                result["run_metadata"]["successful_queries"],
            )
            return 0
    except EvalRunnerError as exc:
        logger.error("eval_runner_failed reason=%s", exc)
        return 2
    except Exception:
        logger.exception("eval_runner_failed_unexpected")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
