from __future__ import annotations

import re
from typing import Any

from backend.core.filter_options import INDUSTRY_STANDARD_DICTIONARY
from backend.schemas.job import normalize_industry_label


def normalize_token(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    token = value.strip().lower()
    token = re.sub(r"[-_]+", " ", token)
    token = re.sub(r"\s+", " ", token)
    return token


INDUSTRY_CATEGORY_MAP = {
    canonical: [term.strip().lower() for term in payload.get("category_terms", []) if isinstance(term, str)]
    for canonical, payload in INDUSTRY_STANDARD_DICTIONARY.items()
}


def industry_key(industry: str | None) -> str:
    return normalize_industry_label(industry) or normalize_token(industry)


def compute_keyword_score(*, parsed: dict[str, Any], terms: list[str]) -> float:
    token_pool: set[str] = set()
    for key in ("skills", "normalized_skills", "core_skills", "expanded_skills"):
        values = parsed.get(key) or []
        for value in values:
            if isinstance(value, str) and value.strip():
                token_pool.add(value.strip().lower())

    if not terms:
        return 0.0

    overlap = len(set(terms).intersection(token_pool)) / len(set(terms))
    return round(min(1.0, overlap), 4)


def normalize_vector_similarity(raw_similarity: float) -> float:
    normalized = (raw_similarity + 1.0) / 2.0
    return max(0.0, min(1.0, normalized))


def fusion_score(
    *,
    vector_score: float,
    keyword_score: float,
    metadata_score: float,
    vector_weight: float,
    keyword_weight: float,
    metadata_weight: float,
) -> float:
    v_w = max(0.0, float(vector_weight))
    k_w = max(0.0, float(keyword_weight))
    m_w = max(0.0, float(metadata_weight))
    total = v_w + k_w + m_w or 1.0
    return max(0.0, min(1.0, (vector_score * v_w + keyword_score * k_w + metadata_score * m_w) / total))


def metadata_score(
    *,
    category: str | None,
    industry: str | None,
    min_experience_years: float | None,
    preferred_seniority: str | None,
    candidate_category: str | None,
    candidate_experience_years: float | None,
    candidate_seniority_level: str | None,
) -> float:
    normalized_candidate_category = normalize_token(candidate_category)
    category_score = 0.5
    if category:
        category_score = 1.0 if normalized_candidate_category == normalize_token(category) else 0.0

    industry_score = 0.5
    normalized_industry = industry_key(industry)
    if normalized_industry:
        industry_terms = {normalize_token(term) for term in INDUSTRY_CATEGORY_MAP.get(normalized_industry, [])}
        industry_terms = {term for term in industry_terms if term}
        if not industry_terms:
            industry_score = 0.5
        else:
            industry_score = 1.0 if any(term in normalized_candidate_category for term in industry_terms) else 0.0

    experience_score = 0.5
    if min_experience_years is not None:
        if candidate_experience_years is None:
            experience_score = 0.0
        elif min_experience_years <= 0:
            experience_score = 1.0
        else:
            experience_score = max(0.0, min(1.0, float(candidate_experience_years) / float(min_experience_years)))

    seniority_score = 0.5
    if preferred_seniority:
        if not candidate_seniority_level:
            seniority_score = 0.2
        elif candidate_seniority_level.strip().lower() == preferred_seniority.strip().lower():
            seniority_score = 1.0
        else:
            seniority_score = 0.4

    if normalized_industry:
        return (category_score * 0.4) + (industry_score * 0.15) + (experience_score * 0.3) + (seniority_score * 0.15)
    return (category_score * 0.5) + (experience_score * 0.35) + (seniority_score * 0.15)
