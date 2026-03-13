from __future__ import annotations

from pydantic import BaseModel, Field


class CultureAgentInput(BaseModel):
    candidate_id: str
    job_description: str = Field(..., min_length=20, max_length=10_000)
    target_signals: list[str] = Field(default_factory=list)
    candidate_signals: list[str] = Field(default_factory=list)
    candidate_summary: str | None = None
    raw_resume_text: str | None = None


class CultureAgentOutput(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    alignment: float = Field(..., ge=0.0, le=1.0)
    risk_flags: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    rationale: str = ""

