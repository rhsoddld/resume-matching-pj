from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from backend.services.ingestion.constants import (
    EMBEDDING_TEXT_VERSION,
    EXPERIENCE_YEARS_METHOD,
    NORMALIZATION_VERSION,
    TAXONOMY_VERSION,
)
from backend.services.ingestion.preprocessing import prepare_embedding_text, stable_sorted
from backend.schemas.candidate import Candidate


@dataclass
class ExistingState:
    normalization_hash: str | None
    embedding_hash: str | None


def candidate_key(cand: Candidate) -> tuple[str, str]:
    return (cand.source_dataset, cand.candidate_id)


def normalization_payload(cand: Candidate) -> dict:
    parsed = cand.parsed
    ingestion = cand.ingestion
    return {
        "candidate_id": cand.candidate_id,
        "source_dataset": cand.source_dataset,
        "category": cand.category,
        "parsed": {
            "summary": parsed.summary,
            "skills": parsed.skills,
            "normalized_skills": parsed.normalized_skills,
            "abilities": parsed.abilities,
            "canonical_skills": stable_sorted(parsed.canonical_skills),
            "core_skills": stable_sorted(parsed.core_skills),
            "expanded_skills": stable_sorted(parsed.expanded_skills),
            "capability_phrases": stable_sorted(parsed.capability_phrases),
            "role_candidates": stable_sorted(parsed.role_candidates),
            "review_required_skills": stable_sorted(parsed.review_required_skills),
            "versioned_skills": [item.model_dump() for item in parsed.versioned_skills],
            "experience_years": parsed.experience_years,
            "seniority_level": parsed.seniority_level,
            "education": [item.model_dump() for item in parsed.education],
            "experience_items": [item.model_dump() for item in parsed.experience_items],
        },
        "metadata": {
            "name": cand.metadata.name,
            "location": cand.metadata.location,
        },
        "ingestion": {
            "parsing_version": ingestion.parsing_version,
            "normalization_version": ingestion.normalization_version,
            "taxonomy_version": ingestion.taxonomy_version,
            "embedding_text_version": ingestion.embedding_text_version,
            "experience_years_method": ingestion.experience_years_method,
            "alias_applied": ingestion.alias_applied,
            "taxonomy_applied": ingestion.taxonomy_applied,
            "has_structured_enrichment": ingestion.has_structured_enrichment,
        },
    }


def compute_normalization_hash(cand: Candidate) -> str:
    payload = normalization_payload(cand)
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_ingestion_versions(cand: Candidate) -> None:
    if not cand.ingestion.normalization_version:
        cand.ingestion.normalization_version = NORMALIZATION_VERSION
    if not cand.ingestion.taxonomy_version:
        cand.ingestion.taxonomy_version = TAXONOMY_VERSION
    if not cand.ingestion.embedding_text_version:
        cand.ingestion.embedding_text_version = EMBEDDING_TEXT_VERSION
    if not cand.ingestion.experience_years_method:
        cand.ingestion.experience_years_method = EXPERIENCE_YEARS_METHOD


def ensure_normalization_hash(cand: Candidate) -> str:
    had_version_triplet = bool(
        cand.ingestion.normalization_version
        and cand.ingestion.taxonomy_version
        and cand.ingestion.experience_years_method
    )
    ensure_ingestion_versions(cand)
    normalization_hash = cand.ingestion.normalization_hash
    if (
        normalization_hash
        and had_version_triplet
        and cand.ingestion.normalization_version == NORMALIZATION_VERSION
        and cand.ingestion.taxonomy_version == TAXONOMY_VERSION
        and cand.ingestion.experience_years_method == EXPERIENCE_YEARS_METHOD
    ):
        return normalization_hash
    normalization_hash = compute_normalization_hash(cand)
    cand.ingestion.normalization_hash = normalization_hash
    return normalization_hash


def compute_embedding_hash(cand: Candidate) -> str:
    normalization_hash = ensure_normalization_hash(cand)
    payload = {
        "candidate_id": cand.candidate_id,
        "source_dataset": cand.source_dataset,
        "embedding_text": prepare_embedding_text(cand.embedding_text or ""),
        "embedding_text_version": cand.ingestion.embedding_text_version,
        "normalization_version": cand.ingestion.normalization_version,
        "taxonomy_version": cand.ingestion.taxonomy_version,
        "normalization_hash": normalization_hash,
    }
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_embedding_hash(cand: Candidate) -> str:
    had_text_version = bool(cand.ingestion.embedding_text_version)
    ensure_ingestion_versions(cand)
    embedding_hash = cand.ingestion.embedding_hash
    if embedding_hash and had_text_version and cand.ingestion.embedding_text_version == EMBEDDING_TEXT_VERSION:
        return embedding_hash
    embedding_hash = compute_embedding_hash(cand)
    cand.ingestion.embedding_hash = embedding_hash
    return embedding_hash
