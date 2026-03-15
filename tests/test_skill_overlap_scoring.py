from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services.scoring_service import compute_deterministic_match_score, compute_skill_overlap


def test_skill_overlap_uses_core_expanded_and_normalized_weights():
    candidate = {
        "parsed": {
            "core_skills": ["react"],
            "expanded_skills": ["react", "javascript", "frontend"],
            "normalized_skills": ["react"],
            "capability_phrases": ["team collaboration"],
            "role_candidates": ["frontend engineer"],
        }
    }
    job = {
        "required_skills": ["react", "typescript"],
        "expanded_skills": ["react", "javascript", "frontend", "typescript"],
    }

    score, detail = compute_skill_overlap(candidate, job)

    assert detail["core_overlap"] == pytest.approx(0.5)
    assert detail["expanded_overlap"] == pytest.approx(0.75)
    assert detail["normalized_overlap"] == pytest.approx(0.5)
    assert score == pytest.approx(0.575)


def test_skill_overlap_falls_back_when_core_skills_missing():
    candidate = {
        "parsed": {
            "core_skills": [],
            "expanded_skills": ["javascript"],
            "normalized_skills": ["javascript", "react"],
        }
    }
    job = {
        "required_skills": ["javascript", "react"],
        "expanded_skills": ["javascript", "frontend"],
    }

    score, detail = compute_skill_overlap(candidate, job)

    assert detail["core_overlap"] == pytest.approx(0.0)
    assert detail["expanded_overlap"] == pytest.approx(1.0 / 3.0)
    assert detail["normalized_overlap"] == pytest.approx(1.0)
    assert score == pytest.approx(0.8)


def test_skill_overlap_ignores_capability_and_role_fields_for_scoring():
    candidate = {
        "parsed": {
            "core_skills": [],
            "expanded_skills": [],
            "normalized_skills": [],
            "capability_phrases": ["problem solving"],
            "role_candidates": ["data analyst"],
        }
    }
    job = {"required_skills": ["python"], "expanded_skills": ["python", "data"]}

    score, detail = compute_skill_overlap(candidate, job)

    assert score == pytest.approx(0.0)
    assert detail["core_overlap"] == pytest.approx(0.0)
    assert detail["expanded_overlap"] == pytest.approx(0.0)
    assert detail["normalized_overlap"] == pytest.approx(0.0)


def test_deterministic_score_uses_weighted_components():
    score, detail = compute_deterministic_match_score(
        raw_similarity=0.6,
        skill_overlap=0.8,
        candidate_experience_years=6.0,
        required_experience_years=5.0,
        candidate_seniority="senior",
        preferred_seniority="senior",
        category_matched=True,
    )

    assert detail["semantic_similarity"] == pytest.approx(0.8)
    assert detail["experience_fit"] == pytest.approx(0.96)
    assert detail["seniority_fit"] == pytest.approx(1.0)
    assert detail["category_fit"] == pytest.approx(0.03)
    assert score == pytest.approx(0.8728)


def test_deterministic_score_handles_missing_optional_signals():
    score, detail = compute_deterministic_match_score(
        raw_similarity=-0.2,
        skill_overlap=0.0,
        candidate_experience_years=None,
        required_experience_years=3.0,
        candidate_seniority=None,
        preferred_seniority="lead",
        category_matched=False,
    )

    assert detail["semantic_similarity"] == pytest.approx(0.4)
    assert detail["experience_fit"] == pytest.approx(0.0)
    assert detail["seniority_fit"] == pytest.approx(0.0)
    assert detail["category_fit"] == pytest.approx(0.0)
    assert score == pytest.approx(0.168)
