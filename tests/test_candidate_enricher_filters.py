from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services import candidate_enricher


def _candidate_doc(location: str, degree: str, category: str = "INFORMATION-TECHNOLOGY") -> dict:
    return {
        "candidate_id": "cand-1",
        "category": category,
        "metadata": {"location": location},
        "parsed": {
            "summary": "Built software systems in production.",
            "normalized_skills": ["python", "sql", "distributed systems"],
            "education": [{"degree": degree, "institution": "X"}],
            "experience_items": [{"location": location}],
        },
    }


def test_enrich_hits_applies_region_education_industry_filters(monkeypatch):
    hits = [{"candidate_id": "cand-1", "experience_years": 6.0}]
    docs = {"cand-1": _candidate_doc(location="Austin, United States", degree="Master of Science")}

    monkeypatch.setattr(candidate_enricher, "get_candidates_by_ids", lambda _: docs)

    enriched = candidate_enricher.enrich_hits(
        hits,
        min_experience_years=5.0,
        education="Master",
        region="United States",
        industry="Technology",
    )

    assert len(enriched) == 1
    assert enriched[0][0]["candidate_id"] == "cand-1"


def test_enrich_hits_drops_candidates_when_extended_filters_do_not_match(monkeypatch):
    hits = [{"candidate_id": "cand-1", "experience_years": 6.0}]
    docs = {"cand-1": _candidate_doc(location="Berlin, Germany", degree="Bachelor of Arts", category="HR")}

    monkeypatch.setattr(candidate_enricher, "get_candidates_by_ids", lambda _: docs)

    enriched = candidate_enricher.enrich_hits(
        hits,
        min_experience_years=5.0,
        education="Master",
        region="United States",
        industry="Technology",
    )

    assert enriched == []


def test_enrich_hits_industry_uses_taxonomy_tags_not_summary_keywords(monkeypatch):
    hits = [{"candidate_id": "cand-1", "experience_years": 6.0}]
    docs = {
        "cand-1": {
            "candidate_id": "cand-1",
            "category": "HR",
            "metadata": {"location": "Austin, United States"},
            "parsed": {
                "summary": "Worked on marketplace growth initiatives.",
                "normalized_skills": ["people operations", "hiring"],
                "core_skills": ["human resources"],
                "expanded_skills": ["human resources", "people"],
                "education": [{"degree": "Master of Science", "institution": "X"}],
                "experience_items": [{"location": "Austin, United States"}],
            },
        }
    }

    monkeypatch.setattr(candidate_enricher, "get_candidates_by_ids", lambda _: docs)

    enriched = candidate_enricher.enrich_hits(
        hits,
        min_experience_years=5.0,
        education="Master",
        region="United States",
        industry="E-commerce",
    )

    assert enriched == []


def test_enrich_hits_region_alias_normalization(monkeypatch):
    hits = [{"candidate_id": "cand-1", "experience_years": 6.0}]
    docs = {"cand-1": _candidate_doc(location="Austin, USA", degree="Master of Science")}

    monkeypatch.setattr(candidate_enricher, "get_candidates_by_ids", lambda _: docs)

    enriched = candidate_enricher.enrich_hits(
        hits,
        min_experience_years=5.0,
        education="Master",
        region="United States",
        industry="Technology",
    )

    assert len(enriched) == 1
    assert enriched[0][0]["candidate_id"] == "cand-1"


def test_enrich_hits_industry_alias_normalization(monkeypatch):
    hits = [{"candidate_id": "cand-1", "experience_years": 6.0}]
    docs = {"cand-1": _candidate_doc(location="Austin, United States", degree="Master of Science", category="Information Technology")}

    monkeypatch.setattr(candidate_enricher, "get_candidates_by_ids", lambda _: docs)

    enriched = candidate_enricher.enrich_hits(
        hits,
        min_experience_years=5.0,
        education="Master",
        region="US",
        industry="IT",
    )

    assert len(enriched) == 1
    assert enriched[0][0]["candidate_id"] == "cand-1"
