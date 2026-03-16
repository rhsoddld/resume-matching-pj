"""Load job filter options from config/job_filters.yml and merge current ontology (skill_taxonomy.yml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.core.providers import CONFIG_DIR

_FILTERS_PATH = CONFIG_DIR / "job_filters.yml"
_TAXONOMY_PATH = CONFIG_DIR / "skill_taxonomy.yml"


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _ensure_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if x is not None and str(x).strip()]
    return []


def _ensure_dict_of_dicts(value: Any) -> dict[str, dict[str, list[str]]]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, dict[str, list[str]]] = {}
    for k, v in value.items():
        key = str(k).strip().lower() if k else ""
        if not key:
            continue
        if not isinstance(v, dict):
            continue
        aliases = _ensure_list(v.get("aliases"))
        category_terms = _ensure_list(v.get("category_terms"))
        out[key] = {"aliases": aliases, "category_terms": category_terms}
    return out


def _collect_taxonomy_domains_and_families() -> tuple[set[str], set[str]]:
    """Collect unique domain and family values from skill_taxonomy.yml (current ontology)."""
    doc = _load_yaml(_TAXONOMY_PATH)
    domains: set[str] = set()
    families: set[str] = set()
    if not isinstance(doc, dict):
        return domains, families
    for _skill, payload in doc.items():
        if not isinstance(payload, dict):
            continue
        d = payload.get("domain")
        if isinstance(d, str) and d.strip():
            domains.add(d.strip().lower().replace(" ", "_"))
        f = payload.get("family")
        if isinstance(f, str) and f.strip():
            families.add(f.strip().lower().replace(" ", "_"))
    return domains, families


def _minimal_entry(token: str) -> dict[str, list[str]]:
    """One-off entry for ontology-derived options (key as alias and category_term)."""
    return {"aliases": [token], "category_terms": [token]}


def _load() -> tuple[dict[str, dict[str, list[str]]], dict[str, dict[str, list[str]]], list[str], list[str]]:
    try:
        data = _load_yaml(_FILTERS_PATH)
        industries = _ensure_dict_of_dicts(data.get("industries"))
        job_families = _ensure_dict_of_dicts(data.get("job_families"))
        educations = _ensure_list(data.get("educations"))
        regions = _ensure_list(data.get("regions"))

        # Merge current ontology: add taxonomy domains as industries, families as job_families if missing
        ontology_domains, ontology_families = _collect_taxonomy_domains_and_families()
        for domain in ontology_domains:
            if domain and domain not in industries:
                industries[domain] = _minimal_entry(domain)
        for family in ontology_families:
            if family and family not in job_families:
                job_families[family] = _minimal_entry(family)

        if not educations:
            educations = ["Bachelor", "Master", "PhD"]
        if not regions:
            regions = ["India", "Remote", "United Kingdom", "United States"]
        return industries, job_families, educations, regions
    except Exception:
        # Fallback so app can start when config is missing or invalid (e.g. wrong CONFIG_DIR in Docker)
        _default_industries = {"technology": _minimal_entry("technology")}
        _default_families = {"software engineering": _minimal_entry("software engineering")}
        return (
            _default_industries,
            _default_families,
            ["Bachelor", "Master", "PhD"],
            ["India", "Remote", "United Kingdom", "United States"],
        )


(
    INDUSTRY_STANDARD_DICTIONARY,
    JOB_FAMILY_STANDARD_DICTIONARY,
    EDUCATION_STANDARD_OPTIONS,
    REGION_STANDARD_OPTIONS,
) = _load()


def get_filter_options() -> dict[str, list[str]]:
    """Return job_families, educations, regions, industries as sorted lists for the API (curated + ontology)."""
    def to_display_label(key: Any) -> str:
        token = str(key).strip().lower().replace("-", " ").replace("_", " ")
        if not token:
            return ""
        if token == "e commerce":
            return "E-commerce"
        if token == "ci cd":
            return "CI/CD"
        return " ".join(part.capitalize() for part in token.split())

    try:
        job_families = sorted([to_display_label(k) for k in JOB_FAMILY_STANDARD_DICTIONARY.keys()])
        educations_sorted = sorted(EDUCATION_STANDARD_OPTIONS)
        regions_sorted = sorted(REGION_STANDARD_OPTIONS)
        industries = sorted([to_display_label(k) for k in INDUSTRY_STANDARD_DICTIONARY.keys()])
        return {
            "job_families": job_families,
            "educations": educations_sorted,
            "regions": regions_sorted,
            "industries": industries,
        }
    except Exception:
        return {
            "job_families": ["Software Engineering", "Data Engineering", "Product Management"],
            "educations": ["Bachelor", "Master", "PhD"],
            "regions": ["India", "Remote", "United Kingdom", "United States"],
            "industries": ["Technology", "Finance", "Healthcare"],
        }
