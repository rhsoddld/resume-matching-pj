from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.regen_golden_set import CandidateEvidence, _grade_for, _select_candidates


def test_grade_for_overlap_prefers_high_overlap_at_top_rank() -> None:
    assert _grade_for(0.8, rank=0) == 3
    assert _grade_for(0.55, rank=2) == 2
    assert _grade_for(0.2, rank=1) == 1


def test_select_candidates_applies_primary_and_relaxed_thresholds() -> None:
    rows = [
        CandidateEvidence(
            candidate_id="c1",
            required_overlap=0.45,
            optional_overlap=0.0,
            matched_required=["python"],
            matched_optional=[],
            fusion_score=0.5,
            quality_score=0.4,
            rank=0,
        ),
        CandidateEvidence(
            candidate_id="c2",
            required_overlap=0.26,
            optional_overlap=0.3,
            matched_required=["sql"],
            matched_optional=["tableau"],
            fusion_score=0.6,
            quality_score=0.29,
            rank=1,
        ),
        CandidateEvidence(
            candidate_id="c3",
            required_overlap=0.22,
            optional_overlap=0.0,
            matched_required=[],
            matched_optional=[],
            fusion_score=0.9,
            quality_score=0.2,
            rank=2,
        ),
    ]

    selected = _select_candidates(
        rows,
        max_golden=5,
        min_required_overlap=0.4,
        relaxed_required_overlap=0.25,
        relaxed_min_quality=0.24,
    )

    selected_ids = [row.candidate_id for row in selected]
    assert "c1" in selected_ids  # primary threshold
    assert "c2" in selected_ids  # relaxed threshold
    assert "c3" not in selected_ids  # below relaxed threshold
