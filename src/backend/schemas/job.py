from typing import List, Optional

from pydantic import BaseModel, Field


class ParsedRequirements(BaseModel):
    title: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    must_have: List[str] = Field(default_factory=list)
    nice_to_have: List[str] = Field(default_factory=list)
    seniority: Optional[str] = None
    education: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)


class Job(BaseModel):
    job_id: str
    title: Optional[str] = None
    raw_description: str
    parsed_requirements: ParsedRequirements = Field(default_factory=ParsedRequirements)
    filters: dict = Field(default_factory=dict)


class JobMatchRequest(BaseModel):
    job_description: str
    top_k: int = 10
    category: Optional[str] = None
    min_experience_years: Optional[float] = None

