from __future__ import annotations

from pydantic import BaseModel, Field


class SkillAgentInput(BaseModel):
    candidate_id: str
    job_description: str = Field(..., min_length=20, max_length=10_000)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    candidate_skills: list[str] = Field(default_factory=list)
    candidate_normalized_skills: list[str] = Field(default_factory=list)
    candidate_core_skills: list[str] = Field(default_factory=list)
    candidate_expanded_skills: list[str] = Field(default_factory=list)
    candidate_summary: str | None = None
    raw_resume_text: str | None = None


class SkillAgentOutput(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    rationale: str = ""

