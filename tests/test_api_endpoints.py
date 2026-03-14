from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import backend.api.jobs as jobs_api
import backend.api.ingestion as ingestion_api
import backend.main as main_module
from backend.core.exceptions import ExternalDependencyError


def _build_match_response() -> dict:
    return {
        "query_profile": {
            "job_category": "HR",
            "roles": ["hr manager"],
            "required_skills": ["recruiting", "people operations"],
            "related_skills": ["communication", "onboarding"],
            "skill_signals": [
                {"name": "recruiting", "strength": "must have", "signal_type": "skill"},
                {"name": "people operations", "strength": "main focus", "signal_type": "skill"},
            ],
            "capability_signals": [
                {"name": "web application development", "strength": "nice to have", "signal_type": "capability"}
            ],
            "seniority_hint": "senior",
            "filters": {"category": "HR", "min_experience_years": 5.0},
            "metadata_filters": {"category": "HR", "min_experience_years": 5.0},
            "lexical_query": "hr manager recruiting people operations",
            "semantic_query_expansion": ["hr manager", "recruiting", "people operations"],
            "query_text_for_embedding": "HR recruiting people operations communication onboarding senior",
            "confidence": 0.88,
        },
        "matches": [
            {
                "candidate_id": "cand-001",
                "category": "HR",
                "summary": "Experienced HR manager.",
                "skills": ["recruiting", "communication"],
                "normalized_skills": ["recruiting", "communication"],
                "core_skills": ["recruiting"],
                "expanded_skills": ["recruiting", "hr", "communication"],
                "experience_years": 7.0,
                "seniority_level": "senior",
                "score": 0.91,
                "vector_score": 0.82,
                "skill_overlap": 0.95,
                "score_detail": {
                    "semantic_similarity": 0.9,
                    "experience_fit": 1.0,
                    "seniority_fit": 1.0,
                    "category_fit": 0.03,
                },
                "skill_overlap_detail": {
                    "core_overlap": 1.0,
                    "expanded_overlap": 1.0,
                    "normalized_overlap": 1.0,
                },
            }
        ],
    }


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main_module, "warmup_infrastructure", lambda: None)
    return TestClient(main_module.app)


def test_health_returns_liveness_status(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ready_when_dependencies_are_available(monkeypatch):
    monkeypatch.setattr(main_module, "_check_mongo_ready", lambda: (True, None))
    monkeypatch.setattr(main_module, "_check_milvus_ready", lambda: (True, None))

    with _client(monkeypatch) as client:
        response = client.get("/api/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["mongo"]["ok"] is True
    assert payload["checks"]["milvus"]["ok"] is True


def test_ready_returns_degraded_when_dependency_is_unavailable(monkeypatch):
    monkeypatch.setattr(main_module, "_check_mongo_ready", lambda: (False, "mongo unavailable"))
    monkeypatch.setattr(main_module, "_check_milvus_ready", lambda: (True, None))

    with _client(monkeypatch) as client:
        response = client.get("/api/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["mongo"]["ok"] is False
    assert payload["checks"]["mongo"]["error"] == "mongo unavailable"
    assert payload["checks"]["milvus"]["ok"] is True


def test_jobs_match_returns_response_payload(monkeypatch):
    monkeypatch.setattr(jobs_api.matching_service, "match_jobs", lambda **_: _build_match_response())

    request_payload = {
        "job_description": "Looking for a senior HR manager with recruiting and people operations experience.",
        "top_k": 3,
        "category": "HR",
        "min_experience_years": 5,
    }

    with _client(monkeypatch) as client:
        response = client.post("/api/jobs/match", json=request_payload)

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_profile"]["job_category"] == "HR"
    assert payload["query_profile"]["roles"] == ["hr manager"]
    assert payload["query_profile"]["confidence"] == 0.88
    assert len(payload["matches"]) == 1
    assert payload["matches"][0]["candidate_id"] == "cand-001"
    assert "agent_scores" in payload["matches"][0]
    assert "agent_explanation" in payload["matches"][0]


def test_jobs_match_returns_validation_error_for_short_description(monkeypatch):
    request_payload = {"job_description": "too short", "top_k": 3}

    with _client(monkeypatch) as client:
        response = client.post("/api/jobs/match", json=request_payload)

    assert response.status_code == 422


def test_jobs_match_forwards_extended_filters(monkeypatch):
    captured: dict = {}

    def _stub_match_jobs(**kwargs):
        captured.update(kwargs)
        return _build_match_response()

    monkeypatch.setattr(jobs_api.matching_service, "match_jobs", _stub_match_jobs)

    request_payload = {
        "job_description": "Hiring a backend engineer with distributed systems experience and production ownership.",
        "top_k": 5,
        "category": "Python Developer",
        "min_experience_years": 4,
        "education": "Master",
        "region": "United States",
        "industry": "Technology",
    }

    with _client(monkeypatch) as client:
        response = client.post("/api/jobs/match", json=request_payload)

    assert response.status_code == 200
    assert captured["education"] == "Master"
    assert captured["region"] == "United States"
    assert captured["industry"] == "Technology"


def test_jobs_match_maps_external_dependency_error(monkeypatch):
    def _raise_error(**_):
        raise ExternalDependencyError("retrieval service unavailable")

    monkeypatch.setattr(jobs_api.matching_service, "match_jobs", _raise_error)

    request_payload = {
        "job_description": "Hiring a data engineer who can build robust ETL pipelines and optimize SQL workloads.",
        "top_k": 3,
    }

    with _client(monkeypatch) as client:
        response = client.post("/api/jobs/match", json=request_payload)

    assert response.status_code == 503
    payload = response.json()
    assert payload["error_code"] == "external_dependency_error"
    assert "retrieval service unavailable" in payload["detail"]


def test_ingestion_endpoint_runs_sync_job(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(ingestion_api.settings, "ingestion_api_key", None)
    monkeypatch.setattr(ingestion_api.settings, "ingestion_rate_limit_per_minute", 1000)

    def _iter_candidates(*args, **kwargs):
        captured["iter_args"] = args
        captured["iter_kwargs"] = kwargs
        return iter([])

    def _run_ingestion(candidates, **kwargs):
        captured["run_kwargs"] = kwargs
        captured["materialized"] = list(candidates)

    monkeypatch.setattr(ingestion_api, "iter_candidates", _iter_candidates)
    monkeypatch.setattr(ingestion_api, "run_ingestion", _run_ingestion)

    request_payload = {
        "source": "all",
        "target": "mongo",
        "dry_run": True,
        "batch_size": 16,
        "csv_chunk_size": 100,
        "parser_mode": "hybrid",
        "async_mode": False,
    }

    with _client(monkeypatch) as client:
        response = client.post("/api/ingestion/resumes", json=request_payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert captured["iter_kwargs"]["csv_chunk_size"] == 100
    assert captured["run_kwargs"]["write_mongo"] is True
    assert captured["run_kwargs"]["write_milvus"] is False
    assert captured["run_kwargs"]["dry_run"] is True
    assert captured["run_kwargs"]["batch_size"] == 16


def test_ingestion_endpoint_enforces_api_key(monkeypatch):
    monkeypatch.setattr(ingestion_api.settings, "ingestion_api_key", "secret-key")
    monkeypatch.setattr(ingestion_api.settings, "ingestion_rate_limit_per_minute", 1000)

    request_payload = {"source": "all", "target": "mongo", "dry_run": True}

    with _client(monkeypatch) as client:
        response = client.post("/api/ingestion/resumes", json=request_payload)

    assert response.status_code == 401
    payload = response.json()
    assert payload["error_code"] == "ingestion_unauthorized"


def test_ingestion_endpoint_accepts_async_job(monkeypatch):
    called = {"run": 0}

    monkeypatch.setattr(ingestion_api.settings, "ingestion_api_key", None)
    monkeypatch.setattr(ingestion_api.settings, "ingestion_rate_limit_per_minute", 1000)
    monkeypatch.setattr(ingestion_api.settings, "ingestion_allow_async", True)
    monkeypatch.setattr(ingestion_api, "iter_candidates", lambda *_, **__: iter([]))

    def _run_ingestion(candidates, **kwargs):
        called["run"] += 1
        list(candidates)

    monkeypatch.setattr(ingestion_api, "run_ingestion", _run_ingestion)

    request_payload = {"source": "all", "target": "mongo", "dry_run": True, "async_mode": True}

    with _client(monkeypatch) as client:
        response = client.post("/api/ingestion/resumes", json=request_payload)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert called["run"] == 1
