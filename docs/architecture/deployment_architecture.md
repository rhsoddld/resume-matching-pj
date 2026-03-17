# Deployment Architecture

![Architecture](../assets/Architecture.png)

This document defines **runtime topology**, **MVP vs production scope**, and **production-scale considerations** (API Gateway, Load Balancer, K8s).  
For software components/layers, see [system_architecture.md](system_architecture.md). For logical data movement, see [../data-flow/](../data-flow/).

---

## MVP vs production scope

| Category | Current scope (MVP / capstone) | Production expansion scope |
|------|----------------------------|------------------------------|
| **Deployment unit** | Single-host `docker-compose` (frontend, backend, mongodb, milvus) | Kubernetes (K8s) native deployment, multiple replicas |
| **Traffic control** | Single backend instance, optional ingestion rate limit | API Gateway (auth/routing/rate limit), Load Balancer distributes across replicas |
| **Availability** | Single AZ, manual recovery | Multi-AZ, auto recovery, health-check based restarts |
| **Observability** | Structured logs, health endpoints, eval archives, LangSmith (SaaS) tracing (config on/off); logs temporarily stored in MongoDB (MVP) | Central logs/metrics, dashboards, alerting + tracing integration (re-evaluate Grafana/Prometheus/Datadog; see `docs/observability`) |
| **ML pipeline** | Quality validation via eval scripts + golden set | MLOps: model versioning, A/B, retraining triggers (future work) |

The MVP vs production split aligns with Non-Goals in [problem_definition.md](../../requirements/problem_definition.md) (no default ingestion LLM parsing, fine-tuned embeddings deferred, full ATS out of scope).

---

## Runtime topology (current implementation)

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

1. The backend is stateless by default; persistent data lives in MongoDB/Milvus. The token cache is process-local in-memory (ephemeral).
2. Ingestion and matching APIs share the same backend service with config-based guards.
3. Retrieval can degrade gracefully to Mongo lexical fallback if vector retrieval fails.
4. Observability is centralized through structured logs and request-id propagation.

### Logs (MVP)

In the MVP, **structured logs are temporarily stored in MongoDB** for operational convenience. In production, re-evaluate the logs/metrics pipeline (Grafana/Prometheus/Datadog, etc.) and adopt a centralized collection/retention policy.

### LLM / Agent Tracing (LangSmith SaaS)

The system supports tracing LLM calls and agent execution flows via **LangSmith (SaaS)** (toggleable via env/settings).  
See `langsmith_*` in `src/backend/core/settings.py` and `LANGSMITH_*` in `.env.example`.

### Ingestion Security and Traffic Controls

- Ingestion API key guard: `X-API-Key` (when `ingestion_api_key` is configured)
- In-memory sliding window rate limit: `ingestion_rate_limit_per_minute`
- Async ingestion policy toggle: `ingestion_allow_async`

## Environment Controls

- Model and rerank route: `src/backend/core/settings.py`
- Guardrails and fairness toggles: `src/backend/core/settings.py`
- Token budget/cache controls: `src/backend/core/settings.py`
- Ingestion auth/rate-limit controls: `src/backend/core/settings.py`

---

## Production-scale considerations (API Gateway, Load Balancer, K8s)

The codebase currently runs as a single-backend docker-compose setup. When expanding to **production-scale deployment**, map components as follows.

| Component | Role | Current implementation | Production expansion |
|------|------|-----------|---------------------|
| **API Gateway** | auth, routing, rate limits, API versioning | Ingestion: `X-API-Key`, `ingestion_rate_limit_per_minute` (in-memory) | Move to centralized auth + global rate limits via Kong / AWS API Gateway / Azure APIM, etc. |
| **Load Balancer** | traffic distribution, health-based routing | single backend; provides `GET /api/health`, `GET /api/ready` | distribute across multiple backend replicas; remove traffic on readiness failures |
| **Kubernetes (K8s)** | orchestration, replicas, auto recovery | not used (docker-compose) | deploy backend/frontend as Deployments; Mongo/Milvus as StatefulSets or managed services; use HPA for autoscaling |

**Architecture considerations:**

- The backend is **stateless**, so session affinity is not required for horizontal scaling.
- Keep persistent state only in MongoDB/Milvus so backend restarts/replacements are data-independent.
- Connection pooling (Motor, Milvus client) allows controlling DB connection counts as replicas scale.
- Observability (structured logs, request-id, health) is defined in [docs/observability/monitoring.md](../observability/monitoring.md) and can be wired into K8s probes and log collectors.

---

## Design decisions (ADRs) and decoupling

- **ADRs (Architecture Decision Records):** key technology choices, trade-offs, and rationale are captured in [../adr/](../adr/).  
  Examples: [ADR-001 Vector DB](../adr/ADR-001-vector-db.md), [ADR-002 Embedding Model](../adr/ADR-002-embedding-model.md), [ADR-003 Hybrid Retrieval](../adr/ADR-003-hybrid-retrieval.md), [ADR-004 Agent Orchestration](../adr/ADR-004-agent-orchestration.md), [ADR-005 Deterministic Query Understanding](../adr/ADR-005-deterministic-query-understanding.md), [ADR-006 Rerank Policy](../adr/ADR-006-rerank-policy.md), [ADR-007 Ingestion Parsing (Rule-based)](../adr/ADR-007-ingestion-parsing-rule-based.md), [ADR-008 Bias & Fairness Guardrails](../adr/ADR-008-bias-fairness-guardrails.md), [ADR-009 Observability Strategy](../adr/ADR-009-observability-strategy.md).  
  For higher-level trade-offs, see [../tradeoffs/design_tradeoffs.md](../tradeoffs/design_tradeoffs.md) and [key-design-decisions.md](../design/key-design-decisions.md).
- **Decoupling:** the vector store is behind repository abstractions so the Vector DB can be swapped without changing core API code.  
  For the rationale, see [ADR-001 Vector DB](../adr/ADR-001-vector-db.md).
