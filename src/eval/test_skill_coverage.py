"""DeepEval stub: Skill Coverage metric test.

This test is skipped by default because it requires a DEEPEVAL_API_KEY
(or OpenAI key) for the LLM-as-Judge metric.

To run:
    export OPENAI_API_KEY=sk-...
    deepeval test run src/eval/test_skill_coverage.py
    # or: python -m pytest src/eval/test_skill_coverage.py -v -m "not skip_deepeval"
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from eval.eval_metrics import (
    build_synthetic_candidate,
    extract_culture_targets,
    extract_expected_skills,
    extract_min_experience_years,
    score_culture_fit,
    score_experience_fit,
    score_potential_fit,
    score_skill_coverage,
)

# ---------------------------------------------------------------------------
# Try importing deepeval; skip the whole module gracefully if not installed.
# ---------------------------------------------------------------------------
deepeval_available = True
try:
    from deepeval import evaluate  # noqa: F401
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams
except ImportError:
    deepeval_available = False


GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.jsonl"
POTENTIAL_RUBRIC_PATH = Path(__file__).resolve().parents[2] / "docs" / "eval" / "llm_judge_softskill_potential_rubric.md"
SKIP_REASON = (
    "deepeval not installed or OPENAI_API_KEY not set. "
    "Run: pip install deepeval && export OPENAI_API_KEY=sk-..."
)

needs_deepeval = pytest.mark.skipif(
    not deepeval_available or not os.getenv("OPENAI_API_KEY"),
    reason=SKIP_REASON,
)


def load_golden_set() -> list[dict]:
    """Load all entries from golden_set.jsonl."""
    if not GOLDEN_SET_PATH.exists():
        return []
    lines = GOLDEN_SET_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# Metric definition (constructed lazily to avoid import errors when skipped)
# ---------------------------------------------------------------------------
def _skill_coverage_metric() -> "GEval":
    return GEval(
        name="SkillCoverage",
        criteria=(
            "Given the job description and the candidate's matched skills, "
            "evaluate how well the candidate's skills cover the job requirements. "
            "Score 1.0 = full coverage, 0.0 = no relevant skills matched."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        threshold=0.5,
    )


def _load_potential_rubric() -> str:
    if not POTENTIAL_RUBRIC_PATH.exists():
        return (
            "Evaluate soft-skill alignment and potential from JD and candidate summary. "
            "Score 1.0 for clear growth, ownership, collaboration evidence; "
            "score 0.0 when evidence is missing or contradictory."
        )
    return POTENTIAL_RUBRIC_PATH.read_text(encoding="utf-8").strip()


def _culture_potential_metric() -> "GEval":
    rubric = _load_potential_rubric()
    return GEval(
        name="CulturePotentialFit",
        criteria=rubric,
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        threshold=0.6,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@needs_deepeval
def test_skill_coverage_golden_set_smoke() -> None:
    """Smoke test: ensure golden set loads and metric can be constructed."""
    entries = load_golden_set()
    assert len(entries) >= 10, "Golden set must have at least 10 entries"

    metric = _skill_coverage_metric()
    assert metric is not None

    # Just verify the metric can be instantiated — no API call in smoke test
    good_entries = [e for e in entries if e.get("expected_label") == "good"]
    assert len(good_entries) > 0


@needs_deepeval
@pytest.mark.parametrize("entry", load_golden_set()[:3])  # first 3 as sample
def test_skill_coverage_sample(entry: dict) -> None:
    """LLM-as-Judge skill coverage on first 3 golden set entries.

    NOTE: Requires live OpenAI API call. Use sparingly.
    Replace `actual_output` with a real API call to /api/jobs/match
    once the server is running.
    """
    metric = _skill_coverage_metric()

    # Placeholder actual_output — replace with real match call in CI/CD
    placeholder_output = (
        "[STUB] Matched skills: python, machine learning, pytorch. "
        "Missing: aws, cloud deployment."
    )

    test_case = LLMTestCase(
        input=entry["job_description"],
        actual_output=placeholder_output,
        expected_output=f"label={entry['expected_label']}",
    )

    metric.measure(test_case)
    # Log score but don't assert in stub — only verify metric executes
    assert metric.score is not None, "GEval metric must return a score"


@needs_deepeval
@pytest.mark.parametrize("entry", load_golden_set()[:3])  # first 3 as sample
def test_llm_judge_softskill_potential_sample(entry: dict) -> None:
    """R2.4: LLM-as-Judge metric for soft-skill/potential using fixed rubric."""
    metric = _culture_potential_metric()
    candidate = build_synthetic_candidate(entry)
    summary = candidate["candidate_summary"]
    output = (
        f"Candidate summary: {summary} "
        f"Signals: {', '.join(sorted(candidate['candidate_culture_signals'])) or 'none'}."
    )
    test_case = LLMTestCase(
        input=entry["job_description"],
        actual_output=output,
        expected_output=f"label={entry['expected_label']}",
    )
    metric.measure(test_case)
    assert metric.score is not None, "CulturePotentialFit metric must return a score"


def test_custom_eval_skill_experience_culture_release_gate() -> None:
    """R2.2: custom deterministic metrics with dedicated culture-fit gate."""
    entries = load_golden_set()
    assert len(entries) >= 10

    rows: list[dict] = []
    for entry in entries:
        candidate = build_synthetic_candidate(entry)
        expected_skills = extract_expected_skills(entry)
        required_exp = extract_min_experience_years(entry["job_description"])
        target_culture = extract_culture_targets(entry)

        skill_score = score_skill_coverage(expected_skills, candidate["candidate_skills"])
        exp_score = score_experience_fit(required_exp, candidate["candidate_experience_years"])
        culture_score = score_culture_fit(
            target_signals=target_culture,
            candidate_signals=candidate["candidate_culture_signals"],
            candidate_summary=candidate["candidate_summary"],
        )
        potential_score = score_potential_fit(
            job_description=entry["job_description"],
            candidate_summary=candidate["candidate_summary"],
            candidate_signals=candidate["candidate_culture_signals"],
        )

        rows.append(
            {
                "id": entry.get("id"),
                "label": str(entry.get("expected_label") or "neutral").lower(),
                "skill_score": skill_score,
                "experience_score": exp_score,
                "culture_score": culture_score,
                "potential_score": potential_score,
                "culture_targets": sorted(target_culture),
            }
        )

    def _avg(key: str, label: str) -> float:
        vals = [float(r[key]) for r in rows if r["label"] == label]
        if not vals:
            return 0.0
        return sum(vals) / float(len(vals))

    by_label = {
        "good": {
            "skill": round(_avg("skill_score", "good"), 4),
            "experience": round(_avg("experience_score", "good"), 4),
            "culture": round(_avg("culture_score", "good"), 4),
            "potential": round(_avg("potential_score", "good"), 4),
        },
        "neutral": {
            "skill": round(_avg("skill_score", "neutral"), 4),
            "experience": round(_avg("experience_score", "neutral"), 4),
            "culture": round(_avg("culture_score", "neutral"), 4),
            "potential": round(_avg("potential_score", "neutral"), 4),
        },
        "bad": {
            "skill": round(_avg("skill_score", "bad"), 4),
            "experience": round(_avg("experience_score", "bad"), 4),
            "culture": round(_avg("culture_score", "bad"), 4),
            "potential": round(_avg("potential_score", "bad"), 4),
        },
    }
    print("custom_eval_report=" + json.dumps(by_label, ensure_ascii=False))

    assert by_label["good"]["skill"] >= 0.70, "skill coverage gate failed for good set"
    assert by_label["good"]["experience"] >= 0.80, "experience gate failed for good set"
    assert by_label["bad"]["skill"] <= 0.45, "bad set skill score too high"
    assert by_label["bad"]["experience"] <= 0.65, "bad set experience score too high"

    # Culture-focused strengthening
    assert by_label["good"]["culture"] >= 0.70, "culture-fit gate failed for good set"
    assert by_label["bad"]["culture"] <= 0.50, "bad set culture-fit should remain low"
    assert (by_label["good"]["culture"] - by_label["bad"]["culture"]) >= 0.20, (
        "culture metric separation between good and bad is insufficient"
    )

    # Potential-focused strengthening (R2.4)
    assert by_label["good"]["potential"] >= 0.70, "potential gate failed for good set"
    assert by_label["bad"]["potential"] <= 0.40, "bad set potential score should remain low"
    assert (by_label["good"]["potential"] - by_label["bad"]["potential"]) >= 0.30, (
        "potential metric separation between good and bad is insufficient"
    )
