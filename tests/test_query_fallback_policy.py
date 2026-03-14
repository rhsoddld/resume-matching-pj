from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.core.settings import settings
from backend.services.job_profile_extractor import JobProfile, QuerySignal
from backend.services.matching_service import MatchingService
from backend.services.query_fallback_service import QueryFallbackDraft, QueryFallbackService


def test_fallback_gate_triggers_on_low_confidence(monkeypatch):
    monkeypatch.setattr(settings, "query_fallback_enabled", True)
    monkeypatch.setattr(settings, "query_fallback_confidence_threshold", 0.7)
    monkeypatch.setattr(settings, "query_fallback_unknown_ratio_threshold", 0.5)

    profile = JobProfile(
        required_skills=["python"],
        expanded_skills=["python"],
        required_experience_years=None,
        preferred_seniority=None,
        confidence=0.55,
        signal_quality={"unknown_ratio": 0.1},
    )

    enabled, reason, trigger = MatchingService._should_use_query_fallback(profile)
    assert enabled is True
    assert reason == "low_confidence"
    assert trigger["confidence"] == 0.55


def test_fallback_gate_triggers_on_high_unknown_ratio(monkeypatch):
    monkeypatch.setattr(settings, "query_fallback_enabled", True)
    monkeypatch.setattr(settings, "query_fallback_confidence_threshold", 0.4)
    monkeypatch.setattr(settings, "query_fallback_unknown_ratio_threshold", 0.45)

    profile = JobProfile(
        required_skills=["python"],
        expanded_skills=["python"],
        required_experience_years=None,
        preferred_seniority=None,
        confidence=0.8,
        signal_quality={"unknown_ratio": 0.8},
    )

    enabled, reason, trigger = MatchingService._should_use_query_fallback(profile)
    assert enabled is True
    assert reason == "high_unknown_ratio"
    assert trigger["unknown_ratio"] == 0.8


def test_merge_profiles_prefers_fallback_signals():
    service = MatchingService()
    primary = JobProfile(
        required_skills=["python", "sql"],
        expanded_skills=["python", "sql"],
        required_experience_years=4.0,
        preferred_seniority="mid",
        job_category="information technology",
        roles=["backend engineer"],
        skill_signals=[QuerySignal(name="python", strength="unknown", signal_type="skill")],
        capability_signals=[],
        lexical_query="backend engineer python",
        semantic_query_expansion=["backend engineer", "python"],
        query_text_for_embedding="backend engineer python",
        confidence=0.52,
        signal_quality={"unknown_ratio": 1.0},
    )
    fallback = JobProfile(
        required_skills=["python", "api", "microservices"],
        expanded_skills=["python", "api", "microservices", "docker"],
        required_experience_years=4.0,
        preferred_seniority="mid",
        job_category="backend engineer",
        roles=["backend engineer", "integration/service engineer"],
        skill_signals=[
            QuerySignal(name="python", strength="must have", signal_type="skill"),
            QuerySignal(name="api", strength="must have", signal_type="skill"),
        ],
        capability_signals=[QuerySignal(name="system integration", strength="main focus", signal_type="capability")],
        lexical_query="backend engineer python api microservices",
        semantic_query_expansion=["backend engineer", "api", "microservices"],
        query_text_for_embedding="backend engineer python api microservices",
        confidence=0.85,
        signal_quality={"unknown_ratio": 0.1},
    )

    merged = service._merge_profiles(primary=primary, fallback=fallback)
    assert merged.job_category == "backend engineer"
    assert "microservices" in merged.required_skills
    assert merged.confidence == 0.85
    python_signal = [s for s in merged.skill_signals if s.name == "python"][0]
    assert python_signal.strength == "must have"
    assert merged.signal_quality["unknown_ratio"] <= 0.5


def test_fallback_prompt_text_is_structured():
    draft = QueryFallbackDraft(
        job_category="backend engineer",
        roles=["backend engineer"],
        skill_signals=[
            {"name": "python", "strength": "must have"},
            {"name": "docker", "strength": "familiarity"},
        ],
        capability_signals=[{"name": "system integration", "strength": "main focus"}],
        related_skills=["kubernetes"],
        seniority_hint="mid",
    )
    text = QueryFallbackService.to_deterministic_text(draft)
    assert "must have: python" in text
    assert "capabilities:" in text
    assert "related skills:" in text
