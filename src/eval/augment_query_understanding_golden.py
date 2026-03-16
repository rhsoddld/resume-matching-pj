from __future__ import annotations

"""
Utility to augment query_understanding_golden_set.jsonl
using existing strict retrieval golden_set.jsonl.

Idea:
- We already trust strict golden_set for end-to-end eval.
- For families that tend to be harder (fullstack / ml_ai / qa / business_analyst / senior_architect),
  we add query-understanding golden rows derived from those JDs.

This makes query_understanding tests cover more realistic / difficult JDs
without touching the retrieval golden itself.
"""

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT / "src" / "eval"
STRICT_GOLDEN = EVAL_DIR / "golden_set.jsonl"
QU_GOLDEN = EVAL_DIR / "query_understanding_golden_set.jsonl"
QU_BACKUP = EVAL_DIR / "query_understanding_golden_set.backup.jsonl"


HARD_FAMILIES = {
    "fullstack",
    "ml_ai",
    "qa_test_automation",
    "business_analyst",
    "senior_architect",
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _family_from_job_family(job_family: str | None) -> str:
    jf = (job_family or "").strip().lower()
    if not jf:
        return "unknown"
    if jf in {
        "backend",
        "frontend",
        "fullstack",
        "cloud_devops",
        "junior_software",
        "senior_architect",
        "qa_test_automation",
        "ml_ai",
        "data_analyst",
        "business_analyst",
    }:
        return jf
    # fallback mapping for legacy names
    if "backend" in jf:
        return "backend"
    if "frontend" in jf:
        return "frontend"
    if "devops" in jf or "cloud" in jf:
        return "cloud_devops"
    if "qa" in jf or "test" in jf:
        return "qa_test_automation"
    if "ml" in jf or "ai" in jf or "data" in jf:
        return "ml_ai"
    if "analyst" in jf:
        return "business_analyst"
    return jf


def build_qu_case_from_strict(row: dict[str, Any]) -> dict[str, Any]:
    qid = str(row.get("query_id") or row.get("id") or "").strip()
    job_desc = str(row.get("job_description") or "")
    job_family = _family_from_job_family(row.get("job_family"))

    expected_role = str(row.get("expected_role") or "").strip()
    exp_roles = [expected_role] if expected_role else []
    exp_skills = [str(s).strip() for s in (row.get("expected_skills") or []) if str(s).strip()]

    # Use relatively strict but not harsh thresholds;
    # we want the parser to have reasonable signal density and confidence.
    max_unknown_ratio = 0.55
    min_confidence = 0.65

    return {
        "id": f"qd-from-{qid}",
        "family": job_family,
        "job_description": job_desc,
        "expected_roles": exp_roles,
        "expected_skills": exp_skills,
        "expected_capabilities": [],
        "expected_strengths": {},
        "max_unknown_ratio": max_unknown_ratio,
        "min_confidence": min_confidence,
    }


def main() -> None:
    strict_rows = _load_jsonl(STRICT_GOLDEN)
    qu_rows = _load_jsonl(QU_GOLDEN)
    existing_ids = {str(r.get("id") or "") for r in qu_rows}

    # Backup existing query-understanding golden
    if QU_GOLDEN.exists() and not QU_BACKUP.exists():
        QU_GOLDEN.rename(QU_BACKUP)

    added: list[dict[str, Any]] = []
    for row in strict_rows:
        family = _family_from_job_family(row.get("job_family"))
        if family not in HARD_FAMILIES:
            continue
        qid = str(row.get("query_id") or row.get("id") or "").strip()
        qu_id = f"qd-from-{qid}"
        if qu_id in existing_ids:
            continue
        case = build_qu_case_from_strict(row)
        added.append(case)
        existing_ids.add(qu_id)

    all_rows = qu_rows + added
    _dump_jsonl(QU_GOLDEN, all_rows)

    print(f"Augmented query_understanding_golden_set.jsonl with {len(added)} new cases.")


if __name__ == "__main__":
    main()

