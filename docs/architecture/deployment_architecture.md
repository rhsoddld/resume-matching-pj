# Deployment Architecture

![Architecture](../assets/Architecture.png)

이 문서는 **런타임 토폴로지**, **MVP vs Production 범위**, **운영 규모(API Gateway, Load Balancer, K8s) 고려**를 정의합니다.  
소프트웨어 컴포넌트 구조는 [system_architecture.md](system_architecture.md), 논리적 데이터 이동은 [../data-flow/](../data-flow/)를 참고하세요.

---

## MVP vs Production 범위

| 구분 | 현재 범위 (MVP / Capstone) | Production 확장 시 적용 범위 |
|------|----------------------------|------------------------------|
| **배포 단위** | 단일 호스트 `docker-compose` (frontend, backend, mongodb, milvus) | Kubernetes(K8s) 네이티브 배포, 다중 replica |
| **트래픽 제어** | Backend 단일 인스턴스, 선택적 ingestion rate limit | API Gateway(인증/라우팅/rate limit), Load Balancer로 다중 backend 분산 |
| **가용성** | 단일 AZ, 수동 복구 | 다중 AZ, 자동 복구, 헬스체크 기반 재시작 |
| **관측성** | 구조화 로그, 헬스 엔드포인트, 평가 아카이브, LangSmith(SaaS) 트레이싱(설정 기반); 로그는 MongoDB에 일시 저장(MVP) | 중앙 로그/메트릭, 대시보드, 알림 정책 + 트레이싱 통합 (Grafana/Prometheus/Datadog 등은 재검토; docs/observability 참고) |
| **ML 파이프라인** | 평가 스크립트·golden set 기반 품질 검증 | MLOps: 모델 버전, A/B, 재학습 트리거 (후속 고도화) |

MVP와 Production의 차이는 [problem_definition.md](../../requirements/problem_definition.md) Non-Goals(ingestion LLM 기본 경로 미사용, fine-tuned embedding 후속, full ATS 미포함)와 정합됩니다.

---

## Runtime Topology (현재 구현)

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

1. Backend는 기본적으로 stateless이며, 영속 데이터는 MongoDB/Milvus에 저장한다. 단, token cache는 프로세스 로컬 인메모리(ephemeral)로 동작한다.
2. Ingestion and matching APIs share the same backend service with config-based guards.
3. Retrieval can degrade gracefully to Mongo lexical fallback if vector retrieval fails.
4. Observability is centralized through structured logs and request-id propagation.

### Logs (MVP)

현재 MVP 구현에서는 운영 편의상 **구조화 로그를 MongoDB에 일시 저장**하는 경로를 사용합니다. Production 환경에서는 로그/메트릭 파이프라인을 **Grafana/Prometheus/Datadog 등으로 재검토**하여 중앙 수집·보관 정책에 맞게 교체하는 것을 전제로 합니다.

### LLM / Agent Tracing (LangSmith SaaS)

현재 구현은 **LangSmith(SaaS)** 를 이용해 LLM 호출·에이전트 실행 흐름을 트레이싱할 수 있도록 구성되어 있습니다(환경변수/설정으로 on/off 가능).  
관련 설정은 `src/backend/core/settings.py`의 `langsmith_*` 항목과 `.env.example`의 `LANGSMITH_*` 값을 참고하세요.

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

## Production-Scale 고려 (API Gateway, Load Balancer, K8s)

현재 코드는 단일 백엔드·docker-compose로 동작하도록 구현되어 있으며, **운영 규모 배포**로 확장할 때 아래와 같이 매핑됩니다.

| 요소 | 역할 | 현재 구현 | Production 확장 시 |
|------|------|-----------|---------------------|
| **API Gateway** | 인증, 라우팅, rate limit, API 버전 | Ingestion: `X-API-Key`, `ingestion_rate_limit_per_minute` (in-memory) | Kong / AWS API Gateway / Azure APIM 등으로 통합 인증·전역 rate limit 이전 |
| **Load Balancer** | 트래픽 분산, 헬스 기반 라우팅 | 단일 backend; `GET /api/health`, `GET /api/ready` 제공 | LB가 여러 backend replica에 분산; readiness 실패 시 트래픽 제외 |
| **Kubernetes (K8s)** | 오케스트레이션, replica, 자동 복구 | 미사용 (docker-compose) | Backend/Frontend를 Deployment로 배포, Mongo/Milvus는 StatefulSet 또는 관리형 서비스; HPA로 replica 수 조절 |

**아키텍처 상의 고려 사항:**

- Backend는 **stateless**이므로 replica 수평 확장 시 세션 고정 불필요.
- 영속 상태는 MongoDB·Milvus에만 두어, 백엔드 교체·재시작이 데이터와 무관하게 동작.
- 커넥션 풀링(Motor, Milvus client)으로 replica 증가 시에도 DB 연결 수를 설정으로 제어 가능.
- 관측성(구조화 로그, request-id, 헬스)은 [docs/observability/monitoring.md](../observability/monitoring.md)에 정의되어 있어, K8s 프로브 및 로그 수집기에 연동 가능.

---

## 디자인 결정 (ADR) 및 결합도 분리

- **ADR (Architecture Decision Records):** 주요 기술 선택의 장단점·근거(왜)는 [../adr/](../adr/)에 정리되어 있습니다.  
  예: [ADR-001 Vector DB](../adr/ADR-001-vector-db.md), [ADR-002 Embedding Model](../adr/ADR-002-embedding-model.md), [ADR-003 Hybrid Retrieval](../adr/ADR-003-hybrid-retrieval.md), [ADR-004 Agent Orchestration](../adr/ADR-004-agent-orchestration.md), [ADR-005 Deterministic Query Understanding](../adr/ADR-005-deterministic-query-understanding.md), [ADR-006 Rerank Policy](../adr/ADR-006-rerank-policy.md), [ADR-007 Ingestion Parsing (Rule-based)](../adr/ADR-007-ingestion-parsing-rule-based.md), [ADR-008 Bias & Fairness Guardrails](../adr/ADR-008-bias-fairness-guardrails.md), [ADR-009 Observability Strategy](../adr/ADR-009-observability-strategy.md).  
  상위 수준 tradeoff는 [../tradeoffs/design_tradeoffs.md](../tradeoffs/design_tradeoffs.md), [key-design-decisions.md](../design/key-design-decisions.md)를 참고하세요.
- **결합도 분리 (Decoupling):** 벡터 저장소는 repository 추상화 뒤에 두어, 코어 API 수정 없이 Vector DB를 교체할 수 있는 구조입니다.  
  자세한 결정 이유는 [ADR-001 Vector DB](../adr/ADR-001-vector-db.md)를 참고하세요.
