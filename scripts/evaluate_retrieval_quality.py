#!/usr/bin/env python3
"""Retrieval Quality Measurement (5-2: HCR.1-3).

Measures precision@k and recall@k for the hybrid retriever using
golden_set.jsonl's expected_skills as ground truth.

Usage:
    source .venv/bin/activate
    set -a && source .env && set +a
    PYTHONPATH=src python scripts/evaluate_retrieval_quality.py --top-k 10
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

GOLDEN_SET = ROOT / "src" / "eval" / "golden_set.jsonl"
REPORT_MD = ROOT / "docs" / "eval" / "retrieval-quality.md"
REPORT_JSON = ROOT / "docs" / "eval" / "retrieval-quality.json"


def _load_golden() -> list[dict]:
    entries = []
    with open(GOLDEN_SET) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _compute_overlap(
    retrieved_skills: list[str],
    expected_skills: list[str],
) -> tuple[float, float]:
    """Returns (precision@k, recall@k) based on skill overlap."""
    if not expected_skills:
        return 0.0, 0.0
    retrieved_set = {s.strip().lower() for s in retrieved_skills}
    expected_set = {s.strip().lower() for s in expected_skills}
    hits = len(retrieved_set & expected_set)
    precision = hits / len(retrieved_set) if retrieved_set else 0.0
    recall = hits / len(expected_set)
    return round(precision, 4), round(recall, 4)


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure retrieval quality against golden set")
    parser.add_argument("--top-k", type=int, default=10, help="Top-k candidates to retrieve")
    parser.add_argument("--label-filter", default="good", help="Only evaluate this label (default: good)")
    args = parser.parse_args()

    from backend.repositories.hybrid_retriever import HybridRetriever
    from backend.services.job_profile_extractor import build_job_profile

    retriever = HybridRetriever()

    entries = _load_golden()
    if args.label_filter:
        entries = [e for e in entries if e.get("expected_label") == args.label_filter]
        print(f"Evaluating {len(entries)} '{args.label_filter}' entries (out of {len(_load_golden())} total)")

    results = []
    precision_sum = 0.0
    recall_sum = 0.0

    for i, entry in enumerate(entries, 1):
        jd = entry.get("job_description") or entry.get("query", "")
        expected_skills = [s.strip().lower() for s in (entry.get("expected_skills") or [])]
        if not jd or not expected_skills:
            continue

        try:
            job_profile = build_job_profile(jd, None)
            hits = retriever.search_candidates(
                job_description=jd,
                job_profile=job_profile,
                top_k=args.top_k,
                category=None,
            )
        except Exception as exc:
            print(f"  [{i}] ERROR: {exc}")
            continue

        # Collect all retrieved skills from top-k candidates (via MongoDB follow-up)
        from backend.core.database import get_collection
        candidate_ids = [h["candidate_id"] for h in hits if h.get("candidate_id")]
        docs = list(
            get_collection("candidates").find(
                {"candidate_id": {"$in": candidate_ids}},
                {"candidate_id": 1, "parsed.skills": 1, "parsed.normalized_skills": 1, "parsed.core_skills": 1, "_id": 0},
            )
        )
        retrieved_skills: list[str] = []
        for doc in docs:
            parsed = doc.get("parsed") or {}
            for key in ("skills", "normalized_skills", "core_skills"):
                retrieved_skills.extend(parsed.get(key) or [])

        precision, recall = _compute_overlap(retrieved_skills, expected_skills)
        precision_sum += precision
        recall_sum += recall
        results.append({
            "id": entry.get("id"),
            "label": entry.get("expected_label"),
            "precision_at_k": precision,
            "recall_at_k": recall,
            "expected_skill_count": len(expected_skills),
            "retrieved_candidate_count": len(hits),
        })
        print(f"  [{i}/{len(entries)}] id={entry.get('id')} precision@{args.top_k}={precision:.3f} recall@{args.top_k}={recall:.3f}")

    n = len(results)
    avg_precision = round(precision_sum / n, 4) if n else 0.0
    avg_recall = round(recall_sum / n, 4) if n else 0.0
    f1 = round(2 * avg_precision * avg_recall / (avg_precision + avg_recall), 4) if (avg_precision + avg_recall) else 0.0

    summary = {
        "run_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "top_k": args.top_k,
        "label_filter": args.label_filter,
        "evaluated_entries": n,
        "avg_precision_at_k": avg_precision,
        "avg_recall_at_k": avg_recall,
        "f1_at_k": f1,
        "target_overlap_at_k": 0.50,
        "target_met": avg_recall >= 0.50,
        "results": results,
    }

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    # Write markdown report
    lines = [
        "# Retrieval Quality Report",
        "",
        f"- Run at (UTC): `{summary['run_at']}`",
        f"- Top-k: `{args.top_k}`",
        f"- Label filter: `{args.label_filter}`",
        f"- Evaluated entries: `{n}`",
        "",
        "## KPI Summary",
        "",
        "| Metric | Value | Target | Status |",
        "|---|---|---|---|",
        f"| avg precision@{args.top_k} | {avg_precision:.4f} | — | — |",
        f"| avg recall@{args.top_k} | {avg_recall:.4f} | ≥ 0.50 | {'✅ MET' if avg_recall >= 0.50 else '❌ MISS'} |",
        f"| F1@{args.top_k} | {f1:.4f} | — | — |",
        "",
        "## Per-Entry Results",
        "",
        f"| ID | Label | precision@{args.top_k} | recall@{args.top_k} |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['id']} | {r['label']} | {r['precision_at_k']:.4f} | {r['recall_at_k']:.4f} |")

    lines += [
        "",
        "## Interpretation",
        "",
        "- **recall@k**: fraction of expected skills found in top-k retrieved candidates' skill pools",
        "- **precision@k**: fraction of retrieved skills that overlap with expected skills",
        "- Target: recall@k ≥ 0.50 (improvement path: tune fusion weights via `RETRIEVAL_VECTOR_WEIGHT`, `RETRIEVAL_KEYWORD_WEIGHT`, `RETRIEVAL_METADATA_WEIGHT`)",
    ]

    REPORT_MD.write_text("\n".join(lines))
    print(f"\nDone: avg_precision@{args.top_k}={avg_precision:.4f} | avg_recall@{args.top_k}={avg_recall:.4f} | F1={f1:.4f}")
    print(f"Target recall≥0.50: {'✅ MET' if avg_recall >= 0.50 else '❌ MISS — adjust fusion weights'}")
    print(f"Report: {REPORT_MD}")


if __name__ == "__main__":
    main()
