from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.core.settings import settings
from backend.services.cross_encoder_rerank_service import CrossEncoderRerankService
from backend.services.matching_service import MatchingService


def test_resolve_retrieval_top_n_when_rerank_enabled(monkeypatch):
    service = MatchingService()
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "rerank_top_n", 50)
    assert service._resolve_retrieval_top_n(10) == 50
    assert service._resolve_retrieval_top_n(80) == 80


def test_shortlist_without_rerank_uses_first_top_k(monkeypatch):
    service = MatchingService()
    monkeypatch.setattr(settings, "rerank_enabled", False)
    enriched_hits = [
        ({"candidate_id": "a", "fusion_score": 0.9}, {"parsed": {}}),
        ({"candidate_id": "b", "fusion_score": 0.8}, {"parsed": {}}),
        ({"candidate_id": "c", "fusion_score": 0.7}, {"parsed": {}}),
    ]
    out = service._shortlist_candidates(job_description="jd", enriched_hits=enriched_hits, top_k=2)
    assert len(out) == 2
    assert out[0][0]["candidate_id"] == "a"
    assert out[1][0]["candidate_id"] == "b"


def test_cross_encoder_rerank_reorders_by_relevance(monkeypatch):
    service = CrossEncoderRerankService()
    enriched_hits = [
        (
            {"candidate_id": "a", "fusion_score": 0.8, "score": 0.8, "category": "it", "experience_years": 5, "seniority_level": "mid"},
            {"parsed": {"summary": "python backend", "normalized_skills": ["python", "api"]}},
        ),
        (
            {"candidate_id": "b", "fusion_score": 0.7, "score": 0.7, "category": "it", "experience_years": 6, "seniority_level": "senior"},
            {"parsed": {"summary": "distributed systems", "normalized_skills": ["go", "kubernetes"]}},
        ),
    ]

    monkeypatch.setattr(
        service,
        "_score_candidates",
        lambda **_: [{"candidate_id": "a", "relevance": 0.2}, {"candidate_id": "b", "relevance": 0.95}],
    )
    out = service.rerank(job_description="backend microservices kubernetes", enriched_hits=enriched_hits, top_k=2)
    assert len(out) == 2
    assert out[0][0]["candidate_id"] == "b"
    assert out[0][0]["rerank_score"] == 0.95


def test_embedding_rerank_reorders_by_similarity(monkeypatch):
    service = CrossEncoderRerankService()
    enriched_hits = [
        (
            {"candidate_id": "a", "fusion_score": 0.8, "score": 0.8, "category": "it", "experience_years": 5, "seniority_level": "mid"},
            {"parsed": {"summary": "python backend", "normalized_skills": ["python", "api"]}},
        ),
        (
            {"candidate_id": "b", "fusion_score": 0.7, "score": 0.7, "category": "it", "experience_years": 6, "seniority_level": "senior"},
            {"parsed": {"summary": "distributed systems", "normalized_skills": ["go", "kubernetes"]}},
        ),
    ]

    class _EmbRow:
        def __init__(self, embedding):
            self.embedding = embedding

    class _EmbResp:
        def __init__(self, rows):
            self.data = rows

    class _EmbApi:
        @staticmethod
        def create(**kwargs):
            # input shape: [query, cand-a, cand-b]
            # query is more similar to cand-b than cand-a
            return _EmbResp(
                [
                    _EmbRow([1.0, 0.0]),   # query
                    _EmbRow([0.1, 0.99]),  # cand-a
                    _EmbRow([0.95, 0.05]), # cand-b
                ]
            )

    class _Client:
        embeddings = _EmbApi()

    monkeypatch.setattr(settings, "rerank_mode", "embedding")
    monkeypatch.setattr(settings, "rerank_embedding_model", "text-embedding-3-small")
    monkeypatch.setattr("backend.services.cross_encoder_rerank_service.get_openai_client", lambda: _Client())

    out = service.rerank(job_description="backend microservices kubernetes", enriched_hits=enriched_hits, top_k=2)
    assert len(out) == 2
    assert out[0][0]["candidate_id"] == "b"
    assert out[0][0]["rerank_score"] > out[1][0]["rerank_score"]
