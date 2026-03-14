#!/usr/bin/env python3
"""Benchmark hybrid retrieval throughput (candidates/sec) and latency."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import random
from pathlib import Path
import statistics
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.core.providers import get_skill_ontology  # noqa: E402
from backend.repositories.hybrid_retriever import HybridRetriever  # noqa: E402
from backend.services.job_profile_extractor import JobProfile, build_job_profile  # noqa: E402


DEFAULT_INPUT = ROOT / "src" / "eval" / "golden_set.jsonl"
DEFAULT_JSON_OUTPUT = ROOT / "docs" / "eval" / "retrieval-benchmark.json"
DEFAULT_MD_OUTPUT = ROOT / "docs" / "eval" / "retrieval-benchmark.md"


def _load_job_descriptions(path: Path, *, limit: int | None, seed: int) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        job_description = str(payload.get("job_description") or "").strip()
        if not job_description:
            continue
        rows.append(
            {
                "id": str(payload.get("id") or f"query-{len(rows) + 1}"),
                "job_description": job_description,
                "category": payload.get("job_family"),
            }
        )
    if not rows:
        raise SystemExit(f"No valid job descriptions in: {path}")
    if limit is not None and limit > 0:
        rng = random.Random(seed)
        if limit < len(rows):
            rows = rng.sample(rows, k=limit)
    return rows


def _build_profiles(
    *,
    rows: list[dict[str, Any]],
    min_experience_years: float | None,
    category_override: str | None,
) -> list[dict[str, Any]]:
    ontology = get_skill_ontology()
    profiles: list[dict[str, Any]] = []
    for row in rows:
        job_description = str(row["job_description"])
        profile = build_job_profile(
            job_description=job_description,
            ontology=ontology,
            category_override=category_override,
            min_experience_years=min_experience_years,
            education_override=None,
            region_override=None,
            industry_override=None,
        )
        profiles.append(
            {
                "id": row["id"],
                "job_description": job_description,
                "profile": profile,
            }
        )
    return profiles


def _run_single_call(
    *,
    retriever: HybridRetriever,
    query_id: str,
    job_description: str,
    job_profile: JobProfile,
    top_k: int,
    category: str | None,
    min_experience_years: float | None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    error: str | None = None
    result_count = 0
    try:
        hits = retriever.search_candidates(
            job_description=job_description,
            job_profile=job_profile,
            top_k=top_k,
            category=category,
            min_experience_years=min_experience_years,
        )
        result_count = len(hits)
    except Exception as exc:  # pragma: no cover
        error = f"{type(exc).__name__}: {exc}"
    elapsed_sec = time.perf_counter() - started_at
    return {
        "query_id": query_id,
        "elapsed_sec": elapsed_sec,
        "result_count": result_count,
        "error": error,
    }


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    pos = (len(ordered) - 1) * (p / 100.0)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    frac = pos - low
    return ordered[low] + (ordered[high] - ordered[low]) * frac


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    cfg = report["config"]
    latency = summary["latency_ms"]
    error_rows = report.get("errors", [])
    error_counts = Counter(err.get("error", "unknown_error") for err in error_rows if err.get("error"))
    if error_counts:
        error_lines = "\n".join(f"- `{name}`: {count}" for name, count in error_counts.most_common(5))
    else:
        error_lines = "- 없음"

    return (
        "# Retrieval Benchmark\n\n"
        "## Run Metadata\n\n"
        f"- Generated at (UTC): `{report['generated_at_utc']}`\n"
        f"- Input dataset: `{cfg['input_path']}`\n"
        f"- Query count: `{summary['queries']}`\n"
        f"- Iterations: `{cfg['iterations']}`\n"
        f"- Workers: `{cfg['workers']}`\n"
        f"- Warmup rounds: `{cfg['warmup_rounds']}` (calls: `{cfg['warmup_calls']}`)\n"
        f"- top_k: `{cfg['top_k']}`\n"
        f"- Category override: `{cfg['category']}`\n"
        f"- Min experience filter: `{cfg['min_experience_years']}`\n\n"
        "## KPI Summary\n\n"
        "| Metric | Value |\n"
        "|---|---|\n"
        f"| Success rate | `{summary['success_rate']}` |\n"
        f"| Candidates/sec | `{summary['candidates_per_sec']}` |\n"
        f"| Calls/sec | `{summary['calls_per_sec']}` |\n"
        f"| Successful calls | `{summary['successful_calls']}` |\n"
        f"| Failed calls | `{summary['failed_calls']}` |\n"
        f"| Total returned candidates | `{summary['total_returned_candidates']}` |\n"
        f"| Latency mean (ms) | `{latency['mean']}` |\n"
        f"| Latency p50 (ms) | `{latency['p50']}` |\n"
        f"| Latency p95 (ms) | `{latency['p95']}` |\n"
        f"| Latency p99 (ms) | `{latency['p99']}` |\n"
        f"| Latency max (ms) | `{latency['max']}` |\n\n"
        "## Interpretation Guide\n\n"
        "- `success_rate`: 1.0에 가까울수록 안정적입니다. 0.99 미만이면 인프라/의존성 오류를 먼저 점검하세요.\n"
        "- `candidates_per_sec`: 같은 환경/같은 입력셋으로 이전 실행값과 비교해 추세를 보세요.\n"
        "- `p95/p99 latency`: tail 지연 구간입니다. 평균보다 이 값이 먼저 악화되면 부하 병목 신호입니다.\n"
        "- `calls_per_sec`: 동시성(`workers`)과 인프라 상태 영향을 크게 받으므로 단독 지표로 해석하지 마세요.\n\n"
        "## Error Summary (Top)\n\n"
        f"{error_lines}\n\n"
        "## Next Actions Checklist\n\n"
        "- [ ] 이번 실행의 기준선(baseline)을 팀 문서에 기록했다.\n"
        "- [ ] 이전 실행 대비 증감(%)을 기록했다.\n"
        "- [ ] 실패 케이스 원인(Mongo/Milvus/OpenAI/timeout)을 분류했다.\n"
        "- [ ] 재현 커맨드와 환경 정보를 함께 남겼다.\n\n"
        "## Raw Summary JSON\n\n"
        "```json\n"
        f"{json.dumps(summary, indent=2, ensure_ascii=False)}\n"
        "```\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark hybrid retrieval throughput (candidates/sec).")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to JSONL query set.")
    parser.add_argument("--query-limit", type=int, default=None, help="Sample N queries from input.")
    parser.add_argument("--iterations", type=int, default=10, help="How many full rounds to run.")
    parser.add_argument("--warmup-rounds", type=int, default=2, help="Warmup rounds excluded from stats.")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent retrieval workers.")
    parser.add_argument("--top-k", type=int, default=30, help="Retrieval top_k for each call.")
    parser.add_argument("--category", type=str, default=None, help="Override category filter.")
    parser.add_argument("--min-experience-years", type=float, default=None, help="Optional experience filter.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling/shuffling.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON_OUTPUT, help="Where to write JSON report.")
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD_OUTPUT, help="Where to write markdown report.")
    args = parser.parse_args()

    if args.iterations <= 0:
        raise SystemExit("--iterations must be > 0")
    if args.warmup_rounds < 0:
        raise SystemExit("--warmup-rounds must be >= 0")
    if args.workers <= 0:
        raise SystemExit("--workers must be > 0")
    if args.top_k <= 0:
        raise SystemExit("--top-k must be > 0")

    rows = _load_job_descriptions(args.input, limit=args.query_limit, seed=args.seed)
    prepared = _build_profiles(
        rows=rows,
        min_experience_years=args.min_experience_years,
        category_override=args.category,
    )

    retriever = HybridRetriever()
    rng = random.Random(args.seed)

    warmup_calls = 0
    for _ in range(args.warmup_rounds):
        shuffled = list(prepared)
        rng.shuffle(shuffled)
        for item in shuffled:
            _run_single_call(
                retriever=retriever,
                query_id=item["id"],
                job_description=item["job_description"],
                job_profile=item["profile"],
                top_k=args.top_k,
                category=args.category,
                min_experience_years=args.min_experience_years,
            )
            warmup_calls += 1

    runs: list[dict[str, Any]] = []
    bench_started = time.perf_counter()
    for _ in range(args.iterations):
        shuffled = list(prepared)
        rng.shuffle(shuffled)
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [
                executor.submit(
                    _run_single_call,
                    retriever=retriever,
                    query_id=item["id"],
                    job_description=item["job_description"],
                    job_profile=item["profile"],
                    top_k=args.top_k,
                    category=args.category,
                    min_experience_years=args.min_experience_years,
                )
                for item in shuffled
            ]
            for fut in as_completed(futures):
                runs.append(fut.result())
    bench_elapsed = time.perf_counter() - bench_started

    successful = [r for r in runs if r["error"] is None]
    failed = [r for r in runs if r["error"] is not None]
    latencies = [float(r["elapsed_sec"]) for r in successful]
    total_returned = int(sum(int(r["result_count"]) for r in successful))
    total_success_elapsed = float(sum(latencies))
    candidates_per_sec = (float(total_returned) / total_success_elapsed) if total_success_elapsed > 0 else 0.0
    calls_per_sec = (float(len(successful)) / bench_elapsed) if bench_elapsed > 0 else 0.0

    report = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "input_path": str(args.input),
            "query_limit": args.query_limit,
            "iterations": args.iterations,
            "warmup_rounds": args.warmup_rounds,
            "warmup_calls": warmup_calls,
            "workers": args.workers,
            "top_k": args.top_k,
            "category": args.category,
            "min_experience_years": args.min_experience_years,
            "seed": args.seed,
        },
        "summary": {
            "queries": len(prepared),
            "total_calls": len(runs),
            "successful_calls": len(successful),
            "failed_calls": len(failed),
            "success_rate": round(float(len(successful)) / float(len(runs)) if runs else 0.0, 4),
            "total_returned_candidates": total_returned,
            "benchmark_elapsed_sec": round(bench_elapsed, 6),
            "successful_call_elapsed_sec_sum": round(total_success_elapsed, 6),
            "candidates_per_sec": round(candidates_per_sec, 4),
            "calls_per_sec": round(calls_per_sec, 4),
            "latency_ms": {
                "mean": round((statistics.mean(latencies) * 1000.0) if latencies else 0.0, 3),
                "p50": round(_percentile(latencies, 50) * 1000.0, 3),
                "p95": round(_percentile(latencies, 95) * 1000.0, 3),
                "p99": round(_percentile(latencies, 99) * 1000.0, 3),
                "max": round((max(latencies) * 1000.0) if latencies else 0.0, 3),
            },
        },
        "errors": [
            {
                "query_id": r["query_id"],
                "error": r["error"],
            }
            for r in failed[:20]
        ],
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.output_md.write_text(_render_markdown(report), encoding="utf-8")

    print(f"Benchmark complete: {len(successful)}/{len(runs)} calls succeeded")
    print(f"Candidates/sec: {report['summary']['candidates_per_sec']}")
    print(f"Calls/sec: {report['summary']['calls_per_sec']}")
    print(f"JSON report: {args.output_json}")
    print(f"Markdown report: {args.output_md}")

    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
