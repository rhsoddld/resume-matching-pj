from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.culture_agent import CultureAgentInput, CultureAgentOutput
from agents.experience_agent import ExperienceAgentInput, ExperienceAgentOutput
from agents.orchestrator import CandidateAgentResult
from agents.ranking_agent import RankingAgentInput, RankingAgentOutput, RankingBreakdown
from agents.skill_agent import SkillAgentInput, SkillAgentOutput
from agents.technical_agent import TechnicalAgentInput, TechnicalAgentOutput
from backend.services.job_profile_extractor import JobProfile


@dataclass
class AgentOrchestrationService:
    """
    Phase 2 scaffold adapter:
    - fixes I/O wiring between matching pipeline and agent contracts
    - returns deterministic placeholder outputs until real SDK calls are integrated
    """

    def run_for_candidate(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        hit: dict[str, Any],
        candidate_doc: dict[str, Any],
        category_filter: str | None,
    ) -> CandidateAgentResult:
        parsed = candidate_doc.get("parsed", {})
        parsed = parsed if isinstance(parsed, dict) else {}

        candidate_id = str(hit.get("candidate_id", ""))
        candidate_skills = list(parsed.get("skills", []) or [])
        candidate_normalized_skills = list(parsed.get("normalized_skills", []) or [])
        candidate_core_skills = list(parsed.get("core_skills", []) or [])
        candidate_expanded_skills = list(parsed.get("expanded_skills", []) or [])
        raw_resume_text = ((candidate_doc.get("raw") or {}).get("resume_text")) if isinstance(candidate_doc.get("raw"), dict) else None

        skill_input = SkillAgentInput(
            candidate_id=candidate_id,
            job_description=job_description,
            required_skills=job_profile.required_skills,
            preferred_skills=job_profile.expanded_skills,
            candidate_skills=candidate_skills,
            candidate_normalized_skills=candidate_normalized_skills,
            candidate_core_skills=candidate_core_skills,
            candidate_expanded_skills=candidate_expanded_skills,
            candidate_summary=parsed.get("summary"),
            raw_resume_text=raw_resume_text,
        )
        skill_score = self._compute_skill_score(skill_input.required_skills, skill_input.candidate_normalized_skills)
        skill_output = SkillAgentOutput(
            score=skill_score,
            matched_skills=sorted(set(skill_input.required_skills).intersection(skill_input.candidate_normalized_skills)),
            missing_skills=sorted(set(skill_input.required_skills).difference(skill_input.candidate_normalized_skills)),
            rationale="Scaffold score from required-vs-normalized skill overlap.",
        )

        experience_input = ExperienceAgentInput(
            candidate_id=candidate_id,
            job_description=job_description,
            required_experience_years=job_profile.required_experience_years,
            preferred_seniority=job_profile.preferred_seniority,
            candidate_experience_years=hit.get("experience_years"),
            candidate_seniority_level=hit.get("seniority_level"),
            candidate_summary=parsed.get("summary"),
            raw_resume_text=raw_resume_text,
        )
        experience_fit = self._compute_experience_fit(
            required_experience_years=experience_input.required_experience_years,
            candidate_experience_years=experience_input.candidate_experience_years,
        )
        seniority_fit = self._compute_seniority_fit(
            preferred_seniority=experience_input.preferred_seniority,
            candidate_seniority=experience_input.candidate_seniority_level,
        )
        experience_output = ExperienceAgentOutput(
            score=round((experience_fit + seniority_fit) / 2.0, 4),
            experience_fit=experience_fit,
            seniority_fit=seniority_fit,
            rationale="Scaffold score from experience-year and seniority heuristics.",
        )

        technical_input = TechnicalAgentInput(
            candidate_id=candidate_id,
            job_description=job_description,
            required_stack=job_profile.required_skills,
            preferred_stack=job_profile.expanded_skills,
            candidate_skills=candidate_normalized_skills,
            candidate_summary=parsed.get("summary"),
            raw_resume_text=raw_resume_text,
        )
        stack_coverage = self._compute_skill_score(technical_input.required_stack, technical_input.candidate_skills)
        depth_signal = round(min(1.0, stack_coverage * 0.8 + float(hit.get("score", 0.0)) * 0.2), 4)
        technical_output = TechnicalAgentOutput(
            score=round((stack_coverage + depth_signal) / 2.0, 4),
            stack_coverage=stack_coverage,
            depth_signal=depth_signal,
            rationale="Scaffold score from stack coverage blended with vector similarity.",
        )

        category_match = bool(category_filter and hit.get("category") == category_filter)
        culture_input = CultureAgentInput(
            candidate_id=candidate_id,
            job_description=job_description,
            target_signals=["communication", "collaboration", "ownership"],
            candidate_signals=list(parsed.get("capability_phrases", []) or []),
            candidate_summary=parsed.get("summary"),
            raw_resume_text=raw_resume_text,
        )
        culture_alignment = 0.75 if category_match else 0.6
        culture_output = CultureAgentOutput(
            score=round(culture_alignment, 4),
            alignment=round(culture_alignment, 4),
            rationale="Scaffold score from category alignment baseline.",
        )

        ranking_input = RankingAgentInput(
            candidate_id=candidate_id,
            skill_score=skill_output.score,
            experience_score=experience_output.score,
            technical_score=technical_output.score,
            culture_score=culture_output.score,
            vector_score=round(float(hit.get("score", 0.0)), 4),
            deterministic_score=None,
        )
        weighted_score = self._compute_weighted_score(ranking_input)
        ranking_output = RankingAgentOutput(
            final_score=weighted_score,
            breakdown=RankingBreakdown(
                skill=ranking_input.skill_score,
                experience=ranking_input.experience_score,
                technical=ranking_input.technical_score,
                culture=ranking_input.culture_score,
                weighted_score=weighted_score,
            ),
            explanation="Scaffold ranking output from weighted domain-agent scores.",
        )

        return CandidateAgentResult(
            candidate_id=candidate_id,
            skill_output=skill_output,
            experience_output=experience_output,
            technical_output=technical_output,
            culture_output=culture_output,
            ranking_input=ranking_input,
            ranking_output=ranking_output,
        )

    @staticmethod
    def _compute_skill_score(required_skills: list[str], candidate_skills: list[str]) -> float:
        required = {item.strip().lower() for item in required_skills if item}
        if not required:
            return 0.0
        candidate = {item.strip().lower() for item in candidate_skills if item}
        return round(len(required.intersection(candidate)) / len(required), 4)

    @staticmethod
    def _compute_experience_fit(*, required_experience_years: float | None, candidate_experience_years: float | None) -> float:
        if required_experience_years is None:
            return 0.5
        if candidate_experience_years is None:
            return 0.0
        if required_experience_years <= 0:
            return 1.0
        return round(min(1.0, candidate_experience_years / required_experience_years), 4)

    @staticmethod
    def _compute_seniority_fit(*, preferred_seniority: str | None, candidate_seniority: str | None) -> float:
        if preferred_seniority is None:
            return 0.5
        if candidate_seniority is None:
            return 0.0
        return 1.0 if preferred_seniority.strip().lower() == candidate_seniority.strip().lower() else 0.4

    @staticmethod
    def _compute_weighted_score(ranking_input: RankingAgentInput) -> float:
        weighted = (
            ranking_input.skill_score * ranking_input.weights.skill
            + ranking_input.experience_score * ranking_input.weights.experience
            + ranking_input.technical_score * ranking_input.weights.technical
            + ranking_input.culture_score * ranking_input.weights.culture
        )
        return round(min(1.0, max(0.0, weighted)), 4)


agent_orchestration_service = AgentOrchestrationService()

