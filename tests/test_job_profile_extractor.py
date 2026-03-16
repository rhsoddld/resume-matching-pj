from __future__ import annotations

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backend.services.job_profile_extractor import build_job_profile


def test_build_job_profile_compresses_overlong_skill_lists() -> None:
    skills = [f"skill{i}" for i in range(1, 41)]
    jd = (
        "We are hiring a backend engineer. Must have "
        + ", ".join(skills)
        + ". Responsibilities include balancing reliability, scalability, cost across internal platforms."
    )

    profile = build_job_profile(jd, ontology=None)

    assert len(profile.required_skills) <= 18
    assert len(profile.related_skills) <= 12
    assert "responsibilities" not in profile.required_skills
    assert "cost" not in profile.required_skills
    assert "nice" not in profile.required_skills

    included_query_skills = [token for token in skills if re.search(rf"\b{token}\b", profile.query_text_for_embedding)]
    assert len(included_query_skills) <= 20


def test_preferred_seniority_does_not_match_internal_word_fragment() -> None:
    jd = "Backend role focused on internal platform integrations and APIs."
    profile = build_job_profile(jd, ontology=None)
    assert profile.preferred_seniority is None


def test_junior_software_role_and_skill_hints_are_extracted() -> None:
    jd = (
        "We are looking for a junior software engineer. "
        "Requirements: foundational programming in Python or Java, understanding of data structures, "
        "and familiarity with Git. Nice to have unit testing basics."
    )
    profile = build_job_profile(jd, ontology=None)
    required = set(profile.required_skills)
    related = set(profile.related_skills)
    assert "junior software engineer" in profile.roles
    assert {"python", "java", "git"} <= required
    assert {"data structures", "unit testing"} <= related


def test_senior_architect_role_and_skill_hints_are_extracted() -> None:
    jd = (
        "We are looking for a senior architect. "
        "Responsibilities include architecture review practices and architecture governance. "
        "Requirements: distributed systems, cloud architecture, and security by design."
    )
    profile = build_job_profile(jd, ontology=None)
    required = set(profile.required_skills)
    assert "senior architect" in profile.roles
    assert {"system architecture", "distributed systems", "cloud architecture", "technical leadership", "security by design"} & required


def test_role_specific_embed_cap_expands_for_senior_architect() -> None:
    skills = [f"skill{i}" for i in range(1, 41)]
    jd = "We are looking for a senior architect. Must have " + ", ".join(skills)
    profile = build_job_profile(jd, ontology=None)
    included_query_skills = [token for token in skills if re.search(rf"\b{token}\b", profile.query_text_for_embedding)]
    assert len(included_query_skills) > 20
    assert len(included_query_skills) <= 28


def test_job_profile_avoids_generic_core_noise_and_keeps_related_requirements() -> None:
    jd = (
        "We are hiring a business analyst consulting role. "
        "The main focus is guiding client change programs and process support. "
        "Requirements: requirements management, stakeholder management, SQL, reporting. "
        "Nice to have operational improvement and process mapping."
    )

    profile = build_job_profile(jd, ontology=None)
    required = set(profile.required_skills)
    related = set(profile.related_skills)

    assert "business analyst" in profile.roles
    assert "stakeholder management" in required
    assert "sql" in required
    assert {"requirements gathering", "process mapping", "reporting"} <= related
    assert {"role", "main", "focus", "client", "change", "support", "consulting"} & required == set()
