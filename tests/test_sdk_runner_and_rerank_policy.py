from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.agents.contracts.culture_agent import CultureAgentOutput  # noqa: E402
from backend.agents.contracts.experience_agent import ExperienceAgentOutput  # noqa: E402
from backend.agents.contracts.skill_agent import SkillAgentOutput  # noqa: E402
from backend.agents.contracts.technical_agent import TechnicalAgentOutput  # noqa: E402
from backend.agents.contracts.weight_negotiation_agent import WeightProposal  # noqa: E402
from backend.agents.runtime.helpers import build_grounded_ranking_explanation  # noqa: E402
from backend.agents.runtime.models import ScorePackOutput, ViewpointProposalOutput  # noqa: E402
from backend.agents.runtime.sdk_runner import (  # noqa: E402
    _coerce_score_pack_output,
    _coerce_skill_output,
    _coerce_weight_negotiation_output,
)
from backend.agents.runtime.sdk_runtime import should_try_agents_sdk  # noqa: E402
from backend.services.job_profile_extractor import JobProfile  # noqa: E402
from backend.services.match_result_builder import build_match_candidate  # noqa: E402
from backend.services.matching.rerank_policy import should_apply_rerank  # noqa: E402


def test_coerce_skill_output_fills_missing_score_from_overlap():
    output = _coerce_skill_output(
        {
            "matched_skills": ["python", "sql"],
            "missing_skills": ["tableau", "dbt"],
            "evidence": ["Built SQL dashboards."],
            "rationale": "Partial match.",
        }
    )

    assert isinstance(output, SkillAgentOutput)
    assert output.score == 0.5
    assert output.matched_skills == ["python", "sql"]
    assert output.missing_skills == ["tableau", "dbt"]


def test_coerce_weight_negotiation_accepts_viewpoint_output():
    score_pack = ScorePackOutput(
        skill_output=SkillAgentOutput(score=0.7, matched_skills=["python"], missing_skills=[], evidence=[], rationale=""),
        experience_output=ExperienceAgentOutput(
            score=0.6,
            experience_fit=0.6,
            seniority_fit=0.6,
            career_trajectory={},
            evidence=[],
            rationale="",
        ),
        technical_output=TechnicalAgentOutput(
            score=0.5,
            stack_coverage=0.5,
            depth_signal=0.5,
            evidence=[],
            rationale="",
        ),
        culture_output=CultureAgentOutput(
            score=0.4,
            alignment=0.4,
            potential_score=0.0,
            potential_level="unknown",
            risk_flags=[],
            evidence=[],
            potential_evidence=[],
            rationale="",
        ),
        ranking_explanation="pack explanation",
    )
    payload = {
        "job_profile": {
            "required_skills": ["python", "sql"],
            "required_experience_years": 3.0,
        }
    }
    raw_output = ViewpointProposalOutput(
        proposal={"skill": 0.4, "experience": 0.3, "technical": 0.2, "culture": 0.1},
        rationale="single viewpoint only",
    )

    negotiation = _coerce_weight_negotiation_output(
        raw_output=raw_output,
        payload=payload,
        score_pack=score_pack,
    )

    assert negotiation.final.skill == 0.4
    assert negotiation.final.experience == 0.3
    assert negotiation.ranking_explanation == "pack explanation"
    assert negotiation.recruiter == negotiation.final
    assert negotiation.hiring_manager == negotiation.final


def test_coerce_score_pack_output_backfills_missing_sections():
    skill_output = SkillAgentOutput(
        score=0.7,
        matched_skills=["aws"],
        missing_skills=["argocd"],
        evidence=[],
        rationale="",
    )
    experience_output = ExperienceAgentOutput(
        score=0.6,
        experience_fit=0.6,
        seniority_fit=0.6,
        career_trajectory={},
        evidence=[],
        rationale="",
    )
    technical_output = TechnicalAgentOutput(
        score=0.8,
        stack_coverage=0.8,
        depth_signal=0.8,
        evidence=[],
        rationale="",
    )
    culture_output = CultureAgentOutput(
        score=0.5,
        alignment=0.5,
        potential_score=0.0,
        potential_level="unknown",
        risk_flags=[],
        evidence=[],
        potential_evidence=[],
        rationale="",
    )

    score_pack = _coerce_score_pack_output(
        raw_output={
            "skill_output": {"matched_skills": ["aws"], "missing_skills": ["argocd"]},
            "experience_output": {"experience_fit": 0.6, "seniority_fit": 0.6},
            "ranking_explanation": "fallback-safe pack",
        },
        skill_output=skill_output,
        experience_output=experience_output,
        technical_output=technical_output,
        culture_output=culture_output,
    )

    assert score_pack.skill_output.score == 0.5
    assert score_pack.experience_output.score == 0.6
    assert score_pack.technical_output == technical_output
    assert score_pack.culture_output == culture_output
    assert score_pack.ranking_explanation == "fallback-safe pack"


def test_should_apply_rerank_skips_confident_query_with_strong_top_hit():
    job_profile = JobProfile(
        required_skills=["python", "sql"],
        expanded_skills=[],
        required_experience_years=None,
        preferred_seniority=None,
        confidence=0.9,
        signal_quality={"unknown_ratio": 0.0},
    )
    enriched_hits = [
        (
            {"fusion_score": 0.52, "score": 0.52},
            {"parsed": {"normalized_skills": ["python", "sql", "airflow"]}},
        ),
        (
            {"fusion_score": 0.51, "score": 0.51},
            {"parsed": {"normalized_skills": ["python"]}},
        ),
    ]

    should_apply, reason = should_apply_rerank(
        job_profile=job_profile,
        enriched_hits=enriched_hits,
        top_k=5,
    )

    assert should_apply is False
    assert reason == "strong_top_hit_without_query_ambiguity"


def test_should_apply_rerank_requires_ambiguous_query_and_tight_gap():
    job_profile = JobProfile(
        required_skills=["python", "sql"],
        expanded_skills=[],
        required_experience_years=None,
        preferred_seniority=None,
        confidence=0.5,
        signal_quality={"unknown_ratio": 0.7},
    )
    enriched_hits = [
        (
            {"fusion_score": 0.505, "score": 0.505},
            {"parsed": {"normalized_skills": ["excel"]}},
        ),
        (
            {"fusion_score": 0.5, "score": 0.5},
            {"parsed": {"normalized_skills": ["power bi"]}},
        ),
    ]

    should_apply, reason = should_apply_rerank(
        job_profile=job_profile,
        enriched_hits=enriched_hits,
        top_k=5,
    )

    assert should_apply is True
    assert reason == "tight_top_scores_and_ambiguous_query"


def test_should_try_agents_sdk_disabled_in_eval_context(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RESUME_MATCHING_EVAL_MODE", "agent")
    assert should_try_agents_sdk() is False


def test_build_grounded_ranking_explanation_includes_literal_skill_tokens():
    explanation = build_grounded_ranking_explanation(
        payload={
            "job_profile": {"required_skills": ["aws", "terraform", "kubernetes", "linux"]},
            "candidate": {
                "skill_input": {"candidate_normalized_skills": ["aws", "terraform", "ec2", "cloudwatch"]},
                "technical_input": {"candidate_skills": ["aws", "terraform", "ec2", "cloudwatch"]},
            },
        },
        skill_output=SkillAgentOutput(
            score=0.9,
            matched_skills=["aws", "terraform", "kubernetes"],
            missing_skills=["linux"],
            evidence=[],
            rationale="",
        ),
        experience_output=ExperienceAgentOutput(
            score=0.8,
            experience_fit=0.8,
            seniority_fit=0.8,
            career_trajectory={},
            evidence=[],
            rationale="",
        ),
        technical_output=TechnicalAgentOutput(
            score=0.85,
            stack_coverage=0.85,
            depth_signal=0.85,
            evidence=[],
            rationale="",
        ),
        culture_output=CultureAgentOutput(
            score=0.6,
            alignment=0.6,
            potential_score=0.0,
            potential_level="unknown",
            risk_flags=[],
            evidence=[],
            potential_evidence=[],
            rationale="",
        ),
        final_weights=WeightProposal(skill=0.3, experience=0.2, technical=0.4, culture=0.1),
    )

    assert "matched required skills:" in explanation.lower()
    assert "aws" in explanation.lower()
    assert "terraform" in explanation.lower()
    assert "candidate evidence tokens:" in explanation.lower()
    assert "cloudwatch" in explanation.lower()


def test_build_match_candidate_adds_deterministic_explanation_outside_agent_scope():
    job_profile = JobProfile(
        required_skills=["python", "sql", "docker"],
        expanded_skills=["backend", "api"],
        required_experience_years=3.0,
        preferred_seniority="mid",
    )
    hit = {
        "candidate_id": "cand-1",
        "score": 0.62,
        "vector_score": 0.62,
        "experience_years": 4.0,
        "seniority_level": "mid",
        "category": "backend",
    }
    candidate_doc = {
        "parsed": {
            "summary": "Backend engineer with API and data experience.",
            "skills": ["Python", "SQL", "Docker", "FastAPI"],
            "normalized_skills": ["python", "sql", "docker", "fastapi"],
            "core_skills": ["python", "sql"],
            "expanded_skills": ["backend", "api", "docker"],
        }
    }

    result = build_match_candidate(
        hit=hit,
        candidate_doc=candidate_doc,
        job_profile=job_profile,
        category="backend",
        agent_result=None,
        agent_evaluation_applied=False,
        agent_evaluation_reason="outside_agent_eval_top_n(4)",
    )

    assert result.agent_scores["runtime_mode"] == "deterministic_only"
    assert result.agent_explanation is not None
    assert "matched required skills:" in result.agent_explanation.lower()
    assert "candidate evidence tokens:" in result.agent_explanation.lower()
    assert "python" in result.agent_explanation.lower()
