"""Deterministic evaluation metrics for quality, diversity, and culture fit."""

from __future__ import annotations

from collections import Counter
import math
import re
from typing import Any


_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.#/-]*")
_YEARS_RE = re.compile(
    r"(?P<min>\d+)\s*(?:\+|plus)?\s*(?:-|to)?\s*(?P<max>\d+)?\s*years?",
    flags=re.IGNORECASE,
)

_CULTURE_SIGNAL_SYNONYMS: dict[str, tuple[str, ...]] = {
    "collaboration": ("team", "cross-functional", "stakeholder", "collaboration", "collaborating"),
    "ownership": ("ownership", "own", "drive", "accountability", "responsibility"),
    "communication": ("communication", "communicate", "presentation", "verbal", "written"),
    "adaptability": ("startup", "fast-paced", "dynamic", "adaptability", "adaptable"),
    "leadership": ("lead", "leadership", "mentor", "coaching", "manage"),
}

_POTENTIAL_SIGNAL_SYNONYMS: dict[str, tuple[str, ...]] = {
    "learning_agility": ("learn", "learning", "upskill", "self-driven", "curious", "adapt"),
    "growth_trajectory": ("promotion", "progression", "growth", "trajectory", "expanded scope"),
    "leadership_readiness": ("lead", "mentor", "ownership", "initiative", "drive"),
    "problem_solving": ("problem", "solve", "debug", "optimize", "improve", "root cause"),
}

_SKILL_STOPWORDS = {
    "and",
    "with",
    "for",
    "the",
    "role",
    "position",
    "must",
    "have",
    "experience",
    "years",
    "strong",
    "required",
    "plus",
    "preferred",
    "knowledge",
    "seeking",
    "looking",
    "responsible",
    "build",
    "maintain",
}

_FAMILY_HINTS: dict[str, tuple[str, ...]] = {
    "data": ("data scientist", "data engineer", "machine learning", "etl", "airflow", "spark"),
    "frontend": ("frontend", "react", "typescript", "css", "web interface"),
    "backend": ("backend", "fastapi", "django", "redis", "api design"),
    "devops_cloud": ("devops", "kubernetes", "terraform", "cloud architect", "infrastructure"),
    "security": ("security", "siem", "incident response", "forensics", "cybersecurity"),
    "product_business": ("product manager", "business analyst", "roadmap", "prd", "stakeholder"),
    "mobile_blockchain": ("android", "kotlin", "solidity", "defi", "ethereum"),
    "non_tech": ("receptionist", "coordinator", "onboarding documentation", "telephone etiquette", "hr"),
}


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text or "")]


def infer_job_family(job_description: str) -> str:
    jd = (job_description or "").lower()
    for family, hints in _FAMILY_HINTS.items():
        if any(hint in jd for hint in hints):
            return family
    return "other"


def extract_min_experience_years(job_description: str) -> float | None:
    jd = job_description or ""
    match = _YEARS_RE.search(jd)
    if not match:
        return None
    min_value = float(match.group("min"))
    return min_value


def extract_expected_skills(entry: dict[str, Any]) -> set[str]:
    declared = entry.get("expected_skills")
    if isinstance(declared, list):
        cleaned = {str(item).strip().lower() for item in declared if str(item).strip()}
        if cleaned:
            return cleaned

    tokens = _tokenize(str(entry.get("job_description") or ""))
    return {
        token
        for token in tokens
        if len(token) > 2 and token not in _SKILL_STOPWORDS and not token.isdigit()
    }


def extract_culture_targets(entry: dict[str, Any]) -> set[str]:
    declared = entry.get("target_culture_signals")
    if isinstance(declared, list):
        cleaned = {str(item).strip().lower() for item in declared if str(item).strip()}
        if cleaned:
            return cleaned

    jd = str(entry.get("job_description") or "").lower()
    matched = {
        signal
        for signal, keywords in _CULTURE_SIGNAL_SYNONYMS.items()
        if any(keyword in jd for keyword in keywords)
    }
    if matched:
        return matched
    return {"collaboration", "communication"}


def score_skill_coverage(expected_skills: set[str], candidate_skills: set[str]) -> float:
    if not expected_skills:
        return 0.0
    overlap = expected_skills.intersection(candidate_skills)
    return round(len(overlap) / float(len(expected_skills)), 4)


def score_experience_fit(required_years: float | None, candidate_years: float | None) -> float:
    if candidate_years is None:
        return 0.0
    if required_years is None or required_years <= 0:
        return 0.5

    ratio = float(candidate_years) / float(required_years)
    if ratio <= 1.0:
        return round(max(0.0, min(1.0, ratio)), 4)

    over_penalty = min(0.35, (ratio - 1.0) * 0.20)
    return round(max(0.0, min(1.0, 1.0 - over_penalty)), 4)


def score_culture_fit(
    *,
    target_signals: set[str],
    candidate_signals: set[str],
    candidate_summary: str = "",
) -> float:
    if not target_signals:
        return 0.0
    evidence = {signal.lower() for signal in candidate_signals}
    summary = candidate_summary.lower()
    lexical_hits = {
        signal
        for signal, keywords in _CULTURE_SIGNAL_SYNONYMS.items()
        if any(keyword in summary for keyword in keywords)
    }
    total_hits = target_signals.intersection(evidence.union(lexical_hits))
    return round(len(total_hits) / float(len(target_signals)), 4)


def score_potential_fit(
    *,
    job_description: str,
    candidate_summary: str = "",
    candidate_signals: set[str] | None = None,
) -> float:
    jd = (job_description or "").lower()
    summary = (candidate_summary or "").lower()
    explicit = {s.lower() for s in (candidate_signals or set())}

    demand_hits = 0
    evidence_hits = 0
    for _, keywords in _POTENTIAL_SIGNAL_SYNONYMS.items():
        demand = any(keyword in jd for keyword in keywords)
        evidence = any(keyword in summary for keyword in keywords) or any(keyword in explicit for keyword in keywords)
        if demand:
            demand_hits += 1
        if evidence:
            evidence_hits += 1

    if demand_hits == 0:
        return round(min(1.0, evidence_hits / 2.0), 4)
    return round(max(0.0, min(1.0, evidence_hits / float(demand_hits))), 4)


def score_custom_quality(
    *,
    skill_score: float,
    experience_score: float,
    culture_score: float,
    potential_score: float = 0.0,
) -> float:
    weighted = (
        (skill_score * 0.40)
        + (experience_score * 0.30)
        + (culture_score * 0.20)
        + (potential_score * 0.10)
    )
    return round(max(0.0, min(1.0, weighted)), 4)


def build_synthetic_candidate(entry: dict[str, Any]) -> dict[str, Any]:
    label = str(entry.get("expected_label") or "neutral").lower()
    expected_skills = sorted(extract_expected_skills(entry))
    required_exp = extract_min_experience_years(str(entry.get("job_description") or ""))
    culture_targets = extract_culture_targets(entry)

    if label == "good":
        chosen = set(expected_skills[: max(2, math.ceil(len(expected_skills) * 0.85))])
        years = (required_exp or 3.0) + 1.0
        culture = set(culture_targets)
        summary = "Strong collaboration, ownership, and communication. Demonstrates initiative, growth, and mentorship."
    elif label == "bad":
        chosen = {"python", "sql"} if "python" not in expected_skills else {"excel", "scheduling"}
        years = None
        culture = set()
        summary = "Generic profile with little soft-skill evidence."
    else:
        chosen = set(expected_skills[: max(1, int(len(expected_skills) * 0.45))])
        years = max(0.0, (required_exp or 2.0) - 0.5)
        culture = {"communication", "collaboration"}
        summary = "Partial alignment with team communication and collaboration."

    return {
        "candidate_skills": chosen,
        "candidate_experience_years": years,
        "candidate_culture_signals": culture,
        "candidate_summary": summary,
    }


def _shannon_entropy(values: list[str]) -> float:
    if not values:
        return 0.0
    total = len(values)
    entropy = 0.0
    for count in Counter(values).values():
        p = count / float(total)
        entropy -= p * math.log2(p)
    return entropy


def build_diversity_report(entries: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [str(e.get("expected_label") or "unknown").lower() for e in entries]
    families = [
        str(e.get("job_family") or "").strip().lower() or infer_job_family(str(e.get("job_description") or ""))
        for e in entries
    ]
    skill_vocab: set[str] = set()
    for entry in entries:
        skill_vocab.update(extract_expected_skills(entry))

    family_entropy = _shannon_entropy(families)
    family_unique = len(set(families))
    max_family_entropy = math.log2(max(1, family_unique))
    family_entropy_norm = (family_entropy / max_family_entropy) if max_family_entropy > 0 else 0.0

    label_counts = Counter(labels)
    family_counts = Counter(families)

    return {
        "total_entries": len(entries),
        "label_distribution": dict(sorted(label_counts.items())),
        "family_distribution": dict(sorted(family_counts.items())),
        "family_count": family_unique,
        "family_entropy": round(family_entropy, 4),
        "family_entropy_normalized": round(family_entropy_norm, 4),
        "skill_vocabulary_size": len(skill_vocab),
    }
