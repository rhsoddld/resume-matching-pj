from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable

import yaml

from backend.schemas.candidate import VersionedSkill


# skill_aliases.yml로 커버되지 않는 소수 케이스에 대한 전수려 파이프라인내 단일 매핑
# alias_to_canonical 단계에서 처리되지 않는 raw token에만 적용
LEGACY_LEXICAL_NORMALIZATION: dict[str, str] = {
    "mongo db": "mongodb",        # 공백 스타일 원본
    "mongo db-3.2": "mongodb",    # 버전 접미사 변형
    "ms office": "microsoft office",  # 엄격한 표기를 유지
    # note: ms excel/microsoft excel 등은 skill_aliases.yml에서 커버
    # note: ssrs는 skill_aliases.yml로 커버; 더 이상 엄리설 필요 없음
}

VERSION_PATTERNS = [
    re.compile(r"^(sql server|ms sql server|microsoft sql server)\s+([0-9]{4}(?:\s*r2)?|[0-9]{4}r2)$"),
    re.compile(r"^(windows(?: server)?)\s+(xp|nt|7|8|10|[0-9]{4})$"),
    re.compile(r"^(oracle)\s+([0-9]+(?:\.[0-9]+)+|[0-9]{1,2}[a-z](?:r[0-9]+)?|[0-9]{1,2}[a-z]/[0-9]{1,2}[a-z])$"),
    re.compile(r"^(oracle)\s+([0-9]{1,2}[a-z]\s+rac)$"),
]


def _clean_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip().lower()
    if not token:
        return None
    token = re.sub(r"\s+", " ", token)
    token = token.replace("&", " and ")
    token = re.sub(r"\s+", " ", token).strip(" ,;:/|")
    if not token:
        return None
    return LEGACY_LEXICAL_NORMALIZATION.get(token, token)


def _dedupe_preserve(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass
class SkillNormalizationResult:
    normalized_skills: list[str]
    canonical_skills: list[str]
    core_skills: list[str]
    expanded_skills: list[str]
    capability_phrases: list[str]
    role_candidates: list[str]
    review_required_skills: list[str]
    versioned_skills: list[VersionedSkill]
    alias_applied: bool
    taxonomy_applied: bool


@dataclass
class RuntimeSkillOntology:
    alias_to_canonical: dict[str, str]
    core_taxonomy: dict[str, dict[str, Any]]
    role_candidates: set[str]
    capability_phrases: set[str]
    review_required_skills: set[str]
    versioned_skill_map: dict[str, tuple[str, str]]

    @classmethod
    def load_from_config(cls, config_dir: Path) -> "RuntimeSkillOntology":
        aliases_doc = _load_yaml(config_dir / "skill_aliases.yml")
        taxonomy_doc = _load_yaml(config_dir / "skill_taxonomy.yml")
        role_doc = _load_yaml(config_dir / "skill_role_candidates.yml")
        capability_doc = _load_yaml(config_dir / "skill_capability_phrases.yml")
        versioned_doc = _load_yaml(config_dir / "versioned_skills.yml")
        review_doc = _load_yaml(config_dir / "skill_review_required.yml")

        alias_to_canonical: dict[str, str] = {}
        for raw_canonical, payload in aliases_doc.items():
            canonical = _clean_token(raw_canonical)
            if not canonical:
                continue
            alias_to_canonical[canonical] = canonical
            aliases = payload.get("aliases", []) if isinstance(payload, dict) else []
            for alias in aliases:
                norm_alias = _clean_token(alias)
                if norm_alias:
                    alias_to_canonical[norm_alias] = canonical

        core_taxonomy: dict[str, dict[str, Any]] = {}
        for raw_skill, payload in taxonomy_doc.items():
            skill = _clean_token(raw_skill)
            if not skill or not isinstance(payload, dict):
                continue
            core_taxonomy[skill] = {
                "domain": payload.get("domain"),
                "family": payload.get("family"),
                "parents": [p for p in payload.get("parents", []) if isinstance(p, str)],
            }

        roles = {t for t in (_clean_token(k) for k in role_doc.keys()) if t}
        capabilities = {t for t in (_clean_token(k) for k in capability_doc.keys()) if t}

        versioned_map: dict[str, tuple[str, str]] = {}
        for raw_skill, payload in versioned_doc.items():
            raw_token = _clean_token(raw_skill)
            if not raw_token or not isinstance(payload, dict):
                continue
            canonical = _clean_token(payload.get("canonical")) or raw_token
            version = _clean_token(payload.get("version")) or "unknown"
            versioned_map[raw_token] = (canonical, version)

        review_terms: set[str] = set()
        ambiguous = review_doc.get("ambiguous_skills", []) if isinstance(review_doc, dict) else []
        for item in ambiguous:
            if not isinstance(item, dict):
                continue
            token = _clean_token(item.get("token"))
            if token:
                review_terms.add(token)
        for key in ("taxonomy_review_required", "canonical_merge_candidates"):
            rows = review_doc.get(key, []) if isinstance(review_doc, dict) else []
            for item in rows:
                if not isinstance(item, dict):
                    continue
                token = _clean_token(item.get("token"))
                if token:
                    review_terms.add(token)

        return cls(
            alias_to_canonical=alias_to_canonical,
            core_taxonomy=core_taxonomy,
            role_candidates=roles,
            capability_phrases=capabilities,
            review_required_skills=review_terms,
            versioned_skill_map=versioned_map,
        )

    def _parse_versioned_token(self, token: str) -> VersionedSkill | None:
        if token in self.versioned_skill_map:
            canonical, version = self.versioned_skill_map[token]
            return VersionedSkill(raw=token, canonical=canonical, version=version)
        for pattern in VERSION_PATTERNS:
            m = pattern.match(token)
            if not m:
                continue
            canonical = _clean_token(m.group(1)) or token
            version = _clean_token(m.group(2)) or "unknown"
            canonical = canonical.replace("microsoft sql server", "sql server").replace("ms sql server", "sql server")
            return VersionedSkill(raw=token, canonical=canonical, version=version)
        return None

    def normalize(self, *, raw_skills: Iterable[object], abilities: Iterable[object]) -> SkillNormalizationResult:
        raw_tokens = [_clean_token(v) for v in raw_skills]
        ability_tokens = [_clean_token(v) for v in abilities]
        raw_dedup = _dedupe_preserve([t for t in raw_tokens if t is not None])
        ability_dedup = _dedupe_preserve([t for t in ability_tokens if t is not None])

        pipeline_tokens = _dedupe_preserve([*raw_dedup, *ability_dedup])
        normalized_skills = pipeline_tokens

        canonical_skills: list[str] = []
        alias_applied = False
        for token in normalized_skills:
            canonical = self.alias_to_canonical.get(token, token)
            if canonical != token:
                alias_applied = True
            canonical_skills.append(canonical)
        canonical_skills = _dedupe_preserve(canonical_skills)

        # 1) exact match
        core_skills_exact = {t for t in canonical_skills if t in self.core_taxonomy}

        # 2) substring match: taxonomy key가 token 안에 포함된 경우
        #    예: "sql server 2012" → "sql server" ⊂ token → hit
        #    단, taxonomy key가 5자 이상인 경우만 적용 (단문자 키 오탐 방지)
        substring_hits: dict[str, str] = {}  # token → best_tax_key (가장 긴 것)
        for token in canonical_skills:
            if token in core_skills_exact:
                continue
            best: str | None = None
            for tax_key in self.core_taxonomy:
                if len(tax_key) >= 5 and tax_key in token:
                    if best is None or len(tax_key) > len(best):
                        best = tax_key
            if best:
                substring_hits[token] = best

        core_skills = []
        for token in canonical_skills:
            if token in core_skills_exact:
                core_skills.append(token)
            elif token in substring_hits:
                mapped = substring_hits[token]
                if mapped not in core_skills:
                    core_skills.append(mapped)
        core_skills = _dedupe_preserve(core_skills)

        expanded: list[str] = []
        for core in core_skills:
            expanded.append(core)
            for parent in self.core_taxonomy.get(core, {}).get("parents", []):
                parent_token = _clean_token(parent)
                if parent_token:
                    expanded.append(parent_token)
        expanded_skills = _dedupe_preserve(expanded)

        capability_phrases = _dedupe_preserve([t for t in canonical_skills if t in self.capability_phrases])
        role_candidates = _dedupe_preserve([t for t in canonical_skills if t in self.role_candidates])
        review_required = _dedupe_preserve([t for t in canonical_skills if t in self.review_required_skills])

        versioned_seen: set[tuple[str, str, str]] = set()
        versioned_skills: list[VersionedSkill] = []
        for token in canonical_skills:
            parsed = self._parse_versioned_token(token)
            if not parsed:
                continue
            key = (parsed.raw, parsed.canonical, parsed.version)
            if key in versioned_seen:
                continue
            versioned_seen.add(key)
            versioned_skills.append(parsed)

        taxonomy_applied = any(
            [
                bool(core_skills),
                bool(expanded_skills),
                bool(capability_phrases),
                bool(role_candidates),
                bool(review_required),
                bool(versioned_skills),
            ]
        )

        return SkillNormalizationResult(
            normalized_skills=normalized_skills,
            canonical_skills=canonical_skills,
            core_skills=core_skills,
            expanded_skills=expanded_skills,
            capability_phrases=capability_phrases,
            role_candidates=role_candidates,
            review_required_skills=review_required,
            versioned_skills=versioned_skills,
            alias_applied=alias_applied,
            taxonomy_applied=taxonomy_applied,
        )

