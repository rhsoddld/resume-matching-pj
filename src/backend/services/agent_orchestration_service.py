from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import importlib
import json
import logging
import os
import re
from typing import Any

from domain_agents.culture_agent import CultureAgentInput, CultureAgentOutput
from domain_agents.experience_agent import ExperienceAgentInput, ExperienceAgentOutput
from domain_agents.orchestrator import CandidateAgentResult
from domain_agents.ranking_agent import AgentWeights, RankingAgentInput, RankingAgentOutput, RankingBreakdown
from domain_agents.skill_agent import SkillAgentInput, SkillAgentOutput
from domain_agents.technical_agent import TechnicalAgentInput, TechnicalAgentOutput
from domain_agents.weight_negotiation_agent import WeightNegotiationOutput, WeightProposal
from backend.core.collections import dedupe_preserve
from backend.core.providers import get_openai_client
from backend.core.settings import settings
from backend.services.job_profile_extractor import JobProfile
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class _RawWeightProposal(BaseModel):
    skill: float = Field(..., ge=0.0, le=1.0)
    experience: float = Field(..., ge=0.0, le=1.0)
    technical: float = Field(..., ge=0.0, le=1.0)
    culture: float = Field(..., ge=0.0, le=1.0)


class _ScorePackOutput(BaseModel):
    skill_output: SkillAgentOutput
    experience_output: ExperienceAgentOutput
    technical_output: TechnicalAgentOutput
    culture_output: CultureAgentOutput
    ranking_explanation: str = ""


class _ViewpointProposalOutput(BaseModel):
    proposal: _RawWeightProposal
    rationale: str = ""


class _NegotiationOutput(BaseModel):
    final: _RawWeightProposal
    rationale: str = ""
    ranking_explanation: str = ""


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
            sdk_result = self._run_agents_sdk_runtime(
                job_description=job_description,
                job_profile=job_profile,
                hit=hit,
                skill_input=skill_input,
                experience_input=experience_input,
                technical_input=technical_input,
                culture_input=culture_input,
                category_filter=category_filter,
            )
            if sdk_result is not None:
                skill_output, experience_output, technical_output, culture_output, weight_negotiation, ranking_explanation = sdk_result
            else:
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
                        parsed=parsed,
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
                parsed=parsed,
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

    def _run_agents_sdk_runtime(
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
        if not settings.openai_agents_sdk_enabled:
            return None

        runtime = self._load_agents_sdk_runtime()
        if runtime is None:
            return None
        AgentCls, RunnerCls = runtime

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
        payload_json = json.dumps(payload, ensure_ascii=False)

        try:
            model = settings.openai_agent_model

            skill_agent = AgentCls(
                name="SkillEvalAgent",
                model=model,
                instructions=(
                    "You are SkillEvalAgent. Score required/preferred skill alignment from 0 to 1. "
                    "Ground evidence in candidate inputs only."
                ),
                output_type=SkillAgentOutput,
            )
            experience_agent = AgentCls(
                name="ExperienceEvalAgent",
                model=model,
                instructions=(
                    "You are ExperienceEvalAgent. Evaluate experience_fit and seniority_fit (0..1) and final score. "
                    "Use job profile and candidate experience fields only."
                ),
                output_type=ExperienceAgentOutput,
            )
            technical_agent = AgentCls(
                name="TechnicalEvalAgent",
                model=model,
                instructions=(
                    "You are TechnicalEvalAgent. Evaluate stack_coverage and depth_signal (0..1) and final score. "
                    "Use technical evidence from the payload only."
                ),
                output_type=TechnicalAgentOutput,
            )
            culture_agent = AgentCls(
                name="CultureEvalAgent",
                model=model,
                instructions=(
                    "You are CultureEvalAgent. Evaluate collaboration/communication/ownership signals. "
                    "Return alignment, risk_flags, and score between 0 and 1."
                ),
                output_type=CultureAgentOutput,
            )

            skill_output = RunnerCls.run_sync(skill_agent, payload_json).final_output
            experience_output = RunnerCls.run_sync(experience_agent, payload_json).final_output
            technical_output = RunnerCls.run_sync(technical_agent, payload_json).final_output
            culture_output = RunnerCls.run_sync(culture_agent, payload_json).final_output

            score_pack_agent = AgentCls(
                name="ScorePackAgent",
                model=model,
                instructions=(
                    "You are ScorePackAgent. Consolidate four agent outputs into a coherent score pack. "
                    "Do not change score meaning; keep evidence concise and grounded."
                ),
                output_type=_ScorePackOutput,
            )
            score_pack_input = json.dumps(
                {
                    "payload": payload,
                    "skill_output": skill_output.model_dump(),
                    "experience_output": experience_output.model_dump(),
                    "technical_output": technical_output.model_dump(),
                    "culture_output": culture_output.model_dump(),
                },
                ensure_ascii=False,
            )
            score_pack = RunnerCls.run_sync(score_pack_agent, score_pack_input).final_output

            recruiter_agent = AgentCls(
                name="RecruiterAgent",
                model=model,
                instructions=(
                    "You are RecruiterAgent. Propose weights over skill/experience/technical/culture that sum to 1.0. "
                    "Recruiter should slightly prioritize experience and culture for delivery/readiness."
                ),
                output_type=_ViewpointProposalOutput,
            )
            hiring_manager_agent = AgentCls(
                name="HiringManagerAgent",
                model=model,
                instructions=(
                    "You are HiringManagerAgent. Propose weights over skill/experience/technical/culture that sum to 1.0. "
                    "Hiring manager should slightly prioritize technical depth and required skill fit."
                ),
                output_type=_ViewpointProposalOutput,
            )
            viewpoint_input = json.dumps(
                {"payload": payload, "score_pack": score_pack.model_dump()},
                ensure_ascii=False,
            )
            recruiter_view = RunnerCls.run_sync(recruiter_agent, viewpoint_input).final_output
            hiring_manager_view = RunnerCls.run_sync(hiring_manager_agent, viewpoint_input).final_output

            negotiation_agent = AgentCls(
                name="WeightNegotiationAgent",
                model=model,
                instructions=(
                    "You are WeightNegotiationAgent. Negotiate final weights from recruiter and hiring manager proposals. "
                    "Return balanced final weights summing to 1.0, rationale, and ranking_explanation."
                ),
                output_type=_NegotiationOutput,
            )
            negotiation_input = json.dumps(
                {
                    "payload": payload,
                    "score_pack": score_pack.model_dump(),
                    "recruiter": recruiter_view.model_dump(),
                    "hiring_manager": hiring_manager_view.model_dump(),
                },
                ensure_ascii=False,
            )
            negotiation = RunnerCls.run_sync(negotiation_agent, negotiation_input).final_output

            recruiter = WeightProposal.model_validate(
                self._normalize_weight_payload(recruiter_view.proposal.model_dump())
            )
            hiring_manager = WeightProposal.model_validate(
                self._normalize_weight_payload(hiring_manager_view.proposal.model_dump())
            )
            final = WeightProposal.model_validate(self._normalize_weight_payload(negotiation.final.model_dump()))
            weight_negotiation = WeightNegotiationOutput(
                recruiter=recruiter,
                hiring_manager=hiring_manager,
                final=final,
                rationale=(negotiation.rationale or "").strip(),
            )
            ranking_explanation = (
                (negotiation.ranking_explanation or "").strip()
                or (score_pack.ranking_explanation or "").strip()
                or "Agent weighted ranking from negotiated A2A policy."
            )
            return (
                score_pack.skill_output,
                score_pack.experience_output,
                score_pack.technical_output,
                score_pack.culture_output,
                weight_negotiation,
                ranking_explanation,
            )
        except Exception:
            logger.exception("Agents SDK runtime scoring failed; fallback to legacy live/heuristic path.")
            return None

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
        parsed: dict[str, Any],
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
        skill_evidence = self._extract_evidence_sentences(
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

        experience_fit = self._compute_experience_fit(
            required_experience_years=experience_input.required_experience_years,
            candidate_experience_years=experience_input.candidate_experience_years,
        )
        seniority_fit = self._compute_seniority_fit(
            preferred_seniority=experience_input.preferred_seniority,
            candidate_seniority=experience_input.candidate_seniority_level,
        )
        career_trajectory = self._build_career_trajectory(
            parsed=parsed,
            candidate_experience_years=experience_input.candidate_experience_years,
            candidate_seniority_level=experience_input.candidate_seniority_level,
        )
        experience_evidence = self._extract_evidence_sentences(
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

        stack_coverage = self._compute_skill_score(technical_input.required_stack, technical_input.candidate_skills)
        depth_signal = round(min(1.0, stack_coverage * 0.8 + float(hit.get("score", 0.0)) * 0.2), 4)
        technical_evidence = self._extract_evidence_sentences(
            text=technical_input.raw_resume_text or technical_input.candidate_summary or "",
            terms=[*technical_input.required_stack, "architecture", "designed", "implemented", "optimized", "built"],
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
    def _load_agents_sdk_runtime() -> tuple[Any, Any] | None:
        try:
            mod = importlib.import_module("agents")
        except Exception:
            return None

        AgentCls = getattr(mod, "Agent", None)
        RunnerCls = getattr(mod, "Runner", None)
        if AgentCls is None or RunnerCls is None:
            return None
        return AgentCls, RunnerCls

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
    def _extract_evidence_sentences(*, text: str, terms: list[str], limit: int = 4) -> list[str]:
        if not isinstance(text, str) or not text.strip():
            return []
        normalized_terms = [term.strip().lower() for term in terms if isinstance(term, str) and term.strip()]
        if not normalized_terms:
            return []
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s and s.strip()]
        scored: list[tuple[int, str]] = []
        for sentence in sentences:
            lowered = sentence.lower()
            hits = sum(1 for term in normalized_terms if term in lowered)
            if hits <= 0:
                continue
            if len(sentence) < 25:
                continue
            scored.append((hits, sentence[:220]))
        scored.sort(key=lambda item: item[0], reverse=True)
        return dedupe_preserve([sentence for _, sentence in scored])[:limit]

    @staticmethod
    def _parse_date_token(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        token = value.strip().lower()
        if token in {"present", "current", "now"}:
            return datetime.utcnow()
        for fmt in ("%Y-%m", "%Y/%m", "%Y"):
            try:
                return datetime.strptime(token, fmt)
            except ValueError:
                continue
        return None

    def _build_career_trajectory(
        self,
        *,
        parsed: dict[str, Any],
        candidate_experience_years: float | None,
        candidate_seniority_level: str | None,
    ) -> dict[str, Any]:
        items = parsed.get("experience_items") or []
        if not isinstance(items, list) or not items:
            return {
                "has_trajectory": False,
                "seniority_level": candidate_seniority_level,
                "total_experience_years": candidate_experience_years,
                "progression": "insufficient-data",
                "moves": [],
            }

        normalized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "title": str(item.get("title") or "").strip() or None,
                    "company": str(item.get("company") or "").strip() or None,
                    "start_date": item.get("start_date"),
                    "end_date": item.get("end_date"),
                    "start_dt": self._parse_date_token(item.get("start_date")),
                }
            )
        normalized.sort(key=lambda row: row.get("start_dt") or datetime.min)
        if not normalized:
            return {
                "has_trajectory": False,
                "seniority_level": candidate_seniority_level,
                "total_experience_years": candidate_experience_years,
                "progression": "insufficient-data",
                "moves": [],
            }

        moves: list[dict[str, Any]] = []
        for idx, row in enumerate(normalized):
            if idx == 0:
                continue
            prev = normalized[idx - 1]
            if row.get("title") == prev.get("title") and row.get("company") == prev.get("company"):
                continue
            moves.append(
                {
                    "from_title": prev.get("title"),
                    "to_title": row.get("title"),
                    "from_company": prev.get("company"),
                    "to_company": row.get("company"),
                    "at": row.get("start_date"),
                }
            )

        progression = "stable"
        if len(moves) >= 2:
            progression = "growth"
        if moves and any(move.get("from_company") != move.get("to_company") for move in moves):
            progression = "transition"

        first = normalized[0]
        last = normalized[-1]
        return {
            "has_trajectory": True,
            "seniority_level": candidate_seniority_level,
            "total_experience_years": candidate_experience_years,
            "first_role": {"title": first.get("title"), "company": first.get("company"), "start_date": first.get("start_date")},
            "latest_role": {"title": last.get("title"), "company": last.get("company"), "start_date": last.get("start_date"), "end_date": last.get("end_date")},
            "progression": progression,
            "moves": moves[:6],
        }

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
