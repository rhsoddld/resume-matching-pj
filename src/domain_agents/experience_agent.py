from __future__ import annotations

from pydantic import BaseModel, Field


class ExperienceAgentInput(BaseModel):
    candidate_id: str
    job_description: str = Field(..., min_length=20, max_length=10_000)
    required_experience_years: float | None = Field(default=None, ge=0.0, le=60.0)
    preferred_seniority: str | None = None
    candidate_experience_years: float | None = Field(default=None, ge=0.0, le=60.0)
    candidate_seniority_level: str | None = None
    candidate_experience_items: list[str] = Field(default_factory=list)
    candidate_summary: str | None = None
    raw_resume_text: str | None = None


class ExperienceAgentOutput(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    experience_fit: float = Field(..., ge=0.0, le=1.0)
    seniority_fit: float = Field(..., ge=0.0, le=1.0)
    career_trajectory: dict = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    rationale: str = ""
