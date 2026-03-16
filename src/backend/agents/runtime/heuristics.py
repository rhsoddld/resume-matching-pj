from __future__ import annotations

from typing import Any

from backend.services.job_profile_extractor import JobProfile
from backend.agents.contracts.culture_agent import CultureAgentOutput
from backend.agents.contracts.experience_agent import ExperienceAgentOutput
from backend.agents.contracts.skill_agent import SkillAgentOutput
from backend.agents.contracts.technical_agent import TechnicalAgentOutput

from .candidate_mapper import build_career_trajectory
from .helpers import (
    build_grounded_ranking_explanation,
    build_fallback_weight_negotiation,
    compute_experience_fit,
    compute_seniority_fit,
    compute_skill_score,
    extract_evidence_sentences,
)
from .types import AgentExecutionResult, CandidateInputBundle


def run_heuristic_agents(
    *,
    bundle: CandidateInputBundle,
    hit: dict[str, Any],
    job_profile: JobProfile,
    category_filter: str | None,
    runtime_reason: str = "",
) -> AgentExecutionResult:
    skill_input = bundle.skill_input
    experience_input = bundle.experience_input
    technical_input = bundle.technical_input
    culture_input = bundle.culture_input

    skill_score = compute_skill_score(skill_input.required_skills, skill_input.candidate_normalized_skills)
    matched_skills = sorted(set(skill_input.required_skills).intersection(skill_input.candidate_normalized_skills))
    missing_skills = sorted(set(skill_input.required_skills).difference(skill_input.candidate_normalized_skills))
    skill_evidence = extract_evidence_sentences(
        text=skill_input.raw_resume_text or skill_input.candidate_summary or "",
        terms=[*skill_input.required_skills, *matched_skills],
        limit=4,
    )
    skill_output = SkillAgentOutput(
        score=skill_score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        evidence=skill_evidence or matched_skills[:6],
        rationale="Fallback: required-vs-normalized skill overlap.",
    )

    experience_fit = compute_experience_fit(
        required_experience_years=experience_input.required_experience_years,
        candidate_experience_years=experience_input.candidate_experience_years,
    )
    seniority_fit = compute_seniority_fit(
        preferred_seniority=experience_input.preferred_seniority,
        candidate_seniority=experience_input.candidate_seniority_level,
    )
    career_trajectory = build_career_trajectory(
        parsed=bundle.parsed,
        candidate_experience_years=experience_input.candidate_experience_years,
        candidate_seniority_level=experience_input.candidate_seniority_level,
    )
    experience_evidence = extract_evidence_sentences(
        text=experience_input.raw_resume_text or experience_input.candidate_summary or "",
        terms=[experience_input.preferred_seniority or "", "promotion", "lead", "manager", "senior"],
        limit=4,
    )
    experience_output = ExperienceAgentOutput(
        score=round((experience_fit + seniority_fit) / 2.0, 4),
        experience_fit=experience_fit,
        seniority_fit=seniority_fit,
        career_trajectory=career_trajectory,
        evidence=experience_evidence or (experience_input.candidate_experience_items or [])[:4],
        rationale="Fallback: experience-year and seniority heuristics.",
    )

    stack_coverage = compute_skill_score(technical_input.required_stack, technical_input.candidate_skills)
    depth_signal = round(min(1.0, stack_coverage * 0.8 + float(hit.get("score", 0.0)) * 0.2), 4)
    technical_evidence = extract_evidence_sentences(
        text=technical_input.raw_resume_text or technical_input.candidate_summary or "",
        terms=[
            *technical_input.required_stack,
            "architecture",
            "designed",
            "implemented",
            "optimized",
            "built",
        ],
        limit=4,
    )
    technical_output = TechnicalAgentOutput(
        score=round((stack_coverage + depth_signal) / 2.0, 4),
        stack_coverage=stack_coverage,
        depth_signal=depth_signal,
        evidence=technical_evidence or (technical_input.candidate_projects or [])[:4],
        rationale="Fallback: stack coverage blended with vector similarity.",
    )

    category_match = bool(category_filter and hit.get("category") == category_filter)
    culture_alignment = 0.75 if category_match else 0.6
    culture_output = CultureAgentOutput(
        score=round(culture_alignment, 4),
        alignment=round(culture_alignment, 4),
        risk_flags=[] if category_match else ["indirect-domain-signal"],
        evidence=(culture_input.candidate_signals or [])[:4],
        rationale="Fallback: category alignment baseline with capability phrases.",
    )

    weight_negotiation = build_fallback_weight_negotiation(
        job_profile.required_experience_years,
        job_profile.required_skills,
    )

    return AgentExecutionResult(
        skill_output=skill_output,
        experience_output=experience_output,
        technical_output=technical_output,
        culture_output=culture_output,
        weight_negotiation=weight_negotiation,
        ranking_explanation=build_grounded_ranking_explanation(
            payload={
                "job_profile": {
                    "required_skills": job_profile.required_skills,
                },
                "candidate": {
                    "skill_input": {
                        "candidate_normalized_skills": skill_input.candidate_normalized_skills,
                    },
                    "technical_input": {
                        "candidate_skills": technical_input.candidate_skills,
                    },
                },
            },
            skill_output=skill_output,
            experience_output=experience_output,
            technical_output=technical_output,
            culture_output=culture_output,
            final_weights=weight_negotiation.final,
        ),
        runtime_mode="heuristic",
        runtime_reason=runtime_reason or "heuristic_fallback",
    )
