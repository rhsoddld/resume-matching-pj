from __future__ import annotations

from pydantic import BaseModel, Field


class AgentWeights(BaseModel):
    skill: float = Field(0.35, ge=0.0, le=1.0)
    experience: float = Field(0.30, ge=0.0, le=1.0)
    technical: float = Field(0.20, ge=0.0, le=1.0)
    culture: float = Field(0.15, ge=0.0, le=1.0)


class RankingAgentInput(BaseModel):
    candidate_id: str
    skill_score: float = Field(..., ge=0.0, le=1.0)
    experience_score: float = Field(..., ge=0.0, le=1.0)
    technical_score: float = Field(..., ge=0.0, le=1.0)
    culture_score: float = Field(..., ge=0.0, le=1.0)
    vector_score: float | None = Field(default=None, ge=0.0, le=1.0)
    deterministic_score: float | None = Field(default=None, ge=0.0, le=1.0)
    weights: AgentWeights = Field(default_factory=AgentWeights)


class RankingBreakdown(BaseModel):
    skill: float = Field(..., ge=0.0, le=1.0)
    experience: float = Field(..., ge=0.0, le=1.0)
    technical: float = Field(..., ge=0.0, le=1.0)
    culture: float = Field(..., ge=0.0, le=1.0)
    weighted_score: float = Field(..., ge=0.0, le=1.0)


class RankingAgentOutput(BaseModel):
    final_score: float = Field(..., ge=0.0, le=1.0)
    breakdown: RankingBreakdown
    explanation: str = ""

