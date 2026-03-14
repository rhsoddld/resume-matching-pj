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


class QueryUnderstandingProfile(BaseModel):
    class Signal(BaseModel):
        name: str
        strength: str
        signal_type: str

    job_category: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)
    related_skills: List[str] = Field(default_factory=list)
    skill_signals: List[Signal] = Field(default_factory=list)
    capability_signals: List[Signal] = Field(default_factory=list)
    seniority_hint: Optional[str] = None
    filters: dict = Field(default_factory=dict)
    metadata_filters: dict = Field(default_factory=dict)
    signal_quality: dict = Field(default_factory=dict)
    lexical_query: str = ""
    semantic_query_expansion: List[str] = Field(default_factory=list)
    query_text_for_embedding: str = ""
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    fallback_rationale: Optional[str] = None
    fallback_trigger: dict = Field(default_factory=dict)


class ScoreDetail(BaseModel):
    semantic_similarity: float
    experience_fit: float
    seniority_fit: float
    category_fit: float
    retrieval_fusion: Optional[float] = None
    retrieval_keyword: Optional[float] = None
    retrieval_metadata: Optional[float] = None
    must_have_match_rate: Optional[float] = None
    must_have_penalty: Optional[float] = None
    agent_weighted: Optional[float] = None
    rank_policy: Optional[str] = None


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
    agent_scores: dict = Field(default_factory=dict)
    agent_explanation: Optional[str] = None
    relevant_experience: List[str] = Field(default_factory=list)
    possible_gaps: List[str] = Field(default_factory=list)
    weighting_summary: Optional[str] = None


class JobMatchResponse(BaseModel):
    query_profile: QueryUnderstandingProfile
    matches: List[JobMatchCandidate] = Field(default_factory=list)
