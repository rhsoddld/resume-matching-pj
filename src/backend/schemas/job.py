from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field


INDUSTRY_STANDARD_DICTIONARY: dict[str, dict[str, List[str]]] = {
    "technology": {
        "aliases": ["it", "tech", "information technology", "software"],
        "category_terms": ["information technology", "it", "software", "engineering", "developer", "platform"],
    },
    "finance": {
        "aliases": ["fintech", "banking", "financial services"],
        "category_terms": ["finance", "fintech", "banking", "accounting", "investment", "audit"],
    },
    "healthcare": {
        "aliases": ["health care", "health tech", "medical"],
        "category_terms": ["healthcare", "health care", "medical", "clinical", "pharma"],
    },
    "e commerce": {
        "aliases": ["ecommerce", "e-commerce", "online retail", "digital commerce"],
        "category_terms": ["e commerce", "ecommerce", "retail", "marketplace", "digital commerce", "online retail"],
    },
    "manufacturing": {
        "aliases": ["industrial", "automotive", "production"],
        "category_terms": ["manufacturing", "industrial", "automotive", "production", "factory"],
    },
}


def _normalize_industry_token(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    token = value.strip().lower()
    token = re.sub(r"[-_]+", " ", token)
    token = re.sub(r"\s+", " ", token)
    return token


def normalize_industry_label(value: str | None) -> str:
    token = _normalize_industry_token(value)
    if not token:
        return ""
    if token in INDUSTRY_STANDARD_DICTIONARY:
        return token
    for canonical, payload in INDUSTRY_STANDARD_DICTIONARY.items():
        aliases = payload.get("aliases", [])
        if token in aliases:
            return canonical
    return token


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
    education: Optional[str] = Field(default=None, max_length=64)
    region: Optional[str] = Field(default=None, max_length=64)
    industry: Optional[str] = Field(default=None, max_length=64)


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
    transferable_skill_score: float = Field(0.0, ge=0.0, le=1.0)
    transferable_skill_evidence: List[str] = Field(default_factory=list)
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
    adjacent_skill_score: Optional[float] = None
    agent_weighted: Optional[float] = None
    rank_policy: Optional[str] = None


class SkillOverlapDetail(BaseModel):
    core_overlap: float
    expanded_overlap: float
    normalized_overlap: float


class FairnessWarning(BaseModel):
    code: str
    severity: str
    message: str
    candidate_ids: List[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)


class FairnessAudit(BaseModel):
    enabled: bool = True
    policy_version: str = "v1"
    checks_run: List[str] = Field(default_factory=list)
    warnings: List[FairnessWarning] = Field(default_factory=list)


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
    career_trajectory: dict = Field(default_factory=dict)
    adjacent_skill_matches: List[str] = Field(default_factory=list)
    possible_gaps: List[str] = Field(default_factory=list)
    bias_warnings: List[str] = Field(default_factory=list)
    weighting_summary: Optional[str] = None


class JobMatchResponse(BaseModel):
    session_id: Optional[str] = None
    query_profile: QueryUnderstandingProfile
    matches: List[JobMatchCandidate] = Field(default_factory=list)
    fairness: FairnessAudit = Field(default_factory=FairnessAudit)
