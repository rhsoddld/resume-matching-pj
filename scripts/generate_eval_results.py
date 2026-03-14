#!/usr/bin/env python3
"""Generate markdown archive for eval metrics and optional LLM-as-Judge runs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.eval_metrics import (  # noqa: E402
    build_diversity_report,
    build_synthetic_candidate,
    extract_culture_targets,
    extract_expected_skills,
    extract_min_experience_years,
    score_culture_fit,
    score_custom_quality,
    score_experience_fit,
    score_potential_fit,
    score_skill_coverage,
)


GOLDEN_SET_PATH = ROOT / "src" / "eval" / "golden_set.jsonl"
RUBRIC_PATH = ROOT / "docs" / "eval" / "llm_judge_softskill_potential_rubric.md"
OUTPUT_PATH = ROOT / "docs" / "eval" / "eval-results.md"


def _load_golden_set() -> list[dict[str, Any]]:
    if not GOLDEN_SET_PATH.exists():
        return []
    lines = GOLDEN_SET_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _avg(rows: list[dict[str, Any]], *, key: str, label: str) -> float:
    vals = [float(r[key]) for r in rows if str(r.get("label")) == label]
    if not vals:
        return 0.0
    return sum(vals) / float(len(vals))


def _compute_custom_eval(entries: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        candidate = build_synthetic_candidate(entry)
        expected_skills = extract_expected_skills(entry)
        required_exp = extract_min_experience_years(str(entry.get("job_description") or ""))
        target_culture = extract_culture_targets(entry)

        skill_score = score_skill_coverage(expected_skills, candidate["candidate_skills"])
        experience_score = score_experience_fit(required_exp, candidate["candidate_experience_years"])
        culture_score = score_culture_fit(
            target_signals=target_culture,
            candidate_signals=candidate["candidate_culture_signals"],
            candidate_summary=candidate["candidate_summary"],
        )
        potential_score = score_potential_fit(
            job_description=str(entry.get("job_description") or ""),
            candidate_summary=candidate["candidate_summary"],
            candidate_signals=candidate["candidate_culture_signals"],
        )
        quality_score = score_custom_quality(
            skill_score=skill_score,
            experience_score=experience_score,
            culture_score=culture_score,
            potential_score=potential_score,
        )

        rows.append(
            {
                "id": entry.get("id"),
                "label": str(entry.get("expected_label") or "neutral").lower(),
                "skill_score": skill_score,
                "experience_score": experience_score,
                "culture_score": culture_score,
                "potential_score": potential_score,
                "quality_score": quality_score,
            }
        )

    report = {
        "counts": {
            "good": len([r for r in rows if r["label"] == "good"]),
            "neutral": len([r for r in rows if r["label"] == "neutral"]),
            "bad": len([r for r in rows if r["label"] == "bad"]),
        },
        "by_label_avg": {
            "good": {
                "skill": round(_avg(rows, key="skill_score", label="good"), 4),
                "experience": round(_avg(rows, key="experience_score", label="good"), 4),
                "culture": round(_avg(rows, key="culture_score", label="good"), 4),
                "potential": round(_avg(rows, key="potential_score", label="good"), 4),
                "quality": round(_avg(rows, key="quality_score", label="good"), 4),
            },
            "neutral": {
                "skill": round(_avg(rows, key="skill_score", label="neutral"), 4),
                "experience": round(_avg(rows, key="experience_score", label="neutral"), 4),
                "culture": round(_avg(rows, key="culture_score", label="neutral"), 4),
                "potential": round(_avg(rows, key="potential_score", label="neutral"), 4),
                "quality": round(_avg(rows, key="quality_score", label="neutral"), 4),
            },
            "bad": {
                "skill": round(_avg(rows, key="skill_score", label="bad"), 4),
                "experience": round(_avg(rows, key="experience_score", label="bad"), 4),
                "culture": round(_avg(rows, key="culture_score", label="bad"), 4),
                "potential": round(_avg(rows, key="potential_score", label="bad"), 4),
                "quality": round(_avg(rows, key="quality_score", label="bad"), 4),
            },
        },
    }
    return report


def _read_rubric() -> str:
    if RUBRIC_PATH.exists():
        return RUBRIC_PATH.read_text(encoding="utf-8")
    return ""


def _run_optional_llm_judge(entries: list[dict[str, Any]]) -> dict[str, Any]:
    if not os.getenv("OPENAI_API_KEY"):
        return {"status": "skipped", "reason": "OPENAI_API_KEY not set"}

    try:
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    except Exception as exc:  # pragma: no cover
        return {"status": "skipped", "reason": f"deepeval import failed: {exc}"}

    rubric = _read_rubric().strip()
    if not rubric:
        return {"status": "skipped", "reason": "rubric not found"}

    metric = GEval(
        name="CulturePotentialFit",
        criteria=rubric,
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.6,
    )

    scores: list[dict[str, Any]] = []
    for entry in entries[:3]:
        candidate = build_synthetic_candidate(entry)
        output = (
            f"Candidate summary: {candidate['candidate_summary']} "
            f"Signals: {', '.join(sorted(candidate['candidate_culture_signals'])) or 'none'}."
        )
        test_case = LLMTestCase(
            input=str(entry.get("job_description") or ""),
            actual_output=output,
            expected_output=f"label={entry.get('expected_label', 'neutral')}",
        )
        metric.measure(test_case)
        scores.append(
            {
                "id": entry.get("id"),
                "label": entry.get("expected_label"),
                "score": round(float(metric.score or 0.0), 4),
            }
        )

    avg_score = round(sum(s["score"] for s in scores) / float(len(scores)), 4) if scores else 0.0
    return {"status": "ok", "sample_size": len(scores), "average_score": avg_score, "samples": scores}


def _git_commit() -> str:
    sha = os.getenv("GITHUB_SHA", "").strip()
    if sha:
        return sha[:12]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _render_markdown(
    *,
    generated_at: str,
    commit: str,
    custom_report: dict[str, Any],
    diversity_report: dict[str, Any],
    llm_report: dict[str, Any],
) -> str:
    return (
        "# Eval Results Archive\n\n"
        f"- Generated at (UTC): `{generated_at}`\n"
        f"- Commit: `{commit}`\n"
        f"- Golden set: `{GOLDEN_SET_PATH.relative_to(ROOT)}`\n"
        f"- Rubric: `{RUBRIC_PATH.relative_to(ROOT)}`\n\n"
        "## Custom Eval (Skill/Experience/Culture/Potential)\n\n"
        "```json\n"
        f"{json.dumps(custom_report, indent=2, ensure_ascii=False)}\n"
        "```\n\n"
        "## Diversity Report\n\n"
        "```json\n"
        f"{json.dumps(diversity_report, indent=2, ensure_ascii=False)}\n"
        "```\n\n"
        "## LLM-as-Judge (Rubric-Based)\n\n"
        "```json\n"
        f"{json.dumps(llm_report, indent=2, ensure_ascii=False)}\n"
        "```\n"
    )


def main() -> int:
    entries = _load_golden_set()
    if not entries:
        raise SystemExit(f"golden set not found or empty: {GOLDEN_SET_PATH}")

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    commit = _git_commit()
    custom_report = _compute_custom_eval(entries)
    diversity_report = build_diversity_report(entries)
    llm_report = _run_optional_llm_judge(entries)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        _render_markdown(
            generated_at=generated_at,
            commit=commit,
            custom_report=custom_report,
            diversity_report=diversity_report,
            llm_report=llm_report,
        ),
        encoding="utf-8",
    )
    print(f"Generated {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
