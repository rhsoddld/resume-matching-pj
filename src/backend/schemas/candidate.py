from typing import List, Optional

from pydantic import BaseModel, Field


class ParsedEducation(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None


class ParsedExperienceItem(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class VersionedSkill(BaseModel):
    raw: str
    canonical: str
    version: str


class ParsedSection(BaseModel):
    summary: Optional[str] = None
    # Original extracted skills before lexical normalization.
    skills: List[str] = Field(default_factory=list)
    # Lexically normalized tokens (lowercase/spacing cleanup).
    normalized_skills: List[str] = Field(default_factory=list)
    # Additional extracted abilities from structured data.
    abilities: List[str] = Field(default_factory=list)
    # Alias-applied canonical tokens.
    canonical_skills: List[str] = Field(default_factory=list)
    # Scoring-focused core skills from ontology taxonomy.
    core_skills: List[str] = Field(default_factory=list)
    # Parent-expanded skills for retrieval/explainability.
    expanded_skills: List[str] = Field(default_factory=list)
    # Operational capability phrases (non-core, auxiliary signal).
    capability_phrases: List[str] = Field(default_factory=list)
    # Role-like tokens (non-core, auxiliary signal).
    role_candidates: List[str] = Field(default_factory=list)
    # Ambiguous tokens kept for manual review.
    review_required_skills: List[str] = Field(default_factory=list)
    # Skill + version tuples.
    versioned_skills: List[VersionedSkill] = Field(default_factory=list)
    experience_years: Optional[float] = None
    seniority_level: Optional[str] = None
    education: List[ParsedEducation] = Field(default_factory=list)
    experience_items: List[ParsedExperienceItem] = Field(default_factory=list)


class Metadata(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None


class IngestionMeta(BaseModel):
    ingested_at: Optional[str] = None
    parsing_version: Optional[str] = None
    normalization_version: Optional[str] = None
    taxonomy_version: Optional[str] = None
    embedding_text_version: Optional[str] = None
    experience_years_method: Optional[str] = None
    alias_applied: bool = False
    taxonomy_applied: bool = False
    has_structured_enrichment: bool = False
    normalization_hash: Optional[str] = None
    embedding_hash: Optional[str] = None
    embedding_upserted_at: Optional[str] = None


class Candidate(BaseModel):
    candidate_id: str
    source_dataset: str = "snehaanbhawal"
    source_keys: dict | None = None
    category: Optional[str] = None

    raw: dict
    parsed: ParsedSection = Field(default_factory=ParsedSection)
    metadata: Metadata = Field(default_factory=Metadata)
    embedding_text: Optional[str] = None
    ingestion: IngestionMeta = Field(default_factory=IngestionMeta)


class CandidateMatchView(BaseModel):
    candidate_id: str
    category: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    normalized_skills: List[str] = Field(default_factory=list)
    experience_years: Optional[float] = None
    seniority_level: Optional[str] = None
