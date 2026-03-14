from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services.job_profile_extractor import build_job_profile


def test_build_job_profile_creates_structured_query_fields_without_ontology():
    profile = build_job_profile(
        "Looking for a mid backend engineer with 3+ years of Python, API, microservices, Docker, and Kubernetes experience.",
        ontology=None,
    )

    assert profile.preferred_seniority == "mid"
    assert profile.required_experience_years == 3.0
    assert profile.job_category == "backend engineer"
    assert 0.0 <= profile.confidence <= 1.0
    assert profile.confidence >= 0.7
    assert "python" in profile.required_skills
    assert "docker" in profile.query_text_for_embedding
    assert profile.query_text_for_embedding.startswith("backend engineer")


def test_build_job_profile_respects_request_filters():
    profile = build_job_profile(
        "Hiring an HR manager with recruiting and onboarding experience.",
        ontology=None,
        category_override="HR",
        min_experience_years=5,
    )

    assert profile.job_category == "HR"
    assert profile.filters["category"] == "HR"
    assert profile.filters["min_experience_years"] == 5.0
    assert "recruiting" in profile.required_skills
    assert profile.confidence >= 0.6


def test_build_job_profile_filters_noisy_sentence_tokens():
    profile = build_job_profile(
        "I need someone early in their career who can analyze business data, generate reports, and work with tools used for interpreting datasets.",
        ontology=None,
        category_override="Data Science",
        min_experience_years=2,
    )

    assert profile.job_category == "Data Science"
    assert "need" not in profile.required_skills
    assert "someone" not in profile.required_skills
    assert "their" not in profile.required_skills
    assert "data analysis" in profile.required_skills
    assert "reporting" in profile.required_skills


def test_build_job_profile_backend_sentence_keeps_technical_signals():
    profile = build_job_profile(
        "We are looking for someone who mainly works on the backend of web applications and has experience building services that connect multiple systems. Familiarity with modern deployment environments would be helpful.",
        ontology=None,
        min_experience_years=4,
    )

    assert "we" not in profile.required_skills
    assert "are" not in profile.required_skills
    assert "looking" not in profile.required_skills
    assert "someone" not in profile.required_skills
    assert "backend" in profile.required_skills
    assert "api" in profile.required_skills
    assert "deployment" in profile.required_skills
    assert "backend engineer" in profile.roles
    assert profile.lexical_query
    assert profile.semantic_query_expansion


def test_build_job_profile_extracts_role_skill_capability_and_strength():
    profile = build_job_profile(
        "We are looking for someone who mainly works on the backend of web applications and has experience building services that connect multiple systems. Familiarity with modern deployment environments would be helpful.",
        ontology=None,
        min_experience_years=4,
    )

    assert "backend web application developer" in profile.roles
    assert "integration/service engineer" in profile.roles

    strengths = {signal.name: signal.strength for signal in profile.skill_signals}
    assert strengths.get("backend") in {"must have", "main focus", "unknown"}

    capabilities = {signal.name: signal.strength for signal in profile.capability_signals}
    assert "system integration" in capabilities
    assert capabilities["deployment environment understanding"] in {"familiarity", "unknown", "nice to have"}

    assert profile.metadata_filters["min_experience_years"] == 4.0
    assert "backend engineer" in profile.lexical_query
