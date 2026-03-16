"""Reporting helpers for canonical evaluation outputs.

README-style quick start:
- JSON output helpers + markdown synthesis for final reviewer-facing report.
- Used by: `src/eval/eval_runner.py`
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_float(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.4f}"
    return "-"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_final_report_markdown(
    *,
    run_metadata: dict[str, Any],
    query_understanding_eval: dict[str, Any],
    retrieval_eval: dict[str, Any],
    rerank_eval: dict[str, Any],
    agent_eval: dict[str, Any],
    performance_eval: dict[str, Any],
    reliability_eval: dict[str, Any],
    per_query_summary: list[dict[str, Any]],
    known_limitations: list[str],
    next_actions: list[str],
) -> str:
    aggregate_rows = [
        ["Query role extraction accuracy", _format_float(query_understanding_eval.get("role_extraction_accuracy"))],
        ["Query skill extraction accuracy", _format_float(query_understanding_eval.get("skill_extraction_accuracy"))],
        ["Retrieval Recall@10", _format_float(retrieval_eval.get("recall_at_10"))],
        ["Retrieval Recall@20", _format_float(retrieval_eval.get("recall_at_20"))],
        ["Retrieval MRR", _format_float(retrieval_eval.get("mrr"))],
        ["Rerank NDCG@5", _format_float(rerank_eval.get("ndcg_at_5"))],
        ["Rerank MRR delta", _format_float(rerank_eval.get("mrr_delta"))],
        ["Human agreement", _format_float(agent_eval.get("human_agreement"))],
        ["LLM-as-Judge agreement", _format_float(agent_eval.get("llm_as_judge_agreement"))],
        ["LLM explanation quality", _format_float(agent_eval.get("llm_explanation_quality_score"))],
        ["LLM explanation groundedness", _format_float(agent_eval.get("llm_explanation_groundedness_score"))],
        ["Agent explanation presence", _format_float(agent_eval.get("explanation_presence_rate"))],
        ["Agent groundedness", _format_float(agent_eval.get("groundedness_score"))],
        ["End-to-end latency p95 (ms)", _format_float(performance_eval.get("end_to_end_latency", {}).get("p95_ms"))],
        ["Cost/request (USD)", _format_float(performance_eval.get("estimated_cost_per_request_usd"))],
        ["Fallback trigger rate", _format_float(reliability_eval.get("fallback_trigger_rate"))],
        ["Error rate", _format_float(reliability_eval.get("error_rate"))],
    ]

    query_rows = []
    for row in per_query_summary[:20]:
        query_rows.append(
            [
                str(row.get("query_id", "-")),
                _format_float(row.get("recall_at_10")),
                _format_float(row.get("mrr")),
                _format_float(row.get("ndcg_at_5")),
                _format_float(row.get("end_to_end_latency_ms")),
                str(row.get("status", "ok")),
            ]
        )

    lines: list[str] = []
    lines.append("# Final Evaluation Report")
    lines.append("")
    lines.append("## Run Metadata")
    lines.append("")
    lines.append(f"- Run ID: `{run_metadata.get('run_id', '-')}`")
    lines.append(f"- Started at (UTC): `{run_metadata.get('started_at_utc', '-')}`")
    lines.append(f"- Finished at (UTC): `{run_metadata.get('finished_at_utc', '-')}`")
    lines.append(f"- Golden set: `{run_metadata.get('golden_set_path', '-')}`")
    lines.append(f"- Total queries: `{run_metadata.get('total_queries', 0)}`")
    lines.append(f"- Successful queries: `{run_metadata.get('successful_queries', 0)}`")
    lines.append("")

    lines.append("## Aggregate Metrics")
    lines.append("")
    lines.append(_table(["Metric", "Value"], aggregate_rows))
    lines.append("")

    lines.append("## Per-Query Summary")
    lines.append("")
    lines.append(_table(["query_id", "Recall@10", "MRR", "NDCG@5", "E2E latency(ms)", "status"], query_rows))
    lines.append("")

    lines.append("## Rerank Delta Summary")
    lines.append("")
    lines.append(f"- NDCG@5 (reranked): `{_format_float(rerank_eval.get('ndcg_at_5'))}`")
    lines.append(f"- MRR delta: `{_format_float(rerank_eval.get('mrr_delta'))}`")
    lines.append(f"- Top-1 improvement rate: `{_format_float(rerank_eval.get('top1_improvement_rate'))}`")
    lines.append(f"- Added latency (ms): `{_format_float(rerank_eval.get('added_latency_ms'))}`")
    gate = rerank_eval.get("gate") if isinstance(rerank_eval.get("gate"), dict) else {}
    lines.append(f"- Gate enabled this run: `{gate.get('enabled_this_run', '-')}`")
    lines.append(f"- Gate reason: `{gate.get('reason', '-')}`")
    lines.append("")

    lines.append("## Agent Quality Summary")
    lines.append("")
    lines.append(f"- LLM-as-Judge agreement: `{_format_float(agent_eval.get('llm_as_judge_agreement'))}`")
    lines.append(f"- LLM explanation quality: `{_format_float(agent_eval.get('llm_explanation_quality_score'))}`")
    lines.append(f"- LLM explanation groundedness: `{_format_float(agent_eval.get('llm_explanation_groundedness_score'))}`")
    lines.append(f"- Explanation presence rate: `{_format_float(agent_eval.get('explanation_presence_rate'))}`")
    lines.append(f"- Explanation groundedness (heuristic): `{_format_float(agent_eval.get('groundedness_score'))}`")
    lines.append(f"- Dimension consistency (heuristic): `{_format_float(agent_eval.get('dimension_consistency_score'))}`")
    lines.append("")

    lines.append("## Latency/Cost Summary")
    lines.append("")
    lines.append(f"- End-to-end latency p50/p95/p99 (ms): `{_format_float(performance_eval.get('end_to_end_latency', {}).get('p50_ms'))}` / `{_format_float(performance_eval.get('end_to_end_latency', {}).get('p95_ms'))}` / `{_format_float(performance_eval.get('end_to_end_latency', {}).get('p99_ms'))}`")
    lines.append(f"- Stage latency (retrieval p95 ms): `{_format_float(performance_eval.get('stage_latency', {}).get('retrieval_ms', {}).get('p95_ms'))}`")
    lines.append(f"- Total tokens/request: `{_format_float(performance_eval.get('total_tokens_per_request'))}`")
    lines.append(f"- Estimated cost/request (USD): `{_format_float(performance_eval.get('estimated_cost_per_request_usd'))}`")
    lines.append(f"- Candidates/sec: `{_format_float(performance_eval.get('candidates_per_sec'))}`")
    lines.append("")

    lines.append("## Known Limitations")
    lines.append("")
    if known_limitations:
        for item in known_limitations:
            lines.append(f"- {item}")
    else:
        lines.append("- No additional limitations were recorded in this run.")
    lines.append("")

    lines.append("## Next Actions")
    lines.append("")
    if next_actions:
        for item in next_actions:
            lines.append(f"1. {item}")
    else:
        lines.append("1. No immediate follow-up actions were recorded.")

    return "\n".join(lines) + "\n"


def write_final_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
