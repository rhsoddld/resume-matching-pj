from __future__ import annotations

from dataclasses import dataclass

from backend.schemas.candidate import VersionedSkill


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
