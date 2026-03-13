from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services.agent_orchestration_service import agent_orchestration_service
from backend.services.job_profile_extractor import JobProfile


def test_agent_orchestration_service_returns_candidate_agent_result():
    job_profile = JobProfile(
        required_skills=["python", "sql"],
        expanded_skills=["python", "sql", "airflow"],
        required_experience_years=5.0,
        preferred_seniority="senior",
    )
    hit = {
        "candidate_id": "cand-1",
        "score": 0.8,
        "category": "Data",
        "experience_years": 6.0,
        "seniority_level": "senior",
    }
    candidate_doc = {
        "parsed": {
            "summary": "Experienced data engineer.",
            "skills": ["python", "sql"],
            "normalized_skills": ["python", "sql"],
            "core_skills": ["python"],
            "expanded_skills": ["python", "sql", "airflow"],
            "capability_phrases": ["ownership", "collaboration"],
        },
        "raw": {"resume_text": "Built ETL pipelines with Python and SQL."},
    }

    result = agent_orchestration_service.run_for_candidate(
        job_description="Looking for a senior data engineer with Python and SQL.",
        job_profile=job_profile,
        hit=hit,
        candidate_doc=candidate_doc,
        category_filter="Data",
    )

    assert result.candidate_id == "cand-1"
    assert 0.0 <= result.skill_output.score <= 1.0
    assert 0.0 <= result.experience_output.score <= 1.0
    assert 0.0 <= result.technical_output.score <= 1.0
    assert 0.0 <= result.culture_output.score <= 1.0
    assert 0.0 <= result.ranking_output.final_score <= 1.0
    assert result.ranking_output.explanation

