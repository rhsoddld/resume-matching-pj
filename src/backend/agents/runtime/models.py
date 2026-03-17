from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.contracts.culture_agent import CultureAgentOutput
from backend.agents.contracts.experience_agent import ExperienceAgentOutput
from backend.agents.contracts.skill_agent import SkillAgentOutput
from backend.agents.contracts.technical_agent import TechnicalAgentOutput


class RawWeightProposal(BaseModel):
    skill: float = Field(..., ge=0.0, le=1.0)
    experience: float = Field(..., ge=0.0, le=1.0)
    technical: float = Field(..., ge=0.0, le=1.0)
    culture: float = Field(..., ge=0.0, le=1.0)


class ScorePackOutput(BaseModel):
    skill_output: SkillAgentOutput
    experience_output: ExperienceAgentOutput
    technical_output: TechnicalAgentOutput
    culture_output: CultureAgentOutput
    ranking_explanation: str = ""


class ViewpointProposalOutput(BaseModel):
    proposal: RawWeightProposal
    rationale: str = ""


class NegotiationOutput(BaseModel):
    final: RawWeightProposal
    rationale: str = ""
    ranking_explanation: str = ""


class HandoffConstraints(BaseModel):
    disagreement_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    max_turns: int = Field(default=3, ge=1, le=12)  # Recruiter→HM→Negotiation = 3 steps; 6 was overkill and costly


class HandoffRunContext(BaseModel):
    payload: dict[str, Any]
    score_pack: ScorePackOutput
    constraints: HandoffConstraints = Field(default_factory=HandoffConstraints)
