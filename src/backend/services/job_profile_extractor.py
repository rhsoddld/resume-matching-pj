from __future__ import annotations

from dataclasses import dataclass
import re

from backend.core.collections import dedupe_preserve
from backend.services.skill_ontology import RuntimeSkillOntology


_SKILL_SPLIT_RE = re.compile(r"[,\n;/|]+")
_SKILL_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9+.#-]{1,}")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.IGNORECASE)
_SKILL_STOPWORDS = {
    "and",
    "or",
    "the",
    "with",
    "for",
    "from",
    "into",
    "years",
    "year",
    "experience",
    "required",
    "preferred",
    "plus",
}
_SENIORITY_KEYWORDS = ("intern", "junior", "mid", "senior", "lead", "staff", "principal")


@dataclass
class JobProfile:
    required_skills: list[str]
    expanded_skills: list[str]
    required_experience_years: float | None
    preferred_seniority: str | None


def _extract_job_skill_candidates(job_description: str) -> list[str]:
    if not job_description:
        return []

    lowered = job_description.lower()
    chunks = [part.strip() for part in _SKILL_SPLIT_RE.split(lowered)]

    candidates: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        cleaned = re.sub(r"\s+", " ", chunk).strip(" .:-")
        if cleaned and len(cleaned) <= 64:
            candidates.append(cleaned)
        for token in _SKILL_TOKEN_RE.findall(cleaned):
            if token in _SKILL_STOPWORDS:
                continue
            candidates.append(token)
    return dedupe_preserve(candidates)


def _extract_required_experience_years(job_description: str) -> float | None:
    if not job_description:
        return None
    matches = [float(value) for value in _YEARS_RE.findall(job_description)]
    if not matches:
        return None
    return max(matches)


def _extract_preferred_seniority(job_description: str) -> str | None:
    lowered = job_description.lower()
    for keyword in _SENIORITY_KEYWORDS:
        if keyword in lowered:
            return keyword
    return None


def build_job_profile(job_description: str, ontology: RuntimeSkillOntology | None) -> JobProfile:
    raw_candidates = _extract_job_skill_candidates(job_description)
    if ontology is None:
        required_skills = raw_candidates
        expanded_skills = raw_candidates
    else:
        normalized = ontology.normalize(raw_skills=raw_candidates, abilities=[])
        required_skills = normalized.core_skills or normalized.canonical_skills or normalized.normalized_skills
        expanded_skills = normalized.expanded_skills or required_skills

    return JobProfile(
        required_skills=dedupe_preserve(required_skills),
        expanded_skills=dedupe_preserve(expanded_skills),
        required_experience_years=_extract_required_experience_years(job_description),
        preferred_seniority=_extract_preferred_seniority(job_description),
    )
