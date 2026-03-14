from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.core.collections import dedupe_preserve
from backend.services.job_profile_extractor import JobProfile
from backend.agents.contracts.culture_agent import CultureAgentInput
from backend.agents.contracts.experience_agent import ExperienceAgentInput
from backend.agents.contracts.skill_agent import SkillAgentInput
from backend.agents.contracts.technical_agent import TechnicalAgentInput

from .helpers import parse_date_token
from .types import CandidateInputBundle


def build_candidate_input_bundle(
    *,
    job_description: str,
    job_profile: JobProfile,
    hit: dict[str, Any],
    candidate_doc: dict[str, Any],
) -> CandidateInputBundle:
    parsed = candidate_doc.get("parsed", {})
    parsed = parsed if isinstance(parsed, dict) else {}

    candidate_id = str(hit.get("candidate_id", ""))
    candidate_skills = list(parsed.get("skills", []) or [])
    candidate_normalized_skills = list(parsed.get("normalized_skills", []) or [])
    candidate_core_skills = list(parsed.get("core_skills", []) or [])
    candidate_expanded_skills = list(parsed.get("expanded_skills", []) or [])

    raw_container = candidate_doc.get("raw")
    raw_resume_text = raw_container.get("resume_text") if isinstance(raw_container, dict) else None

    skill_input = SkillAgentInput(
        candidate_id=candidate_id,
        job_description=job_description,
        required_skills=job_profile.required_skills,
        preferred_skills=job_profile.expanded_skills,
        candidate_skills=candidate_skills,
        candidate_normalized_skills=candidate_normalized_skills,
        candidate_core_skills=candidate_core_skills,
        candidate_expanded_skills=candidate_expanded_skills,
        candidate_summary=parsed.get("summary"),
        raw_resume_text=raw_resume_text,
    )
    experience_input = ExperienceAgentInput(
        candidate_id=candidate_id,
        job_description=job_description,
        required_experience_years=job_profile.required_experience_years,
        preferred_seniority=job_profile.preferred_seniority,
        candidate_experience_years=hit.get("experience_years"),
        candidate_seniority_level=hit.get("seniority_level"),
        candidate_experience_items=extract_experience_items(parsed),
        candidate_summary=parsed.get("summary"),
        raw_resume_text=raw_resume_text,
    )
    technical_input = TechnicalAgentInput(
        candidate_id=candidate_id,
        job_description=job_description,
        required_stack=job_profile.required_skills,
        preferred_stack=job_profile.expanded_skills,
        candidate_skills=candidate_normalized_skills,
        candidate_projects=extract_project_evidence(parsed),
        candidate_summary=parsed.get("summary"),
        raw_resume_text=raw_resume_text,
    )
    culture_input = CultureAgentInput(
        candidate_id=candidate_id,
        job_description=job_description,
        target_signals=["communication", "collaboration", "ownership"],
        candidate_signals=list(parsed.get("capability_phrases", []) or []),
        candidate_summary=parsed.get("summary"),
        raw_resume_text=raw_resume_text,
    )
    return CandidateInputBundle(
        candidate_id=candidate_id,
        parsed=parsed,
        skill_input=skill_input,
        experience_input=experience_input,
        technical_input=technical_input,
        culture_input=culture_input,
    )


def build_runtime_payload(
    *,
    job_description: str,
    job_profile: JobProfile,
    hit: dict[str, Any],
    category_filter: str | None,
    bundle: CandidateInputBundle,
) -> dict[str, Any]:
    return {
        "job_description": job_description,
        "job_profile": {
            "required_skills": job_profile.required_skills,
            "expanded_skills": job_profile.expanded_skills,
            "required_experience_years": job_profile.required_experience_years,
            "preferred_seniority": job_profile.preferred_seniority,
        },
        "retrieval_context": {
            "vector_score": round(float(hit.get("score", 0.0)), 4),
            "category": hit.get("category"),
            "category_filter": category_filter,
            "experience_years": hit.get("experience_years"),
            "seniority_level": hit.get("seniority_level"),
        },
        "candidate": {
            "skill_input": bundle.skill_input.model_dump(),
            "experience_input": bundle.experience_input.model_dump(),
            "technical_input": bundle.technical_input.model_dump(),
            "culture_input": bundle.culture_input.model_dump(),
        },
    }


def extract_experience_items(parsed: dict[str, Any]) -> list[str]:
    items = parsed.get("experience_items", [])
    if not isinstance(items, list):
        return []

    out: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        company = item.get("company")
        if title and company:
            out.append(f"{title} at {company}")
        elif title:
            out.append(str(title))
        elif company:
            out.append(str(company))
    return dedupe_preserve(out)


def extract_project_evidence(parsed: dict[str, Any]) -> list[str]:
    items = parsed.get("experience_items", [])
    if not isinstance(items, list):
        return []

    out: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        description = item.get("description")
        if isinstance(description, str) and description.strip():
            out.append(description.strip()[:180])
    return dedupe_preserve(out)


def build_career_trajectory(
    *,
    parsed: dict[str, Any],
    candidate_experience_years: float | None,
    candidate_seniority_level: str | None,
) -> dict[str, Any]:
    items = parsed.get("experience_items") or []
    if not isinstance(items, list) or not items:
        return {
            "has_trajectory": False,
            "seniority_level": candidate_seniority_level,
            "total_experience_years": candidate_experience_years,
            "progression": "insufficient-data",
            "moves": [],
        }

    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "title": str(item.get("title") or "").strip() or None,
                "company": str(item.get("company") or "").strip() or None,
                "start_date": item.get("start_date"),
                "end_date": item.get("end_date"),
                "start_dt": parse_date_token(item.get("start_date")),
            }
        )
    normalized.sort(key=lambda row: row.get("start_dt") or datetime.min)
    if not normalized:
        return {
            "has_trajectory": False,
            "seniority_level": candidate_seniority_level,
            "total_experience_years": candidate_experience_years,
            "progression": "insufficient-data",
            "moves": [],
        }

    moves: list[dict[str, Any]] = []
    for idx, row in enumerate(normalized):
        if idx == 0:
            continue
        prev = normalized[idx - 1]
        if row.get("title") == prev.get("title") and row.get("company") == prev.get("company"):
            continue
        moves.append(
            {
                "from_title": prev.get("title"),
                "to_title": row.get("title"),
                "from_company": prev.get("company"),
                "to_company": row.get("company"),
                "at": row.get("start_date"),
            }
        )

    progression = "stable"
    if len(moves) >= 2:
        progression = "growth"
    if moves and any(move.get("from_company") != move.get("to_company") for move in moves):
        progression = "transition"

    first = normalized[0]
    last = normalized[-1]
    return {
        "has_trajectory": True,
        "seniority_level": candidate_seniority_level,
        "total_experience_years": candidate_experience_years,
        "first_role": {
            "title": first.get("title"),
            "company": first.get("company"),
            "start_date": first.get("start_date"),
        },
        "latest_role": {
            "title": last.get("title"),
            "company": last.get("company"),
            "start_date": last.get("start_date"),
            "end_date": last.get("end_date"),
        },
        "progression": progression,
        "moves": moves[:6],
    }
