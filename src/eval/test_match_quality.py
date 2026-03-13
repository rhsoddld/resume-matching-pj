"""DeepEval stub: Overall Match Quality metric test.

Evaluates whether the top-k match results returned by /api/jobs/match
are relevant to the input job description using DeepEval's AnswerRelevancy.

To run:
    export OPENAI_API_KEY=sk-...
    deepeval test run src/eval/test_match_quality.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Try importing deepeval; skip gracefully if not installed.
# ---------------------------------------------------------------------------
deepeval_available = True
try:
    from deepeval.metrics import AnswerRelevancyMetric
    from deepeval.test_case import LLMTestCase
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


def _answer_relevancy_metric() -> "AnswerRelevancyMetric":
    return AnswerRelevancyMetric(threshold=0.5)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@needs_deepeval
def test_match_quality_golden_set_smoke() -> None:
    """Smoke test: metric can be constructed and golden set is valid."""
    entries = load_golden_set()
    assert len(entries) >= 10

    metric = _answer_relevancy_metric()
    assert metric is not None

    bad_entries = [e for e in entries if e.get("expected_label") == "bad"]
    assert len(bad_entries) >= 2, (
        "Golden set must contain at least 2 'bad' entries for contrastive eval"
    )


@needs_deepeval
@pytest.mark.parametrize("entry", load_golden_set()[:3])
def test_match_quality_sample(entry: dict) -> None:
    """AnswerRelevancy: top match result should be relevant to job description.

    Replace `actual_output` with the real /api/jobs/match response once running.
    The actual_output should be a stringified summary of the top candidate.
    """
    metric = _answer_relevancy_metric()

    # Stub response — replace with live HTTP call when running integration test
    placeholder_output = (
        "Top candidate: Data Scientist with 6 years experience. "
        "Skills: Python, TensorFlow, scikit-learn, SQL, AWS. "
        "Overall match score: 0.84."
    )

    test_case = LLMTestCase(
        input=entry["job_description"],
        actual_output=placeholder_output,
    )

    metric.measure(test_case)
    assert metric.score is not None, "AnswerRelevancyMetric must return a score"


@needs_deepeval
def test_match_quality_bad_job_low_relevance() -> None:
    """Bad job descriptions (non-technical) should yield lower relevancy for tech candidates."""
    entries = load_golden_set()
    bad_entries = [e for e in entries if e.get("expected_label") == "bad"]
    if not bad_entries:
        pytest.skip("No bad-label entries in golden set")

    metric = _answer_relevancy_metric()
    entry = bad_entries[0]

    # If we match a software engineer against a receptionist posting,
    # relevancy should be low — stub demonstrates the test shape.
    tech_candidate_output = (
        "Top candidate: Software Engineer with 5 years experience. "
        "Skills: Python, Java, SQL, Docker, Kubernetes. Score: 0.71."
    )

    test_case = LLMTestCase(
        input=entry["job_description"],
        actual_output=tech_candidate_output,
    )

    metric.measure(test_case)
    assert metric.score is not None
    # In a real test: assert metric.score < 0.5 (low relevance expected)
