#!/usr/bin/env python3
"""Generate retrieval benchmark archive with CI-safe fallback output."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SCRIPT = ROOT / "scripts" / "benchmark_retrieval.py"
OUTPUT_JSON = ROOT / "docs" / "eval" / "retrieval-benchmark.json"
OUTPUT_MD = ROOT / "docs" / "eval" / "retrieval-benchmark.md"


def _write_fallback_report(*, return_code: int, stderr_text: str) -> None:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    stderr_preview = (stderr_text or "").strip()
    if len(stderr_preview) > 2000:
        stderr_preview = f"{stderr_preview[:2000]}\n...(truncated)"

    report: dict[str, Any] = {
        "generated_at_utc": generated_at,
        "status": "degraded",
        "reason": "Benchmark execution failed in CI environment.",
        "return_code": return_code,
        "summary": {
            "queries": 0,
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "success_rate": 0.0,
            "total_returned_candidates": 0,
            "benchmark_elapsed_sec": 0.0,
            "successful_call_elapsed_sec_sum": 0.0,
            "candidates_per_sec": 0.0,
            "calls_per_sec": 0.0,
            "latency_ms": {
                "mean": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "max": 0.0,
            },
        },
        "errors": [{"error": stderr_preview}] if stderr_preview else [{"error": "No stderr captured."}],
    }

    markdown = (
        "# Retrieval Benchmark\n\n"
        f"- Generated at (UTC): `{generated_at}`\n"
        "- Status: `degraded`\n"
        f"- Reason: `benchmark command failed (exit={return_code})`\n\n"
        "## Notes\n\n"
        "- This archive was generated automatically in CI with fallback mode.\n"
        "- Benchmark depends on runtime infra (MongoDB/Milvus); check workflow logs for environment issues.\n\n"
        "## Raw Summary JSON\n\n"
        "```json\n"
        f"{json.dumps(report['summary'], indent=2, ensure_ascii=False)}\n"
        "```\n"
    )

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(markdown, encoding="utf-8")


def main() -> int:
    command = [
        sys.executable,
        str(BENCHMARK_SCRIPT),
        "--query-limit",
        "5",
        "--iterations",
        "1",
        "--warmup-rounds",
        "0",
        "--workers",
        "1",
        "--top-k",
        "20",
        "--output-json",
        str(OUTPUT_JSON),
        "--output-md",
        str(OUTPUT_MD),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)

    if completed.returncode == 0:
        if completed.stdout:
            print(completed.stdout.strip())
        return 0

    _write_fallback_report(return_code=completed.returncode, stderr_text=completed.stderr)
    print("Benchmark command failed; fallback archive written.", file=sys.stderr)
    if completed.stderr:
        print(completed.stderr.strip(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
