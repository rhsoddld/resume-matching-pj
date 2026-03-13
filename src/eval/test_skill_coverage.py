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
