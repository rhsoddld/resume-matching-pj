from typing import Any, Optional
import re

from backend.core.collections import dedupe_preserve
from backend.core.database import get_collection
from backend.core.exceptions import RepositoryError
from backend.core.observability import traceable_op
from backend.schemas.job import INDUSTRY_STANDARD_DICTIONARY


def _normalize_doc(doc: dict | None) -> dict | None:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

def get_candidate_by_id(candidate_id: str) -> Optional[dict]:
    """Retrieve a single candidate document by its candidate_id."""
    candidates = get_collection("candidates")
    try:
        return _normalize_doc(candidates.find_one({"candidate_id": candidate_id}))
    except Exception as exc:
        raise RepositoryError("Failed to read candidate document.") from exc


@traceable_op(name="mongo.get_candidates_by_ids", run_type="retriever", tags=["mongo"])
def get_candidates_by_ids(candidate_ids: list[str]) -> dict[str, dict]:
    """Batch-load candidate documents indexed by candidate_id."""
    if not candidate_ids:
        return {}

    candidates = get_collection("candidates")
    unique_ids = [candidate_id for candidate_id in dedupe_preserve(candidate_ids) if candidate_id]
    try:
        cursor = candidates.find({"candidate_id": {"$in": unique_ids}})
        docs: dict[str, dict] = {}
        for doc in cursor:
            normalized = _normalize_doc(doc)
            if not normalized:
                continue
            candidate_id = normalized.get("candidate_id")
            if candidate_id:
                docs[candidate_id] = normalized
        return docs
    except Exception as exc:
        raise RepositoryError("Failed to batch-read candidate documents.") from exc


_EDU_PATTERNS = {
    "Bachelor": ("bachelor", "bachelors", "b.tech", "btech", "b.e", "be ", "b.sc", "bsc", "ba "),
    "Master": ("master", "masters", "m.tech", "mtech", "m.e", "m.sc", "msc", "mba", "ms "),
    "PhD": ("phd", "doctor", "doctorate", "dphil"),
}
_REGION_ALIASES = {
    "us": "United States",
    "u.s.": "United States",
    "usa": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "uae": "United Arab Emirates",
    "india": "India",
    "remote": "Remote",
    "wfh": "Remote",
}


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    lowered = value.strip().lower()
    lowered = re.sub(r"[-_]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered)


def _to_display_label(value: str) -> str:
    token = _normalize_text(value)
    if not token:
        return ""
    if token == "e commerce":
        return "E-commerce"
    return " ".join(part.capitalize() for part in token.split(" "))


def _extract_region_tokens(doc: dict[str, Any]) -> list[str]:
    out: list[str] = []
    metadata = doc.get("metadata")
    if isinstance(metadata, dict):
        out.append(_normalize_text(metadata.get("location")))

    parsed = doc.get("parsed")
    parsed = parsed if isinstance(parsed, dict) else {}
    for item in parsed.get("experience_items") or []:
        if isinstance(item, dict):
            out.append(_normalize_text(item.get("location")))
    for item in parsed.get("education") or []:
        if isinstance(item, dict):
            out.append(_normalize_text(item.get("location")))
    return [token for token in out if token]


def _extract_education_levels(doc: dict[str, Any]) -> set[str]:
    levels: set[str] = set()
    parsed = doc.get("parsed")
    parsed = parsed if isinstance(parsed, dict) else {}
    for item in parsed.get("education") or []:
        if not isinstance(item, dict):
            continue
        degree = _normalize_text(item.get("degree"))
        if not degree:
            continue
        for label, patterns in _EDU_PATTERNS.items():
            if any(pattern in degree for pattern in patterns):
                levels.add(label)
    return levels


def _infer_industries(doc: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    category = _normalize_text(doc.get("category"))
    if category:
        tokens.add(category)

    parsed = doc.get("parsed")
    parsed = parsed if isinstance(parsed, dict) else {}
    for field in ("core_skills", "expanded_skills", "normalized_skills"):
        for skill in parsed.get(field) or []:
            skill_token = _normalize_text(skill)
            if skill_token:
                tokens.add(skill_token)

    matched: set[str] = set()
    joined = " ".join(sorted(tokens))
    for canonical, payload in INDUSTRY_STANDARD_DICTIONARY.items():
        terms = [_normalize_text(canonical), *[_normalize_text(alias) for alias in payload.get("aliases", [])], *[_normalize_text(term) for term in payload.get("category_terms", [])]]
        if any(term and term in joined for term in terms):
            matched.add(_to_display_label(canonical))
    return matched


@traceable_op(name="mongo.get_filter_options", run_type="retriever", tags=["mongo"])
def get_filter_options(limit_docs: int = 5000) -> dict[str, list[str]]:
    candidates = get_collection("candidates")
    try:
        categories = [value for value in candidates.distinct("category") if isinstance(value, str) and value.strip()]
        job_families = sorted({_to_display_label(value) for value in categories if _to_display_label(value)})

        regions: set[str] = set()
        educations: set[str] = set()
        industries: set[str] = set()

        projection = {
            "category": 1,
            "metadata.location": 1,
            "parsed.core_skills": 1,
            "parsed.expanded_skills": 1,
            "parsed.normalized_skills": 1,
            "parsed.experience_items.location": 1,
            "parsed.education.location": 1,
            "parsed.education.degree": 1,
        }
        cursor = candidates.find({}, projection).limit(int(max(1, limit_docs)))
        for doc in cursor:
            for token in _extract_region_tokens(doc):
                if token in _REGION_ALIASES:
                    regions.add(_REGION_ALIASES[token])
                    continue
                if "remote" in token or "wfh" in token:
                    regions.add("Remote")
                    continue
                if "india" in token:
                    regions.add("India")
                    continue
                if "united states" in token or token in {"us", "usa"}:
                    regions.add("United States")
                    continue

            educations.update(_extract_education_levels(doc))
            industries.update(_infer_industries(doc))

        region_values = sorted(regions)
        education_values = [label for label in ("Bachelor", "Master", "PhD") if label in educations]
        industry_values = sorted(industries)

        return {
            "job_families": job_families,
            "educations": education_values,
            "regions": region_values,
            "industries": industry_values,
        }
    except Exception as exc:
        raise RepositoryError("Failed to load filter options from candidate documents.") from exc
