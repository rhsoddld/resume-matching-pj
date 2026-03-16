# Deployment Architecture

## Runtime Topology

- `frontend` (Vite build + nginx)
- `backend` (FastAPI + Uvicorn)
- `mongodb` (candidate/job/session documents)
- `milvus` (vector retrieval)

## Network and Ports

- Frontend: `http://localhost`
- Backend API: `http://localhost:8000`
- MongoDB: internal docker network
- Milvus: internal docker network

### Health / Readiness Endpoints

- `GET /api/health`: liveness (`{"status":"ok"}`)
- `GET /api/ready`: Mongo/Milvus readiness probe (`ready | degraded`)

## Deployment Principles

1. Backend is stateless; persistence is delegated to MongoDB and Milvus.
2. Ingestion and matching APIs share the same backend service with config-based guards.
3. Retrieval can degrade gracefully to Mongo lexical fallback if vector retrieval fails.
4. Observability is centralized through structured logs and request-id propagation.

### Ingestion Security and Traffic Controls

- Ingestion API key guard: `X-API-Key` (when `ingestion_api_key` is configured)
- In-memory sliding window rate limit: `ingestion_rate_limit_per_minute`
- Async ingestion policy toggle: `ingestion_allow_async`

## Environment Controls

- Model and rerank route: `src/backend/core/settings.py`
- Guardrails and fairness toggles: `src/backend/core/settings.py`
- Token budget/cache controls: `src/backend/core/settings.py`
- Ingestion auth/rate-limit controls: `src/backend/core/settings.py`
