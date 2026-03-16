from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services.retrieval.hybrid_scoring import (  # noqa: E402
    compute_keyword_score,
    fusion_score,
    metadata_score,
    normalize_token,
)


def test_normalize_token_compacts_spacing_and_separators():
    assert normalize_token("  Data-Science__Lead ") == "data science lead"


def test_compute_keyword_score_uses_skill_overlap():
    parsed = {"skills": ["python", "sql"], "core_skills": ["airflow"]}
    score = compute_keyword_score(parsed=parsed, terms=["python", "airflow", "spark"])
    assert score == 0.6667


def test_fusion_score_respects_weights():
    score = fusion_score(
        vector_score=1.0,
        keyword_score=0.0,
        metadata_score=0.0,
        vector_weight=0.55,
        keyword_weight=0.30,
        metadata_weight=0.15,
    )
    assert score == 0.55


def test_metadata_score_rewards_category_and_experience():
    score = metadata_score(
        category="Data",
        industry=None,
        min_experience_years=5,
        preferred_seniority="senior",
        candidate_category="Data",
        candidate_experience_years=6,
        candidate_seniority_level="senior",
    )
    assert score > 0.9
