from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.core.exceptions import ExternalDependencyError
from backend.services.job_profile_extractor import JobProfile
from backend.repositories.hybrid_retriever import HybridRetriever


def _job_profile() -> JobProfile:
    return JobProfile(
        required_skills=["python", "sql"],
        expanded_skills=["python", "sql", "airflow"],
        required_experience_years=5.0,
        preferred_seniority="senior",
        query_text_for_embedding="data engineer python sql airflow senior",
    )


def test_hybrid_retriever_uses_fusion_when_vector_available(monkeypatch):
    retriever = HybridRetriever()
    job_profile = _job_profile()
    vector_hits = [
        {
            "candidate_id": "cand-1",
            "score": 0.9,
            "category": "Data",
            "experience_years": 6.0,
            "seniority_level": "senior",
        }
    ]
    keyword_hits = [
        {
            "candidate_id": "cand-1",
            "score": 0.7,
            "keyword_score": 0.8,
            "metadata_score": 0.9,
            "fusion_score": 0.75,
            "category": "Data",
            "experience_years": 6.0,
            "seniority_level": "senior",
        }
    ]

    monkeypatch.setattr(retriever, "_search_keyword_candidates", lambda **_: keyword_hits)
    monkeypatch.setattr(retriever.retrieval_service, "search_candidates", lambda **_: vector_hits)

    hits = retriever.search_candidates(
        job_description="Need a data engineer with Python and SQL.",
        job_profile=job_profile,
        top_k=5,
        category="Data",
        min_experience_years=5.0,
    )

    assert len(hits) == 1
    assert hits[0]["candidate_id"] == "cand-1"
    assert hits[0]["fusion_score"] > 0.0
    assert hits[0]["vector_score"] > 0.0
    assert hits[0]["keyword_score"] > 0.0


def test_hybrid_retriever_falls_back_to_keyword_when_vector_fails(monkeypatch):
    retriever = HybridRetriever()
    job_profile = _job_profile()
    keyword_hits = [{"candidate_id": "cand-2", "score": 0.4, "fusion_score": 0.4, "keyword_score": 0.6, "vector_score": 0.0}]

    def _raise_external_dependency(**_):
        raise ExternalDependencyError("vector unavailable")

    monkeypatch.setattr(retriever.retrieval_service, "search_candidates", _raise_external_dependency)
    monkeypatch.setattr(retriever, "_search_keyword_candidates", lambda **_: keyword_hits)

    hits = retriever.search_candidates(
        job_description="Need a data engineer with Python and SQL.",
        job_profile=job_profile,
        top_k=5,
        category="Data",
        min_experience_years=5.0,
    )

    assert hits == keyword_hits


def test_hybrid_retriever_raises_when_vector_and_keyword_both_fail(monkeypatch):
    retriever = HybridRetriever()
    job_profile = _job_profile()

    def _raise_external_dependency(**_):
        raise ExternalDependencyError("vector unavailable")

    def _raise_keyword_failure(**_):
        raise ExternalDependencyError("keyword unavailable")

    monkeypatch.setattr(retriever.retrieval_service, "search_candidates", _raise_external_dependency)
    monkeypatch.setattr(retriever, "_search_keyword_candidates", _raise_keyword_failure)

    with pytest.raises(ExternalDependencyError):
        retriever.search_candidates(
            job_description="Need a data engineer with Python and SQL.",
            job_profile=job_profile,
            top_k=5,
            category="Data",
            min_experience_years=5.0,
        )
