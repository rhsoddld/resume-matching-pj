from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.schemas.job import JobMatchCandidate, ScoreDetail, SkillOverlapDetail
from backend.services.job_profile_extractor import JobProfile
from backend.services.matching_service import MatchingService


def _candidate(
    candidate_id: str,
    *,
    seniority_level: str = "senior",
    culture_weight: float = 0.12,
    culture_confidence: float = 0.55,
    must_have_match_rate: float = 0.9,
    score: float = 0.8,
) -> JobMatchCandidate:
    return JobMatchCandidate(
        candidate_id=candidate_id,
        category="backend engineer",
        summary="Strong backend engineer profile.",
        skills=["python", "api"],
        normalized_skills=["python", "api"],
        core_skills=["python"],
        expanded_skills=["python", "api", "microservices"],
        experience_years=6.0,
        seniority_level=seniority_level,
        score=score,
        vector_score=0.7,
        skill_overlap=0.8,
        score_detail=ScoreDetail(
            semantic_similarity=0.8,
            experience_fit=0.8,
            seniority_fit=0.8,
            category_fit=0.8,
            must_have_match_rate=must_have_match_rate,
            must_have_penalty=0.0,
        ),
        skill_overlap_detail=SkillOverlapDetail(
            core_overlap=0.8,
            expanded_overlap=0.8,
            normalized_overlap=0.8,
        ),
        agent_scores={
            "weights": {"skill": 0.3, "experience": 0.3, "technical": 0.3, "culture": culture_weight},
            "confidence": {"culture": culture_confidence},
        },
        possible_gaps=[],
    )


def test_fairness_guardrails_add_warning_for_culture_weight_cap():
    service = MatchingService()
    profile = JobProfile(required_skills=["python"], expanded_skills=["python"], required_experience_years=None, preferred_seniority=None)
    candidate = _candidate("cand-1", culture_weight=0.35)

    audit = service._run_fairness_guardrails(
        job_description="Hiring backend engineer with Python and API experience.",
        job_profile=profile,
        matches=[candidate],
        top_k=1,
    )

    assert audit.enabled is True
    assert any(item.code == "culture_weight_over_cap" for item in audit.warnings)
    assert any("Culture weight exceeded fairness cap." in text for text in candidate.bias_warnings)


def test_fairness_guardrails_warn_on_sensitive_terms_in_query():
    service = MatchingService()
    profile = JobProfile(required_skills=["python"], expanded_skills=["python"], required_experience_years=None, preferred_seniority=None)

    audit = service._run_fairness_guardrails(
        job_description="Looking for a young male backend engineer with Python.",
        job_profile=profile,
        matches=[],
        top_k=5,
    )

    warning = next(item for item in audit.warnings if item.code == "sensitive_term_in_query")
    assert warning.severity == "critical"
    assert "young" in warning.metrics["terms"]
    assert "male" in warning.metrics["terms"]


def test_fairness_guardrails_warn_on_seniority_concentration_without_jd_constraint():
    service = MatchingService()
    profile = JobProfile(required_skills=["python"], expanded_skills=["python"], required_experience_years=None, preferred_seniority=None)
    matches = [_candidate(f"cand-{i}", seniority_level="senior") for i in range(6)]

    audit = service._run_fairness_guardrails(
        job_description="Hiring backend engineer with API and cloud exposure.",
        job_profile=profile,
        matches=matches,
        top_k=6,
    )

    assert any(item.code == "seniority_concentration_topk" for item in audit.warnings)
