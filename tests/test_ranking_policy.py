from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domain_agents.culture_agent import CultureAgentOutput
from domain_agents.experience_agent import ExperienceAgentOutput
from domain_agents.orchestrator import CandidateAgentResult
from domain_agents.ranking_agent import AgentWeights, RankingAgentInput, RankingAgentOutput, RankingBreakdown
from domain_agents.skill_agent import SkillAgentOutput
from domain_agents.technical_agent import TechnicalAgentOutput
from domain_agents.weight_negotiation_agent import WeightNegotiationOutput, WeightProposal
from backend.services.job_profile_extractor import JobProfile
from backend.services.match_result_builder import build_match_candidate
from backend.services.scoring_service import compute_final_ranking_score


def test_compute_final_ranking_score_uses_hybrid_policy_when_agent_score_exists():
    score = compute_final_ranking_score(deterministic_score=0.8, agent_weighted_score=0.6)
    assert score == pytest.approx(0.71)


def test_build_match_candidate_applies_agent_weighted_ranking_policy():
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
        }
    }
    job_profile = JobProfile(
        required_skills=["python", "sql"],
        expanded_skills=["python", "sql", "airflow"],
        required_experience_years=5.0,
        preferred_seniority="senior",
    )

    negotiation = WeightNegotiationOutput(
        recruiter=WeightProposal(skill=0.3, experience=0.35, technical=0.2, culture=0.15),
        hiring_manager=WeightProposal(skill=0.4, experience=0.2, technical=0.3, culture=0.1),
        final=WeightProposal(skill=0.35, experience=0.3, technical=0.2, culture=0.15),
        rationale="test",
    )
    agent_result = CandidateAgentResult(
        candidate_id="cand-1",
        skill_output=SkillAgentOutput(score=0.9),
        experience_output=ExperienceAgentOutput(score=0.8, experience_fit=1.0, seniority_fit=0.6),
        technical_output=TechnicalAgentOutput(score=0.7, stack_coverage=0.8, depth_signal=0.6),
        culture_output=CultureAgentOutput(score=0.6, alignment=0.6),
        ranking_input=RankingAgentInput(
            candidate_id="cand-1",
            skill_score=0.9,
            experience_score=0.8,
            technical_score=0.7,
            culture_score=0.6,
            weights=AgentWeights(skill=0.35, experience=0.3, technical=0.2, culture=0.15),
        ),
        ranking_output=RankingAgentOutput(
            final_score=0.78,
            breakdown=RankingBreakdown(skill=0.9, experience=0.8, technical=0.7, culture=0.6, weighted_score=0.78),
            explanation="test explanation",
        ),
        weight_negotiation=negotiation,
    )

    candidate = build_match_candidate(
        hit=hit,
        candidate_doc=candidate_doc,
        job_profile=job_profile,
        category="Data",
        agent_result=agent_result,
    )

    assert candidate.score == pytest.approx(0.84)
    assert candidate.score_detail.rank_policy == "hybrid(deterministic:0.55,agent:0.45,must-have-penalty:max0.25)"
    assert "parsing" in candidate.agent_scores
    assert candidate.agent_scores["weights"]["skill"] == 0.35
    assert candidate.agent_scores["weight_negotiation"]["final"]["experience"] == 0.3


def test_build_match_candidate_exposes_adjacent_skill_score_and_trajectory():
    hit = {
        "candidate_id": "cand-2",
        "score": 0.7,
        "category": "Data",
        "experience_years": 4.0,
        "seniority_level": "mid",
    }
    candidate_doc = {
        "parsed": {
            "summary": "Backend/data engineer with API and orchestration experience.",
            "skills": ["python", "sql", "airflow", "fastapi"],
            "normalized_skills": ["python", "sql", "airflow", "fastapi"],
            "core_skills": ["python", "sql"],
            "expanded_skills": ["python", "sql", "airflow", "fastapi"],
            "experience_items": [
                {"title": "Engineer", "company": "A", "start_date": "2020-01", "end_date": "2021-12"},
                {"title": "Senior Engineer", "company": "B", "start_date": "2022-01", "end_date": "Present"},
            ],
        }
    }
    job_profile = JobProfile(
        required_skills=["python", "sql"],
        expanded_skills=["python", "sql", "airflow", "kafka"],
        related_skills=["airflow", "kafka"],
        required_experience_years=3.0,
        preferred_seniority="mid",
    )

    candidate = build_match_candidate(
        hit=hit,
        candidate_doc=candidate_doc,
        job_profile=job_profile,
        category="Data",
        agent_result=None,
    )

    assert candidate.score_detail.adjacent_skill_score is not None
    assert candidate.score_detail.adjacent_skill_score >= 0.0
    assert "airflow" in candidate.adjacent_skill_matches
    assert candidate.career_trajectory.get("has_trajectory") is True
import pytest
