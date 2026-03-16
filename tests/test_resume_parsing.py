from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backend.services.resume_parsing import parse_resume_text


def test_extract_experience_with_fullwidth_dash_range() -> None:
    text = (
        "Experience HR Representative , 11/2008 － 02/2016 Company Name － City , State "
        "Managed onboarding and employee relations."
    )
    parsed = parse_resume_text(text, parser_mode="rule")
    assert parsed.experience
    assert parsed.experience[0].start_date == "11/2008"
    assert parsed.experience[0].end_date == "02/2016"


def test_extract_experience_from_single_date_format() -> None:
    text = (
        "Summary Strong profile. Experience 01/2017 VR Designer Company Name － City , State "
        "Built immersive workflows. 01/2016 Game Tester Company Name － City , State "
        "Education and Training 2014 Fine Art and Game Design."
    )
    parsed = parse_resume_text(text, parser_mode="rule")
    assert parsed.experience
    assert any(item.start_date == "01/2017" for item in parsed.experience)


def test_extract_education_from_institution_pattern() -> None:
    text = (
        "Education and Training Colorado State University － City , State "
        "Mountain States Employers Council. Skills HRIS, recruiting."
    )
    parsed = parse_resume_text(text, parser_mode="rule")
    assert parsed.education
    assert any((item.institution or "").lower().find("university") >= 0 for item in parsed.education)


def test_extract_skills_from_highlights_heading() -> None:
    text = (
        "Professional Summary Delivery-focused engineer. "
        "Highlights Python, SQL, ETL, data modeling, stakeholder communication."
    )
    parsed = parse_resume_text(text, parser_mode="rule")
    lowered = {skill.lower() for skill in parsed.skills}
    assert {"python", "sql"} & lowered
