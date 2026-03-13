from __future__ import annotations

from pydantic import BaseModel, Field


class TechnicalAgentInput(BaseModel):
    candidate_id: str
    job_description: str = Field(..., min_length=20, max_length=10_000)
    required_stack: list[str] = Field(default_factory=list)
    preferred_stack: list[str] = Field(default_factory=list)
    candidate_skills: list[str] = Field(default_factory=list)
    candidate_projects: list[str] = Field(default_factory=list)
    candidate_summary: str | None = None
    raw_resume_text: str | None = None


class TechnicalAgentOutput(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    stack_coverage: float = Field(..., ge=0.0, le=1.0)
    depth_signal: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    rationale: str = ""

