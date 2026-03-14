from __future__ import annotations

import re
from typing import Any

from backend.core.providers import get_skill_ontology
from backend.repositories.mongo_repo import get_candidates_by_ids


_EDUCATION_LEVELS = {"bachelor": 1, "master": 2, "phd": 3}
_EDUCATION_PATTERNS = {
    "bachelor": (
        "bachelor",
        "bachelors",
        "b.tech",
        "btech",
        "b.e",
        "be ",
        "b.sc",
        "bsc",
        "ba ",
    ),
    "master": ("master", "masters", "m.tech", "mtech", "m.e", "m.sc", "msc", "mba", "ms "),
    "phd": ("phd", "doctor", "doctorate", "dphil"),
}
_INDUSTRY_TAXONOMY_SEEDS = {
    "technology": {"technology", "information technology", "backend", "programming", "database", "data"},
    "finance": {"finance", "banking", "accounting", "investment", "audit"},
    "healthcare": {"healthcare", "medical", "clinical", "wellness"},
    "e commerce": {
        "e commerce",
        "ecommerce",
        "retail",
        "online retail",
        "marketplace",
        "digital commerce",
        "sales",
        "marketing",
        "business development",
        "digital media",
    },
    "manufacturing": {"manufacturing", "industrial", "engineering", "automotive", "production"},
}
_REGION_ALIASES = {
    "us": "united states",
    "u.s.": "united states",
    "usa": "united states",
    "united states of america": "united states",
    "uk": "united kingdom",
    "u.k.": "united kingdom",
    "great britain": "united kingdom",
    "england": "united kingdom",
    "uae": "united arab emirates",
}
_INDUSTRY_ALIASES = {
    "it": "technology",
    "tech": "technology",
    "information technology": "technology",
    "fintech": "finance",
    "health care": "healthcare",
    "health tech": "healthcare",
    "ecommerce": "e commerce",
    "e-commerce": "e commerce",
    "online retail": "e commerce",
}


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    lowered = value.strip().lower()
    lowered = re.sub(r"[-_]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered)


def _normalize_region(value: Any) -> str:
    token = _normalize_text(value)
    if not token:
        return ""
    if token in _REGION_ALIASES:
        return _REGION_ALIASES[token]
    normalized = token
    for alias, canonical in sorted(_REGION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in normalized:
            normalized = normalized.replace(alias, canonical)
    return normalized


def _normalize_industry(value: Any) -> str:
    token = _normalize_text(value)
    if not token:
        return ""
    return _INDUSTRY_ALIASES.get(token, token)


def _extract_locations(candidate_doc: dict[str, Any]) -> list[str]:
    values: list[str] = []
    metadata = candidate_doc.get("metadata")
    if isinstance(metadata, dict):
        values.append(_normalize_region(metadata.get("location")))

    parsed = candidate_doc.get("parsed")
    if not isinstance(parsed, dict):
        return [value for value in values if value]

    for item in parsed.get("experience_items") or []:
        if isinstance(item, dict):
            values.append(_normalize_region(item.get("location")))
    for item in parsed.get("education") or []:
        if isinstance(item, dict):
            values.append(_normalize_region(item.get("location")))
    return [value for value in values if value]


def _max_education_level(candidate_doc: dict[str, Any]) -> int:
    parsed = candidate_doc.get("parsed")
    if not isinstance(parsed, dict):
        return 0

    highest = 0
    for item in parsed.get("education") or []:
        if not isinstance(item, dict):
            continue
        degree = _normalize_text(item.get("degree"))
        if not degree:
            continue
        for level, patterns in _EDUCATION_PATTERNS.items():
            if any(pattern in degree for pattern in patterns):
                highest = max(highest, _EDUCATION_LEVELS[level])
    return highest


def _matches_region(candidate_doc: dict[str, Any], region: str | None) -> bool:
    normalized_region = _normalize_region(region)
    if not normalized_region:
        return True
    locations = _extract_locations(candidate_doc)
    if not locations:
        return False
    if normalized_region == "remote":
        return any("remote" in location or "wfh" in location for location in locations)
    return any(normalized_region in location for location in locations)


def _matches_education(candidate_doc: dict[str, Any], education: str | None) -> bool:
    normalized = _normalize_text(education)
    if not normalized or normalized == "any":
        return True
    required = _EDUCATION_LEVELS.get(normalized)
    if required is None:
        return True
    return _max_education_level(candidate_doc) >= required


def _matches_industry(candidate_doc: dict[str, Any], industry: str | None) -> bool:
    normalized = _normalize_industry(industry)
    if not normalized:
        return True

    seed_terms = _INDUSTRY_TAXONOMY_SEEDS.get(normalized)
    if not seed_terms:
        return True

    parsed = candidate_doc.get("parsed")
    parsed = parsed if isinstance(parsed, dict) else {}
    category = _normalize_industry(candidate_doc.get("category")) or _normalize_text(candidate_doc.get("category"))
    candidate_tokens = {
        _normalize_text(skill)
        for field in ("core_skills", "expanded_skills", "normalized_skills")
        for skill in (parsed.get(field) or [])
        if isinstance(skill, str) and _normalize_text(skill)
    }
    if category:
        candidate_tokens.add(category)

    ontology = get_skill_ontology()
    if ontology is None:
        # Fallback: structured token match without free-text summary heuristics.
        return len(candidate_tokens.intersection(seed_terms)) > 0

    candidate_taxonomy_tags: set[str] = set()
    for token in candidate_tokens:
        canonical = ontology.alias_to_canonical.get(token, token)
        candidate_taxonomy_tags.add(canonical)
        meta = ontology.core_taxonomy.get(canonical)
        if not isinstance(meta, dict):
            continue
        domain = _normalize_text(meta.get("domain"))
        family = _normalize_text(meta.get("family"))
        if domain:
            candidate_taxonomy_tags.add(domain)
        if family:
            candidate_taxonomy_tags.add(family)
        for parent in meta.get("parents", []):
            parent_token = _normalize_text(parent)
            if parent_token:
                candidate_taxonomy_tags.add(parent_token)

    industry_taxonomy_terms = set(seed_terms)
    for skill, meta in ontology.core_taxonomy.items():
        related = {
            _normalize_text(skill),
            _normalize_text(meta.get("domain")),
            _normalize_text(meta.get("family")),
            *[_normalize_text(parent) for parent in meta.get("parents", [])],
        }
        if related.intersection(seed_terms):
            skill_token = _normalize_text(skill)
            if skill_token:
                industry_taxonomy_terms.add(skill_token)

    return len(candidate_taxonomy_tags.intersection(industry_taxonomy_terms)) > 0


def enrich_hits(
    hits: list[dict[str, Any]],
    *,
    min_experience_years: float | None,
    education: str | None = None,
    region: str | None = None,
    industry: str | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if not hits:
        return []

    candidate_ids = [hit["candidate_id"] for hit in hits if hit.get("candidate_id")]
    docs_by_id = get_candidates_by_ids(candidate_ids)

    enriched: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for hit in hits:
        if min_experience_years is not None:
            exp = hit.get("experience_years")
            if exp is None or exp < min_experience_years:
                continue

        candidate_id = hit.get("candidate_id")
        if not candidate_id:
            continue
        candidate_doc = docs_by_id.get(candidate_id)
        if not candidate_doc:
            continue
        if not _matches_education(candidate_doc, education):
            continue
        if not _matches_region(candidate_doc, region):
            continue
        if not _matches_industry(candidate_doc, industry):
            continue
        enriched.append((hit, candidate_doc))

    return enriched
