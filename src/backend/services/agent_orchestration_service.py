from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from typing import Any

from agents.culture_agent import CultureAgentInput, CultureAgentOutput
from agents.experience_agent import ExperienceAgentInput, ExperienceAgentOutput
from agents.orchestrator import CandidateAgentResult
from agents.ranking_agent import AgentWeights, RankingAgentInput, RankingAgentOutput, RankingBreakdown
from agents.skill_agent import SkillAgentInput, SkillAgentOutput
from agents.technical_agent import TechnicalAgentInput, TechnicalAgentOutput
from agents.weight_negotiation_agent import WeightNegotiationOutput, WeightProposal
from backend.core.collections import dedupe_preserve
from backend.core.providers import get_openai_client
from backend.core.settings import settings
from backend.services.job_profile_extractor import JobProfile


logger = logging.getLogger(__name__)


@dataclass
class AgentOrchestrationService:
    """
    Production adapter:
    - runs live OpenAI scoring in a single structured call
    - negotiates Recruiter/HiringManager weights (A2A)
    - falls back to deterministic heuristics on API/runtime errors
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

        experience_input = ExperienceAgentInput(
            candidate_id=candidate_id,
            job_description=job_description,
            required_experience_years=job_profile.required_experience_years,
            preferred_seniority=job_profile.preferred_seniority,
            candidate_experience_years=hit.get("experience_years"),
            candidate_seniority_level=hit.get("seniority_level"),
            candidate_experience_items=self._extract_experience_items(parsed),
            candidate_summary=parsed.get("summary"),
            raw_resume_text=raw_resume_text,
        )

        technical_input = TechnicalAgentInput(
            candidate_id=candidate_id,
            job_description=job_description,
            required_stack=job_profile.required_skills,
            preferred_stack=job_profile.expanded_skills,
            candidate_skills=candidate_normalized_skills,
            candidate_projects=self._extract_project_evidence(parsed),
            candidate_summary=parsed.get("summary"),
            raw_resume_text=raw_resume_text,
        )

        culture_input = CultureAgentInput(
            candidate_id=candidate_id,
            job_description=job_description,
            target_signals=["communication", "collaboration", "ownership"],
            candidate_signals=list(parsed.get("capability_phrases", []) or []),
            candidate_summary=parsed.get("summary"),
            raw_resume_text=raw_resume_text,
        )

        if self._should_use_live_agent_calls():
            live_result = self._run_live_agents(
                job_description=job_description,
                job_profile=job_profile,
                hit=hit,
                skill_input=skill_input,
                experience_input=experience_input,
                technical_input=technical_input,
                culture_input=culture_input,
                category_filter=category_filter,
            )
            if live_result is not None:
                skill_output, experience_output, technical_output, culture_output, weight_negotiation, ranking_explanation = live_result
            else:
                skill_output, experience_output, technical_output, culture_output, weight_negotiation, ranking_explanation = self._run_heuristic_agents(
                    hit=hit,
                    skill_input=skill_input,
                    experience_input=experience_input,
                    technical_input=technical_input,
                    culture_input=culture_input,
                    job_profile=job_profile,
                    category_filter=category_filter,
                )
        else:
            skill_output, experience_output, technical_output, culture_output, weight_negotiation, ranking_explanation = self._run_heuristic_agents(
                hit=hit,
                skill_input=skill_input,
                experience_input=experience_input,
                technical_input=technical_input,
                culture_input=culture_input,
                job_profile=job_profile,
                category_filter=category_filter,
            )

        ranking_input = RankingAgentInput(
            candidate_id=candidate_id,
            skill_score=skill_output.score,
            experience_score=experience_output.score,
            technical_score=technical_output.score,
            culture_score=culture_output.score,
            vector_score=round(float(hit.get("score", 0.0)), 4),
            deterministic_score=None,
            weights=weight_negotiation.final.as_agent_weights(),
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
            explanation=ranking_explanation,
        )

        return CandidateAgentResult(
            candidate_id=candidate_id,
            skill_output=skill_output,
            experience_output=experience_output,
            technical_output=technical_output,
            culture_output=culture_output,
            ranking_input=ranking_input,
            ranking_output=ranking_output,
            weight_negotiation=weight_negotiation,
        )

    def _run_live_agents(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        hit: dict[str, Any],
        skill_input: SkillAgentInput,
        experience_input: ExperienceAgentInput,
        technical_input: TechnicalAgentInput,
        culture_input: CultureAgentInput,
        category_filter: str | None,
    ) -> tuple[
        SkillAgentOutput,
        ExperienceAgentOutput,
        TechnicalAgentOutput,
        CultureAgentOutput,
        WeightNegotiationOutput,
        str,
    ] | None:
        payload = {
            "job_description": job_description,
            "job_profile": {
                "required_skills": job_profile.required_skills,
                "expanded_skills": job_profile.expanded_skills,
                "required_experience_years": job_profile.required_experience_years,
                "preferred_seniority": job_profile.preferred_seniority,
            },
            "retrieval_context": {
                "vector_score": round(float(hit.get("score", 0.0)), 4),
                "category": hit.get("category"),
                "category_filter": category_filter,
                "experience_years": hit.get("experience_years"),
                "seniority_level": hit.get("seniority_level"),
            },
            "candidate": {
                "skill_input": skill_input.model_dump(),
                "experience_input": experience_input.model_dump(),
                "technical_input": technical_input.model_dump(),
                "culture_input": culture_input.model_dump(),
            },
        }

        system_prompt = (
            "You are an agent orchestrator for resume matching. "
            "Simulate SkillAgent, ExperienceAgent, TechnicalAgent, CultureAgent, "
            "plus Recruiter/HiringManager A2A weight negotiation. "
            "Return strict JSON only. "
            "Scores must be between 0 and 1. "
            "Weight proposals must each sum to 1.0. "
            "Keep rationales concise and evidence grounded in candidate/job inputs."
        )
        output_schema = {
            "type": "object",
            "properties": {
                "skill_output": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number"},
                        "matched_skills": {"type": "array", "items": {"type": "string"}},
                        "missing_skills": {"type": "array", "items": {"type": "string"}},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"},
                    },
                    "required": ["score", "matched_skills", "missing_skills", "evidence", "rationale"],
                },
                "experience_output": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number"},
                        "experience_fit": {"type": "number"},
                        "seniority_fit": {"type": "number"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"},
                    },
                    "required": ["score", "experience_fit", "seniority_fit", "evidence", "rationale"],
                },
                "technical_output": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number"},
                        "stack_coverage": {"type": "number"},
                        "depth_signal": {"type": "number"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"},
                    },
                    "required": ["score", "stack_coverage", "depth_signal", "evidence", "rationale"],
                },
                "culture_output": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "number"},
                        "alignment": {"type": "number"},
                        "risk_flags": {"type": "array", "items": {"type": "string"}},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"},
                    },
                    "required": ["score", "alignment", "risk_flags", "evidence", "rationale"],
                },
                "weight_negotiation": {
                    "type": "object",
                    "properties": {
                        "recruiter": {
                            "type": "object",
                            "properties": {
                                "skill": {"type": "number"},
                                "experience": {"type": "number"},
                                "technical": {"type": "number"},
                                "culture": {"type": "number"},
                            },
                            "required": ["skill", "experience", "technical", "culture"],
                        },
                        "hiring_manager": {
                            "type": "object",
                            "properties": {
                                "skill": {"type": "number"},
                                "experience": {"type": "number"},
                                "technical": {"type": "number"},
                                "culture": {"type": "number"},
                            },
                            "required": ["skill", "experience", "technical", "culture"],
                        },
                        "final": {
                            "type": "object",
                            "properties": {
                                "skill": {"type": "number"},
                                "experience": {"type": "number"},
                                "technical": {"type": "number"},
                                "culture": {"type": "number"},
                            },
                            "required": ["skill", "experience", "technical", "culture"],
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": ["recruiter", "hiring_manager", "final", "rationale"],
                },
                "ranking_explanation": {"type": "string"},
            },
            "required": [
                "skill_output",
                "experience_output",
                "technical_output",
                "culture_output",
                "weight_negotiation",
                "ranking_explanation",
            ],
        }

        try:
            client = get_openai_client()
            completion = client.chat.completions.create(
                model=settings.openai_agent_model,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "instruction": "Produce outputs matching this JSON schema exactly.",
                                "json_schema": output_schema,
                                "payload": payload,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            raw_content = completion.choices[0].message.content if completion.choices else None
            data = self._safe_json_load(raw_content)

            skill_output = SkillAgentOutput.model_validate(data.get("skill_output", {}))
            experience_output = ExperienceAgentOutput.model_validate(data.get("experience_output", {}))
            technical_output = TechnicalAgentOutput.model_validate(data.get("technical_output", {}))
            culture_output = CultureAgentOutput.model_validate(data.get("culture_output", {}))

            raw_negotiation = data.get("weight_negotiation", {})
            recruiter = WeightProposal.model_validate(self._normalize_weight_payload(raw_negotiation.get("recruiter", {})))
            hiring_manager = WeightProposal.model_validate(self._normalize_weight_payload(raw_negotiation.get("hiring_manager", {})))
            final = WeightProposal.model_validate(self._normalize_weight_payload(raw_negotiation.get("final", {})))
            weight_negotiation = WeightNegotiationOutput(
                recruiter=recruiter,
                hiring_manager=hiring_manager,
                final=final,
                rationale=str(raw_negotiation.get("rationale", "")),
            )
            ranking_explanation = str(data.get("ranking_explanation", "")) or "Agent weighted ranking from negotiated A2A policy."
            return skill_output, experience_output, technical_output, culture_output, weight_negotiation, ranking_explanation
        except Exception:
            logger.exception("Live agent scoring failed; fallback heuristics will be used.")
            return None

    def _run_heuristic_agents(
        self,
        *,
        hit: dict[str, Any],
        skill_input: SkillAgentInput,
        experience_input: ExperienceAgentInput,
        technical_input: TechnicalAgentInput,
        culture_input: CultureAgentInput,
        job_profile: JobProfile,
        category_filter: str | None,
    ) -> tuple[
        SkillAgentOutput,
        ExperienceAgentOutput,
        TechnicalAgentOutput,
        CultureAgentOutput,
        WeightNegotiationOutput,
        str,
    ]:
        skill_score = self._compute_skill_score(skill_input.required_skills, skill_input.candidate_normalized_skills)
        matched_skills = sorted(set(skill_input.required_skills).intersection(skill_input.candidate_normalized_skills))
        missing_skills = sorted(set(skill_input.required_skills).difference(skill_input.candidate_normalized_skills))
        skill_output = SkillAgentOutput(
            score=skill_score,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            evidence=matched_skills[:6],
            rationale="Fallback: required-vs-normalized skill overlap.",
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
            evidence=(experience_input.candidate_experience_items or [])[:4],
            rationale="Fallback: experience-year and seniority heuristics.",
        )

        stack_coverage = self._compute_skill_score(technical_input.required_stack, technical_input.candidate_skills)
        depth_signal = round(min(1.0, stack_coverage * 0.8 + float(hit.get("score", 0.0)) * 0.2), 4)
        technical_output = TechnicalAgentOutput(
            score=round((stack_coverage + depth_signal) / 2.0, 4),
            stack_coverage=stack_coverage,
            depth_signal=depth_signal,
            evidence=(technical_input.candidate_projects or [])[:4],
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

        weight_negotiation = self._fallback_weight_negotiation(job_profile)
        explanation = "Fallback weighted ranking from deterministic domain-agent heuristics and A2A weight policy."
        return skill_output, experience_output, technical_output, culture_output, weight_negotiation, explanation

    @staticmethod
    def _normalize_weight_payload(payload: dict[str, Any]) -> dict[str, float]:
        skill = float(payload.get("skill", 0.0))
        experience = float(payload.get("experience", 0.0))
        technical = float(payload.get("technical", 0.0))
        culture = float(payload.get("culture", 0.0))
        total = skill + experience + technical + culture
        if total <= 0.0:
            return {"skill": 0.35, "experience": 0.30, "technical": 0.20, "culture": 0.15}
        return {
            "skill": round(skill / total, 4),
            "experience": round(experience / total, 4),
            "technical": round(technical / total, 4),
            "culture": round(culture / total, 4),
        }

    def _fallback_weight_negotiation(self, job_profile: JobProfile) -> WeightNegotiationOutput:
        recruiter = {"skill": 0.30, "experience": 0.35, "technical": 0.20, "culture": 0.15}
        hiring_manager = {"skill": 0.40, "experience": 0.20, "technical": 0.30, "culture": 0.10}

        if job_profile.required_experience_years and job_profile.required_experience_years >= 5.0:
            recruiter["experience"] += 0.10
            recruiter["technical"] -= 0.05
            recruiter["culture"] -= 0.05

        if len(job_profile.required_skills) >= 6:
            hiring_manager["technical"] += 0.10
            hiring_manager["experience"] -= 0.05
            hiring_manager["culture"] -= 0.05

        recruiter = self._normalize_weight_payload(recruiter)
        hiring_manager = self._normalize_weight_payload(hiring_manager)

        final = self._normalize_weight_payload(
            {
                "skill": (recruiter["skill"] + hiring_manager["skill"]) / 2.0,
                "experience": (recruiter["experience"] + hiring_manager["experience"]) / 2.0,
                "technical": (recruiter["technical"] + hiring_manager["technical"]) / 2.0,
                "culture": (recruiter["culture"] + hiring_manager["culture"]) / 2.0,
            }
        )

        return WeightNegotiationOutput(
            recruiter=WeightProposal.model_validate(recruiter),
            hiring_manager=WeightProposal.model_validate(hiring_manager),
            final=WeightProposal.model_validate(final),
            rationale=(
                "Fallback A2A negotiation: recruiter biases experience/culture, "
                "hiring manager biases skill/technical, final is normalized midpoint."
            ),
        )

    @staticmethod
    def _should_use_live_agent_calls() -> bool:
        if not settings.openai_agent_live_mode:
            return False
        if os.getenv("PYTEST_CURRENT_TEST"):
            return False
        if not settings.openai_api_key:
            return False
        return True

    @staticmethod
    def _safe_json_load(content: Any) -> dict[str, Any]:
        if not content:
            return {}
        if not isinstance(content, str):
            return {}
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()
        data = json.loads(text)
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _extract_experience_items(parsed: dict[str, Any]) -> list[str]:
        items = parsed.get("experience_items", [])
        if not isinstance(items, list):
            return []
        out: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            company = item.get("company")
            if title and company:
                out.append(f"{title} at {company}")
            elif title:
                out.append(str(title))
            elif company:
                out.append(str(company))
        return dedupe_preserve(out)

    @staticmethod
    def _extract_project_evidence(parsed: dict[str, Any]) -> list[str]:
        items = parsed.get("experience_items", [])
        if not isinstance(items, list):
            return []
        out: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            description = item.get("description")
            if isinstance(description, str) and description.strip():
                out.append(description.strip()[:180])
        return dedupe_preserve(out)

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
        weights: AgentWeights = ranking_input.weights
        weighted = (
            ranking_input.skill_score * weights.skill
            + ranking_input.experience_score * weights.experience
            + ranking_input.technical_score * weights.technical
            + ranking_input.culture_score * weights.culture
        )
        return round(min(1.0, max(0.0, weighted)), 4)


agent_orchestration_service = AgentOrchestrationService()
