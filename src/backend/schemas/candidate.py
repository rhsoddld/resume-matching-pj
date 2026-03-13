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


class ParsedSection(BaseModel):
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    normalized_skills: List[str] = Field(default_factory=list)
    abilities: List[str] = Field(default_factory=list)
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
