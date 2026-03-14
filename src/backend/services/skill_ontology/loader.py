from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .normalization import clean_token


@dataclass(frozen=True)
class LoadedOntologyConfig:
    alias_to_canonical: dict[str, str]
    core_taxonomy: dict[str, dict[str, Any]]
    role_candidates: set[str]
    capability_phrases: set[str]
    review_required_skills: set[str]
    versioned_skill_map: dict[str, tuple[str, str]]


def load_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file_obj:
        return yaml.safe_load(file_obj) or {}


def load_ontology_config(config_dir: Path) -> LoadedOntologyConfig:
    aliases_doc = load_yaml(config_dir / "skill_aliases.yml")
    taxonomy_doc = load_yaml(config_dir / "skill_taxonomy.yml")
    role_doc = load_yaml(config_dir / "skill_role_candidates.yml")
    capability_doc = load_yaml(config_dir / "skill_capability_phrases.yml")
    versioned_doc = load_yaml(config_dir / "versioned_skills.yml")
    review_doc = load_yaml(config_dir / "skill_review_required.yml")

    alias_to_canonical: dict[str, str] = {}
    for raw_canonical, payload in aliases_doc.items():
        canonical = clean_token(raw_canonical)
        if not canonical:
            continue
        alias_to_canonical[canonical] = canonical
        aliases = payload.get("aliases", []) if isinstance(payload, dict) else []
        for alias in aliases:
            norm_alias = clean_token(alias)
            if norm_alias:
                alias_to_canonical[norm_alias] = canonical

    core_taxonomy: dict[str, dict[str, Any]] = {}
    for raw_skill, payload in taxonomy_doc.items():
        skill = clean_token(raw_skill)
        if not skill or not isinstance(payload, dict):
            continue
        core_taxonomy[skill] = {
            "domain": payload.get("domain"),
            "family": payload.get("family"),
            "parents": [parent for parent in payload.get("parents", []) if isinstance(parent, str)],
        }

    roles = {token for token in (clean_token(key) for key in role_doc.keys()) if token}
    capabilities = {token for token in (clean_token(key) for key in capability_doc.keys()) if token}

    versioned_map: dict[str, tuple[str, str]] = {}
    for raw_skill, payload in versioned_doc.items():
        raw_token = clean_token(raw_skill)
        if not raw_token or not isinstance(payload, dict):
            continue
        canonical = clean_token(payload.get("canonical")) or raw_token
        version = clean_token(payload.get("version")) or "unknown"
        versioned_map[raw_token] = (canonical, version)

    review_terms: set[str] = set()
    ambiguous = review_doc.get("ambiguous_skills", []) if isinstance(review_doc, dict) else []
    for item in ambiguous:
        if not isinstance(item, dict):
            continue
        token = clean_token(item.get("token"))
        if token:
            review_terms.add(token)
    for key in ("taxonomy_review_required", "canonical_merge_candidates"):
        rows = review_doc.get(key, []) if isinstance(review_doc, dict) else []
        for item in rows:
            if not isinstance(item, dict):
                continue
            token = clean_token(item.get("token"))
            if token:
                review_terms.add(token)

    return LoadedOntologyConfig(
        alias_to_canonical=alias_to_canonical,
        core_taxonomy=core_taxonomy,
        role_candidates=roles,
        capability_phrases=capabilities,
        review_required_skills=review_terms,
        versioned_skill_map=versioned_map,
    )
