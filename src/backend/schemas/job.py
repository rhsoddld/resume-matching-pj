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
    job_description: str = Field(..., min_length=20, max_length=10_000)
    top_k: int = Field(10, ge=1, le=50)
    category: Optional[str] = Field(default=None, max_length=64)
    min_experience_years: Optional[float] = Field(default=None, ge=0, le=60)


class ScoreDetail(BaseModel):
    semantic_similarity: float
    experience_fit: float
    seniority_fit: float
    category_fit: float


class SkillOverlapDetail(BaseModel):
    core_overlap: float
    expanded_overlap: float
    normalized_overlap: float


class JobMatchCandidate(BaseModel):
    candidate_id: str
    category: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    normalized_skills: List[str] = Field(default_factory=list)
    core_skills: List[str] = Field(default_factory=list)
    expanded_skills: List[str] = Field(default_factory=list)
    experience_years: Optional[float] = None
    seniority_level: Optional[str] = None
    score: float
    vector_score: float
    skill_overlap: float
    score_detail: ScoreDetail
    skill_overlap_detail: SkillOverlapDetail


class JobMatchResponse(BaseModel):
    matches: List[JobMatchCandidate] = Field(default_factory=list)
