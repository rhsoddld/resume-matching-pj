from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.contracts.culture_agent import CultureAgentInput, CultureAgentOutput
from backend.agents.contracts.experience_agent import ExperienceAgentInput, ExperienceAgentOutput
from backend.agents.contracts.ranking_agent import RankingAgentInput, RankingAgentOutput
from backend.agents.contracts.skill_agent import SkillAgentInput, SkillAgentOutput
from backend.agents.contracts.technical_agent import TechnicalAgentInput, TechnicalAgentOutput
from backend.agents.contracts.weight_negotiation_agent import WeightNegotiationOutput


class CandidateContext(BaseModel):
    candidate_id: str
    category: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    normalized_skills: list[str] = Field(default_factory=list)
    core_skills: list[str] = Field(default_factory=list)
    expanded_skills: list[str] = Field(default_factory=list)
    experience_years: float | None = None
    seniority_level: str | None = None
    raw_resume_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestratorRequest(BaseModel):
    job_id: str | None = None
    job_description: str = Field(..., min_length=20, max_length=10_000)
    category: str | None = None
    top_k: int = Field(10, ge=1, le=50)
    candidates: list[CandidateContext] = Field(default_factory=list)


class CandidateAgentBundle(BaseModel):
    candidate_id: str
    skill_input: SkillAgentInput
    experience_input: ExperienceAgentInput
    technical_input: TechnicalAgentInput
    culture_input: CultureAgentInput


class CandidateAgentResult(BaseModel):
    candidate_id: str
    skill_output: SkillAgentOutput
    experience_output: ExperienceAgentOutput
    technical_output: TechnicalAgentOutput
    culture_output: CultureAgentOutput
    ranking_input: RankingAgentInput
    ranking_output: RankingAgentOutput
    weight_negotiation: WeightNegotiationOutput | None = None
    runtime_mode: str | None = None
    runtime_reason: str | None = None


class OrchestratorResponse(BaseModel):
    results: list[CandidateAgentResult] = Field(default_factory=list)
