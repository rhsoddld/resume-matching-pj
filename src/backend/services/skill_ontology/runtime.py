from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from backend.schemas.candidate import VersionedSkill

from .constants import VERSION_PATTERNS
from .loader import load_ontology_config
from .normalization import clean_token, dedupe_preserve
from .types import SkillNormalizationResult


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
        loaded = load_ontology_config(config_dir)
        return cls(
            alias_to_canonical=loaded.alias_to_canonical,
            core_taxonomy=loaded.core_taxonomy,
            role_candidates=loaded.role_candidates,
            capability_phrases=loaded.capability_phrases,
            review_required_skills=loaded.review_required_skills,
            versioned_skill_map=loaded.versioned_skill_map,
        )

    def _parse_versioned_token(self, token: str) -> VersionedSkill | None:
        if token in self.versioned_skill_map:
            canonical, version = self.versioned_skill_map[token]
            return VersionedSkill(raw=token, canonical=canonical, version=version)

        for pattern in VERSION_PATTERNS:
            matched = pattern.match(token)
            if not matched:
                continue
            canonical = clean_token(matched.group(1)) or token
            version = clean_token(matched.group(2)) or "unknown"
            canonical = (
                canonical.replace("microsoft sql server", "sql server")
                .replace("ms sql server", "sql server")
            )
            return VersionedSkill(raw=token, canonical=canonical, version=version)
        return None

    def normalize(self, *, raw_skills: Iterable[object], abilities: Iterable[object]) -> SkillNormalizationResult:
        raw_tokens = [clean_token(value) for value in raw_skills]
        ability_tokens = [clean_token(value) for value in abilities]

        raw_dedup = dedupe_preserve([token for token in raw_tokens if token is not None])
        ability_dedup = dedupe_preserve([token for token in ability_tokens if token is not None])
        normalized_skills = dedupe_preserve([*raw_dedup, *ability_dedup])

        canonical_skills: list[str] = []
        alias_applied = False
        for token in normalized_skills:
            canonical = self.alias_to_canonical.get(token, token)
            if canonical != token:
                alias_applied = True
            canonical_skills.append(canonical)
        canonical_skills = dedupe_preserve(canonical_skills)

        core_skills_exact = {token for token in canonical_skills if token in self.core_taxonomy}
        substring_hits: dict[str, str] = {}
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

        core_skills: list[str] = []
        for token in canonical_skills:
            if token in core_skills_exact:
                core_skills.append(token)
            elif token in substring_hits:
                mapped = substring_hits[token]
                if mapped not in core_skills:
                    core_skills.append(mapped)
        core_skills = dedupe_preserve(core_skills)

        expanded: list[str] = []
        for core in core_skills:
            expanded.append(core)
            for parent in self.core_taxonomy.get(core, {}).get("parents", []):
                parent_token = clean_token(parent)
                if parent_token:
                    expanded.append(parent_token)
        expanded_skills = dedupe_preserve(expanded)

        capability_phrases = dedupe_preserve(
            [token for token in canonical_skills if token in self.capability_phrases]
        )
        role_candidates = dedupe_preserve([token for token in canonical_skills if token in self.role_candidates])
        review_required = dedupe_preserve(
            [token for token in canonical_skills if token in self.review_required_skills]
        )

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

    def find_adjacent_skills(self, skills: Iterable[str], *, limit: int = 12) -> tuple[list[str], list[str]]:
        seeds = [clean_token(skill) for skill in skills]
        canonical_seeds = dedupe_preserve(
            [
                self.alias_to_canonical.get(token, token)
                for token in seeds
                if token is not None and self.alias_to_canonical.get(token, token) in self.core_taxonomy
            ]
        )
        if not canonical_seeds:
            return [], []

        adjacent: list[str] = []
        evidence: list[str] = []
        seed_set = set(canonical_seeds)

        for seed in canonical_seeds:
            seed_meta = self.core_taxonomy.get(seed)
            if not isinstance(seed_meta, dict):
                continue
            seed_domain = clean_token(seed_meta.get("domain"))
            seed_family = clean_token(seed_meta.get("family"))
            seed_parents = {clean_token(parent) for parent in seed_meta.get("parents", [])}
            seed_parents = {parent for parent in seed_parents if parent}

            for skill, meta in self.core_taxonomy.items():
                if skill in seed_set or skill == seed or not isinstance(meta, dict):
                    continue
                domain = clean_token(meta.get("domain"))
                family = clean_token(meta.get("family"))
                parents = {clean_token(parent) for parent in meta.get("parents", [])}
                parents = {parent for parent in parents if parent}

                reason: str | None = None
                if seed_domain and domain and domain == seed_domain:
                    reason = f"shared domain '{seed_domain}'"
                elif seed_family and family and family == seed_family:
                    reason = f"shared family '{seed_family}'"
                elif seed_parents and parents and len(seed_parents.intersection(parents)) > 0:
                    common_parent = sorted(seed_parents.intersection(parents))[0]
                    reason = f"shared parent '{common_parent}'"
                if reason is None:
                    continue

                adjacent.append(skill)
                evidence.append(f"{skill} is adjacent to {seed} via {reason}.")
                if len(adjacent) >= limit:
                    return dedupe_preserve(adjacent), dedupe_preserve(evidence)

        return dedupe_preserve(adjacent), dedupe_preserve(evidence)

    def adjacent_match_score(
        self,
        *,
        job_related_skills: Iterable[str],
        candidate_skills: Iterable[str],
        limit: int = 10,
    ) -> tuple[float, list[str]]:
        related = [clean_token(skill) for skill in job_related_skills]
        candidate = [clean_token(skill) for skill in candidate_skills]

        related_norm = {
            self.alias_to_canonical.get(token, token)
            for token in related
            if token is not None and self.alias_to_canonical.get(token, token)
        }
        candidate_norm = {
            self.alias_to_canonical.get(token, token)
            for token in candidate
            if token is not None and self.alias_to_canonical.get(token, token)
        }
        if not related_norm:
            return 0.0, []

        matches: list[str] = []
        for candidate_skill in sorted(candidate_norm):
            if candidate_skill in related_norm:
                matches.append(candidate_skill)
                continue

            candidate_meta = self.core_taxonomy.get(candidate_skill)
            if not isinstance(candidate_meta, dict):
                continue
            c_domain = clean_token(candidate_meta.get("domain"))
            c_family = clean_token(candidate_meta.get("family"))
            c_parents = {clean_token(parent) for parent in candidate_meta.get("parents", [])}
            c_parents = {parent for parent in c_parents if parent}

            for related_skill in related_norm:
                related_meta = self.core_taxonomy.get(related_skill)
                if not isinstance(related_meta, dict):
                    continue
                r_domain = clean_token(related_meta.get("domain"))
                r_family = clean_token(related_meta.get("family"))
                r_parents = {clean_token(parent) for parent in related_meta.get("parents", [])}
                r_parents = {parent for parent in r_parents if parent}

                if c_domain and r_domain and c_domain == r_domain:
                    matches.append(candidate_skill)
                    break
                if c_family and r_family and c_family == r_family:
                    matches.append(candidate_skill)
                    break
                if c_parents and r_parents and c_parents.intersection(r_parents):
                    matches.append(candidate_skill)
                    break

        deduped_matches = dedupe_preserve(matches)[:limit]
        score = round(len(deduped_matches) / float(len(related_norm)), 4)
        return max(0.0, min(1.0, score)), deduped_matches
