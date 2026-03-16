from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backend.schemas.candidate import ParsedExperienceItem
from backend.services.ingestion.preprocessing import extract_sneha_abilities, sanitize_skill_tokens


def test_extract_sneha_abilities_from_summary_and_experience() -> None:
    summary = (
        "Experienced manager with strong stakeholder communication and cross-functional collaboration skills."
    )
    experience_items = [
        ParsedExperienceItem(
            title="HR Representative",
            description="Managed team onboarding, improved workflow efficiency, and trained new hires.",
        )
    ]
    abilities = extract_sneha_abilities(
        resume_text="",
        summary=summary,
        experience_items=experience_items,
    )
    assert "stakeholder communication" in abilities
    assert "cross-functional collaboration" in abilities
    assert "training and mentoring" in abilities


def test_extract_sneha_abilities_fallback_phrase() -> None:
    abilities = extract_sneha_abilities(
        resume_text="Ability to coordinate interviews and scheduling across departments.",
        summary=None,
        experience_items=[],
    )
    assert abilities


def test_sanitize_skill_tokens_drops_resume_noise() -> None:
    tokens = [
        "Python",
        "Machine Learning",
        "Company Name - City, State",
        "Professional Experience",
        "11/2008 - 02/2016",
        "Managed onboarding and employee relations for hiring pipelines",
    ]
    sanitized = sanitize_skill_tokens(tokens)
    assert "python" in sanitized
    assert "machine learning" in sanitized
    assert "company name - city state" not in sanitized
    assert "professional experience" not in sanitized
    assert not any("11/2008" in token for token in sanitized)
