"""Row-level ingestion transformers."""

from __future__ import annotations

from typing import Sequence

from backend.schemas.candidate import ParsedEducation, ParsedExperienceItem, ParsedSection
from backend.services.ingestion.constants import SNEHA_CATEGORY_SKILL_MAP
from backend.services.ingestion.preprocessing import clean_text, dedupe_preserve, normalize_month
from backend.services.skill_ontology import RuntimeSkillOntology


def _record_value(record: object, key: str) -> object:
    if isinstance(record, dict):
        return record.get(key)
    return getattr(record, key, None)


def to_parsed_education(records: Sequence[object]) -> list[ParsedEducation]:
    items: list[ParsedEducation] = []
    for record in records:
        items.append(
            ParsedEducation(
                degree=clean_text(_record_value(record, "degree")),
                institution=clean_text(_record_value(record, "institution")),
                start_date=normalize_month(_record_value(record, "start_date")),
                end_date=normalize_month(_record_value(record, "end_date")),
                location=clean_text(_record_value(record, "location")),
            )
        )
    return items


def to_parsed_experience(records: Sequence[object]) -> list[ParsedExperienceItem]:
    items: list[ParsedExperienceItem] = []
    for record in records:
        items.append(
            ParsedExperienceItem(
                title=clean_text(_record_value(record, "title")),
                company=clean_text(_record_value(record, "company")),
                start_date=normalize_month(_record_value(record, "start_date")),
                end_date=normalize_month(_record_value(record, "end_date")),
                location=clean_text(_record_value(record, "location")),
                description=clean_text(_record_value(record, "description")),
            )
        )
    return items


def inject_sneha_category_skill(
    *,
    parsed: ParsedSection,
    category: str | None,
    ontology: RuntimeSkillOntology,
) -> None:
    if not category:
        return

    category_skill = SNEHA_CATEGORY_SKILL_MAP.get(category.upper())
    if not category_skill:
        return

    if category_skill not in parsed.core_skills:
        parsed.core_skills = [category_skill, *parsed.core_skills]
    if category_skill not in parsed.canonical_skills:
        parsed.canonical_skills = [category_skill, *parsed.canonical_skills]
    if category_skill not in parsed.expanded_skills:
        parents = ontology.core_taxonomy.get(category_skill, {}).get("parents", [])
        parsed.expanded_skills = [category_skill, *parents, *parsed.expanded_skills]
        parsed.expanded_skills = dedupe_preserve(parsed.expanded_skills)


def build_synthetic_resume_text(
    *,
    name: str | None,
    category: str | None,
    skills: Sequence[str],
    abilities: Sequence[str],
    experience_items: Sequence[ParsedExperienceItem],
    education_items: Sequence[ParsedEducation],
) -> str:
    parts: list[str] = []
    if name:
        parts.append(f"Name: {name}")
    if category:
        parts.append(f"Category: {category}")
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")
    if abilities:
        parts.append("Abilities:")
        parts.extend([f" - {ability}" for ability in abilities])
    if experience_items:
        parts.append("Experience:")
        for exp in experience_items:
            exp_meta = f"{exp.title} at {exp.company}"
            exp_date = f" ({exp.start_date} to {exp.end_date})" if exp.start_date else ""
            parts.append(f" - {exp_meta}{exp_date}")
            if exp.description:
                parts.append(f"   {exp.description}")
    if education_items:
        parts.append("Education:")
        for edu in education_items:
            edu_meta = f"{edu.degree} at {edu.institution}"
            edu_date = f" ({edu.start_date})" if edu.start_date else ""
            parts.append(f" - {edu_meta}{edu_date}")
    return "\n".join(parts)
