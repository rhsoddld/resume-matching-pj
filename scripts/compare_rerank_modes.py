#!/usr/bin/env python3
"""Compare shortlist baseline vs LLM rerank over a small golden-set sample."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.core.providers import get_skill_ontology  # noqa: E402
from backend.core.model_routing import resolve_rerank_model  # noqa: E402
from backend.core.settings import settings  # noqa: E402
from backend.repositories.hybrid_retriever import HybridRetriever  # noqa: E402
from backend.services.candidate_enricher import enrich_hits  # noqa: E402
from backend.services.cross_encoder_rerank_service import cross_encoder_rerank_service  # noqa: E402
from backend.services.job_profile_extractor import build_job_profile  # noqa: E402


DEFAULT_INPUT = ROOT / "src" / "eval" / "golden_set.jsonl"
DEFAULT_JSON_OUTPUT = ROOT / "docs" / "eval" / "llm-rerank-comparison.json"
DEFAULT_MD_OUTPUT = ROOT / "docs" / "eval" / "llm-rerank-comparison.md"


def _load_entries(path: Path, limit: int | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not payload.get("job_description"):
            continue
        rows.append(payload)
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return rows


def _candidate_skills(candidate_doc: dict[str, Any]) -> set[str]:
    parsed = candidate_doc.get("parsed")
    parsed = parsed if isinstance(parsed, dict) else {}
    values: set[str] = set()
    for field in ("normalized_skills", "core_skills", "expanded_skills", "skills"):
        raw = parsed.get(field) or []
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str) and item.strip():
                values.add(item.strip().lower())
    return values


def _overlap_ratio(expected_skills: set[str], candidate_doc: dict[str, Any]) -> float:
    if not expected_skills:
        return 0.0
    candidate_skills = _candidate_skills(candidate_doc)
    if not candidate_skills:
        return 0.0
    matched = expected_skills.intersection(candidate_skills)
    return len(matched) / float(len(expected_skills))


def _summarize_mode(items: list[tuple[dict[str, Any], dict[str, Any]]], expected_skills: set[str]) -> dict[str, Any]:
    top_ids = [str(hit.get("candidate_id")) for hit, _ in items]
    overlaps = [round(_overlap_ratio(expected_skills, doc), 4) for _, doc in items]
    return {
        "top_candidate_ids": top_ids,
        "top1_overlap": overlaps[0] if overlaps else 0.0,
        "avg_overlap_at_k": round(sum(overlaps) / len(overlaps), 4) if overlaps else 0.0,
        "max_overlap_at_k": max(overlaps) if overlaps else 0.0,
        "overlap_scores": overlaps,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    agg = report["aggregate"]
    rows = []
    for case in report["cases"]:
        rows.append(
            "| `{id}` | `{family}` | `{base}` | `{llm}` | `{shift}` | `{lat}` |".format(
                id=case["id"],
                family=case.get("job_family") or "unknown",
                base=case["baseline"]["avg_overlap_at_k"],
                llm=case["llm_rerank"]["avg_overlap_at_k"],
                shift=case["delta"]["avg_overlap_at_k"],
                lat=case["llm_rerank_latency_ms"],
            )
        )
    table = "\n".join(rows) if rows else "| - | - | - | - | - | - |"
    return (
        "# LLM Rerank Comparison\n\n"
        "이 문서는 `HCR.3` 강화를 위한 `LLM rerank on/off` 비교 실험 결과를 정리한다.\n\n"
        "## Experiment Goal\n\n"
        "- baseline shortlist와 `LLM rerank` shortlist를 같은 입력에 대해 비교한다.\n"
        "- 품질 지표는 `expected_skills` 대비 후보 skill overlap의 proxy score를 사용한다.\n"
        "- 이 점수는 최종 relevance의 완전한 대체는 아니며, shortlist refinement 경향을 보기 위한 lightweight proxy다.\n\n"
        "## Run Metadata\n\n"
        f"- Generated at (UTC): `{report['generated_at_utc']}`\n"
        f"- Input dataset: `{report['config']['input_path']}`\n"
        f"- Query count: `{report['config']['query_count']}`\n"
        f"- top_k: `{report['config']['top_k']}`\n"
        f"- rerank_top_n: `{report['config']['rerank_top_n']}`\n"
        f"- rerank model: `{report['config']['rerank_model']}`\n\n"
        f"- rerank model version: `{report['config']['rerank_model_version']}`\n\n"
        "## Aggregate Summary\n\n"
        "| Metric | Value |\n"
        "|---|---|\n"
        f"| Baseline avg overlap@k | `{agg['baseline_avg_overlap_at_k']}` |\n"
        f"| LLM rerank avg overlap@k | `{agg['llm_avg_overlap_at_k']}` |\n"
        f"| Delta avg overlap@k | `{agg['delta_avg_overlap_at_k']}` |\n"
        f"| Baseline avg top1 overlap | `{agg['baseline_avg_top1_overlap']}` |\n"
        f"| LLM rerank avg top1 overlap | `{agg['llm_avg_top1_overlap']}` |\n"
        f"| Delta avg top1 overlap | `{agg['delta_avg_top1_overlap']}` |\n"
        f"| Reordered cases | `{agg['reordered_cases']}` / `{agg['case_count']}` |\n"
        f"| Avg LLM rerank latency (ms) | `{agg['avg_llm_rerank_latency_ms']}` |\n\n"
        "## Case Summary\n\n"
        "| Query | Family | Baseline avg@k | LLM avg@k | Delta | LLM latency ms |\n"
        "|---|---|---:|---:|---:|---:|\n"
        f"{table}\n\n"
        "## Interpretation\n\n"
        "- `Delta avg overlap@k`가 양수면 expected skill proxy 기준으로 shortlist 품질이 개선된 것이다.\n"
        "- `Reordered cases`가 0보다 크면 LLM rerank가 실제로 shortlist 순서를 바꿨음을 뜻한다.\n"
        "- latency는 rerank 단계 추가 비용이므로, timeout/fallback 정책과 함께 해석해야 한다.\n\n"
        "## Raw Aggregate JSON\n\n"
        "```json\n"
        f"{json.dumps(agg, indent=2, ensure_ascii=False)}\n"
        "```\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare baseline shortlist vs LLM rerank.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--query-limit", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rerank-top-n", type=int, default=20)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD_OUTPUT)
    args = parser.parse_args()

    entries = _load_entries(args.input, args.query_limit)
    ontology = get_skill_ontology()
    retriever = HybridRetriever()

    original_mode = settings.rerank_mode
    original_top_n = settings.rerank_top_n
    settings.rerank_mode = "llm"
    settings.rerank_top_n = args.rerank_top_n

    cases: list[dict[str, Any]] = []
    try:
        for entry in entries:
            job_description = str(entry.get("job_description") or "").strip()
            expected_skills = {
                str(skill).strip().lower()
                for skill in (entry.get("expected_skills") or [])
                if isinstance(skill, str) and skill.strip()
            }
            job_profile = build_job_profile(
                job_description=job_description,
                ontology=ontology,
                category_override=None,
                min_experience_years=None,
                education_override=None,
                region_override=None,
                industry_override=None,
            )
            retrieval_top_n = max(args.top_k, args.rerank_top_n)
            hits = retriever.search_candidates(
                job_description=job_description,
                job_profile=job_profile,
                top_k=retrieval_top_n,
                category=None,
                min_experience_years=None,
            )
            enriched_hits = enrich_hits(hits, min_experience_years=None, education=None, region=None, industry=None)
            baseline = enriched_hits[: args.top_k]

            started = time.perf_counter()
            llm_reranked = cross_encoder_rerank_service.rerank(
                job_description=job_description,
                enriched_hits=enriched_hits,
                top_k=args.top_k,
                model_override=resolve_rerank_model(high_quality=True).model,
            )
            llm_latency_ms = round((time.perf_counter() - started) * 1000.0, 3)

            baseline_summary = _summarize_mode(baseline, expected_skills)
            llm_summary = _summarize_mode(llm_reranked, expected_skills)
            reordered = baseline_summary["top_candidate_ids"] != llm_summary["top_candidate_ids"]
            cases.append(
                {
                    "id": str(entry.get("id") or f"case-{len(cases) + 1}"),
                    "job_family": entry.get("job_family"),
                    "baseline": baseline_summary,
                    "llm_rerank": llm_summary,
                    "llm_rerank_latency_ms": llm_latency_ms,
                    "delta": {
                        "avg_overlap_at_k": round(
                            llm_summary["avg_overlap_at_k"] - baseline_summary["avg_overlap_at_k"], 4
                        ),
                        "top1_overlap": round(
                            llm_summary["top1_overlap"] - baseline_summary["top1_overlap"], 4
                        ),
                    },
                    "reordered": reordered,
                }
            )
    finally:
        settings.rerank_mode = original_mode
        settings.rerank_top_n = original_top_n

    case_count = len(cases)
    aggregate = {
        "case_count": case_count,
        "baseline_avg_overlap_at_k": round(
            sum(case["baseline"]["avg_overlap_at_k"] for case in cases) / case_count, 4
        )
        if case_count
        else 0.0,
        "llm_avg_overlap_at_k": round(
            sum(case["llm_rerank"]["avg_overlap_at_k"] for case in cases) / case_count, 4
        )
        if case_count
        else 0.0,
        "delta_avg_overlap_at_k": round(sum(case["delta"]["avg_overlap_at_k"] for case in cases) / case_count, 4)
        if case_count
        else 0.0,
        "baseline_avg_top1_overlap": round(
            sum(case["baseline"]["top1_overlap"] for case in cases) / case_count, 4
        )
        if case_count
        else 0.0,
        "llm_avg_top1_overlap": round(
            sum(case["llm_rerank"]["top1_overlap"] for case in cases) / case_count, 4
        )
        if case_count
        else 0.0,
        "delta_avg_top1_overlap": round(sum(case["delta"]["top1_overlap"] for case in cases) / case_count, 4)
        if case_count
        else 0.0,
        "reordered_cases": sum(1 for case in cases if case["reordered"]),
        "avg_llm_rerank_latency_ms": round(
            sum(case["llm_rerank_latency_ms"] for case in cases) / case_count, 3
        )
        if case_count
        else 0.0,
    }

    report = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "input_path": str(args.input),
            "query_count": case_count,
            "top_k": args.top_k,
            "rerank_top_n": args.rerank_top_n,
            "rerank_model": resolve_rerank_model(high_quality=True).model,
            "rerank_model_version": resolve_rerank_model(high_quality=True).version,
        },
        "aggregate": aggregate,
        "cases": cases,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    args.output_md.write_text(_render_markdown(report), encoding="utf-8")
    print(f"Generated {args.output_json}")
    print(f"Generated {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
