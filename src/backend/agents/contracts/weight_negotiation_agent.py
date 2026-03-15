from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from backend.agents.contracts.ranking_agent import AgentWeights


class WeightProposal(BaseModel):
    skill: float = Field(..., ge=0.0, le=1.0)
    experience: float = Field(..., ge=0.0, le=1.0)
    technical: float = Field(..., ge=0.0, le=1.0)
    culture: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_sum(self) -> "WeightProposal":
        total = self.skill + self.experience + self.technical + self.culture
        if not (0.99 <= total <= 1.01):
            raise ValueError("weight proposal must sum to 1.0")
        return self

    def as_agent_weights(self) -> AgentWeights:
        return AgentWeights(
            skill=self.skill,
            experience=self.experience,
            technical=self.technical,
            culture=self.culture,
        )


class WeightNegotiationOutput(BaseModel):
    recruiter: WeightProposal
    hiring_manager: WeightProposal
    final: WeightProposal
    rationale: str = ""
    ranking_explanation: str = ""
