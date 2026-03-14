from pathlib import Path
import sys

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from domain_agents.culture_agent import CultureAgentInput, CultureAgentOutput
from domain_agents.experience_agent import ExperienceAgentInput, ExperienceAgentOutput
from domain_agents.orchestrator import CandidateContext, OrchestratorRequest
from domain_agents.ranking_agent import RankingAgentInput, RankingAgentOutput, RankingBreakdown
from domain_agents.skill_agent import SkillAgentInput, SkillAgentOutput
from domain_agents.technical_agent import TechnicalAgentInput, TechnicalAgentOutput


JOB_DESCRIPTION = "Looking for a senior data engineer with Python, SQL, and large-scale ETL ownership."


def test_orchestrator_request_contract():
    request = OrchestratorRequest(
        job_description=JOB_DESCRIPTION,
        top_k=5,
        candidates=[
            CandidateContext(
                candidate_id="cand-1",
                summary="Data engineer with strong ETL background.",
                skills=["python", "sql"],
            )
        ],
    )

    assert request.top_k == 5
    assert request.candidates[0].candidate_id == "cand-1"


def test_skill_agent_contract():
    payload = SkillAgentInput(
        candidate_id="cand-1",
        job_description=JOB_DESCRIPTION,
        required_skills=["python", "sql"],
        candidate_skills=["python", "sql", "airflow"],
    )
    output = SkillAgentOutput(score=0.9, matched_skills=["python", "sql"])
    assert payload.candidate_id == "cand-1"
    assert output.score == pytest.approx(0.9)


def test_experience_agent_contract():
    payload = ExperienceAgentInput(
        candidate_id="cand-1",
        job_description=JOB_DESCRIPTION,
        required_experience_years=5.0,
        candidate_experience_years=6.0,
    )
    output = ExperienceAgentOutput(score=0.85, experience_fit=1.0, seniority_fit=0.8)
    assert payload.required_experience_years == pytest.approx(5.0)
    assert output.seniority_fit == pytest.approx(0.8)


def test_technical_agent_contract():
    payload = TechnicalAgentInput(
        candidate_id="cand-1",
        job_description=JOB_DESCRIPTION,
        required_stack=["python", "sql"],
        candidate_skills=["python", "sql", "spark"],
    )
    output = TechnicalAgentOutput(score=0.8, stack_coverage=1.0, depth_signal=0.6)
    assert "spark" in payload.candidate_skills
    assert output.stack_coverage == pytest.approx(1.0)


def test_culture_agent_contract():
    payload = CultureAgentInput(
        candidate_id="cand-1",
        job_description=JOB_DESCRIPTION,
        target_signals=["ownership", "collaboration"],
        candidate_signals=["ownership"],
    )
    output = CultureAgentOutput(score=0.7, alignment=0.7, potential_score=0.65, potential_level="emerging")
    assert payload.target_signals[0] == "ownership"
    assert output.score == pytest.approx(0.7)
    assert output.potential_score == pytest.approx(0.65)


def test_ranking_agent_contract():
    payload = RankingAgentInput(
        candidate_id="cand-1",
        skill_score=0.9,
        experience_score=0.8,
        technical_score=0.75,
        culture_score=0.7,
    )
    output = RankingAgentOutput(
        final_score=0.81,
        breakdown=RankingBreakdown(
            skill=0.9,
            experience=0.8,
            technical=0.75,
            culture=0.7,
            weighted_score=0.81,
        ),
        explanation="Strong technical and skill alignment.",
    )
    assert payload.weights.skill == pytest.approx(0.35)
    assert output.breakdown.weighted_score == pytest.approx(0.81)


def test_agent_contract_rejects_out_of_range_scores():
    with pytest.raises(ValidationError):
        SkillAgentOutput(score=1.5)
