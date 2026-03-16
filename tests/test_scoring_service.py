from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.agents.runtime.helpers import compute_experience_fit  # noqa: E402
from backend.services.job_profile_extractor import JobProfile, QuerySignal  # noqa: E402
from backend.services.match_result_builder import build_match_candidate  # noqa: E402
from backend.services.scoring_service import compute_skill_overlap  # noqa: E402


def test_compute_experience_fit_softens_overqualification_penalty():
    score = compute_experience_fit(
        required_experience_years=4.0,
        candidate_experience_years=12.0,
    )

    assert score == 0.85


def test_build_match_candidate_uses_adjacent_skills_to_soften_must_have_penalty():
    hit = {
        "candidate_id": "cand-soft-skill",
        "score": 0.58,
        "vector_score": 0.58,
        "experience_years": 9.0,
        "seniority_level": "senior",
        "category": "sales",
    }
    candidate_doc = {
        "parsed": {
            "summary": "Sales lead with strong stakeholder management and cross-functional delivery.",
            "skills": ["stakeholder management", "account management", "cross-functional leadership"],
            "normalized_skills": ["stakeholder management", "account management", "cross-functional leadership"],
            "core_skills": ["stakeholder management"],
            "expanded_skills": ["stakeholder management", "cross-functional leadership"],
        }
    }
    strict_profile = JobProfile(
        required_skills=["communication"],
        expanded_skills=["communication"],
        required_experience_years=5.0,
        preferred_seniority="senior",
        related_skills=[],
        skill_signals=[QuerySignal(name="communication", strength="must have", signal_type="skill")],
    )
    lenient_profile = JobProfile(
        required_skills=["communication"],
        expanded_skills=["communication"],
        required_experience_years=5.0,
        preferred_seniority="senior",
        related_skills=["stakeholder management"],
        skill_signals=[QuerySignal(name="communication", strength="must have", signal_type="skill")],
    )

    strict_result = build_match_candidate(
        hit=hit,
        candidate_doc=candidate_doc,
        job_profile=strict_profile,
        category="sales",
        agent_result=None,
        agent_evaluation_applied=False,
        agent_evaluation_reason="test_strict",
    )
    lenient_result = build_match_candidate(
        hit=hit,
        candidate_doc=candidate_doc,
        job_profile=lenient_profile,
        category="sales",
        agent_result=None,
        agent_evaluation_applied=False,
        agent_evaluation_reason="test_lenient",
    )

    assert strict_result.score_detail.must_have_penalty == 0.12
    assert lenient_result.score_detail.must_have_penalty == 0.06
    assert lenient_result.score > strict_result.score


def test_compute_skill_overlap_gives_partial_credit_for_compound_required_skill():
    candidate = {
        "parsed": {
            "core_skills": ["sales support"],
            "expanded_skills": ["sales support", "customer service"],
            "normalized_skills": ["sales", "customer service"],
        }
    }
    job = {
        "required_skills": ["b2b sales support"],
        "expanded_skills": ["b2b sales support", "client management"],
    }

    score, detail = compute_skill_overlap(candidate, job)

    assert score > 0.25
    assert detail["normalized_overlap"] > 0.3


def test_compute_skill_overlap_keeps_unrelated_profile_low():
    candidate = {
        "parsed": {
            "core_skills": ["marketing"],
            "expanded_skills": ["marketing", "branding"],
            "normalized_skills": ["marketing"],
        }
    }
    job = {
        "required_skills": ["b2b sales support"],
        "expanded_skills": ["b2b sales support", "client management"],
    }

    score, detail = compute_skill_overlap(candidate, job)

    assert score < 0.05
    assert detail["normalized_overlap"] == 0.0
