from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.core.exceptions import ExternalDependencyError
from backend.repositories.hybrid_retriever import HybridRetriever


def test_hybrid_retriever_uses_vector_path_when_available(monkeypatch):
    retriever = HybridRetriever()
    vector_hits = [{"candidate_id": "cand-1", "score": 0.9, "category": "Data"}]

    monkeypatch.setattr(retriever.retrieval_service, "search_candidates", lambda **_: vector_hits)

    hits = retriever.search_candidates(
        job_description="Need a data engineer with Python and SQL.",
        top_k=5,
        category="Data",
    )

    assert hits == vector_hits


def test_hybrid_retriever_falls_back_to_mongo_when_vector_fails(monkeypatch):
    retriever = HybridRetriever()
    fallback_hits = [{"candidate_id": "cand-2", "score": 0.4, "category": "Data"}]

    def _raise_external_dependency(**_):
        raise ExternalDependencyError("vector unavailable")

    monkeypatch.setattr(retriever.retrieval_service, "search_candidates", _raise_external_dependency)
    monkeypatch.setattr(retriever, "_search_mongo_fallback", lambda **_: fallback_hits)

    hits = retriever.search_candidates(
        job_description="Need a data engineer with Python and SQL.",
        top_k=5,
        category="Data",
    )

    assert hits == fallback_hits


def test_hybrid_retriever_raises_when_both_paths_fail(monkeypatch):
    retriever = HybridRetriever()

    def _raise_external_dependency(**_):
        raise ExternalDependencyError("vector unavailable")

    def _raise_fallback_failure(**_):
        raise ExternalDependencyError("fallback unavailable")

    monkeypatch.setattr(retriever.retrieval_service, "search_candidates", _raise_external_dependency)
    monkeypatch.setattr(retriever, "_search_mongo_fallback", _raise_fallback_failure)

    with pytest.raises(ExternalDependencyError):
        retriever.search_candidates(
            job_description="Need a data engineer with Python and SQL.",
            top_k=5,
            category="Data",
        )

