# TRACEABILITY MATRIX — AI Resume Matching System

> 이 문서는 **요구사항 ID ↔ 설계 결정 ↔ 구현 위치 ↔ 테스트/평가 증거**를 한눈에 파악할 수 있도록 테이블 형태로 정리한 Reviewer용 추적 매트릭스입니다.  
> 업데이트 기준: 각 Phase 완료 시점마다 `Status` 및 `Evidence` 컬럼을 수동 갱신.

---

## 1. 요구사항 ↔ 구현 매핑

| Req ID | 요구사항 요약 | Priority | 관련 컴포넌트 | 구현 위치 | Status |
|--------|-------------|----------|-------------|---------|--------|
| R1.1 | Resume 텍스트 임베딩 생성 및 Milvus 인덱싱 | Must | IngestionService, Milvus | `src/backend/services/ingest_resumes.py`, `src/backend/core/vector_store.py` | ✅ Done |
| R1.2 | Job description 임베딩 → Milvus Top-K 검색 | Must | MatchingService, Milvus | `src/backend/services/matching_service.py` | ✅ Done |
| R1.3 | 기본 매칭 점수 계산 (skill overlap, category, 연차) | Must | ScoringService | `src/backend/services/scoring_service.py` | ✅ Done |
| R1.4 | Category / 경력 연차 메타 필터 지원 | Must | MatchingService, Milvus | `src/backend/services/matching_service.py`, `src/backend/core/vector_store.py` | ✅ Done |
| R1.5 | 매칭 결과에 category / skills 요약 / 총점 포함 | Must | Schemas, MatchingService | `src/backend/services/matching_service.py` | ✅ Done |
| R1.6 | FastAPI REST 엔드포인트 제공 | Must | API Layer | `src/backend/api/` | ✅ Done |
| R2.1 | Multi-Agent 파이프라인 (Skill/Exp/Technical/Culture 점수 분리) | Should | Agent Layer | `src/agents/`, `src/backend/services/agent_orchestration_service.py` | ✅ Done |
| R2.2 | RankingAgent 가중 합산 + 설명 생성 | Should | RankingAgent | `src/agents/ranking_agent.py`, `src/backend/services/agent_orchestration_service.py` | ✅ Done |
| R2.3 | Hybrid retrieval + Milvus 장애 시 Mongo fallback | Should | HybridRetriever | `src/backend/repositories/hybrid_retriever.py` | 🔄 In Progress |
| R2.4 | RecruiterAgent ↔ HiringManagerAgent A2A 가중치 조정 | Should | Agent Layer (A2A) | `src/agents/weight_negotiation_agent.py`, `src/backend/services/agent_orchestration_service.py` | ✅ Done |
| R3.1 | DeepEval + LLM-as-Judge 자동 평가 | Should | Eval Layer | `src/eval/` | ⬜ Pending |
| R3.2 | LangSmith run/experiment/dataset 추적 | Should | Observability | `(planned) src/ops/langsmith_tracer.py` | ⬜ Pending |
| R3.3 | golden_set.jsonl (최소 10–15개 job+candidate 라벨) | Should | Eval Layer | `(planned) src/eval/golden_set.jsonl` | ⬜ Pending |
| R3.4 | Eval 실행 결과 문서화 | Should | Docs | `docs/eval/eval-results.md` | ⬜ Pending |
| R3.5 | 구조화 JSON 로그, health/ready 엔드포인트, latency 지표 | Should | Ops Layer | `src/backend/main.py`, `src/ops/` | 🔄 In Progress |
| R4.1 | React/Vite UI – job description 입력 + 결과 조회 | Should | Frontend | `src/frontend/` | ⬜ Pending |
| R4.2 | UI – 후보 리스트 + 점수 breakdown + explanation 패널 | Should | Frontend | `(planned) src/frontend/components/` | ⬜ Pending |
| R4.3 | API 스키마 ↔ UI ↔ 문서 일관성 | Should | All | `README.md`, `docs/architecture/` | ⬜ Pending |
| R5.1 | README – 설치/실행/ingestion/예시 요청·응답 | Must | Docs | `README.md` | ⬜ Pending |
| R5.2 | 아키텍처/데이터플로우/에이전트 파이프라인 다이어그램 | Must | Docs | `docs/architecture/`, `docs/data-flow/` | 🔄 In Progress |
| R5.3 | TRACEABILITY 매트릭스 (이 문서) | Must | Docs | `docs/governance/TRACEABILITY.md` | 🔄 In Progress |
| R5.4 | Reviewer Checklist self-review + backlog 명시 | Must | Docs | `docs/governance/TRACEABILITY.md` §4 | ⬜ Pending |

**Legend**: ✅ Done · 🔄 In Progress · ⬜ Pending · ❌ Blocked

---

## 1-1. Retrieval/Rerank 고정안 ↔ Requirement ID 연결

| 항목 | 연결 Req IDs | 증거 문서 | 상태 |
|------|--------------|----------|------|
| Embedding 모델 고정: `text-embedding-3-small` | R1.1, R1.2 | `docs/governance/DESIGN_DECISION_MATRIX.md`, `docs/governance/AGENT.md` | 🔄 In Progress |
| Hybrid retrieval 고정: Milvus + BM25 + merge (Top 30) | R2.3 | `docs/architecture/system-architecture.md`, `docs/governance/AGENT.md` | 🔄 In Progress |
| Deterministic scoring 고정: feature extraction + explainable Top 10 | R1.3, R1.5 | `docs/governance/DESIGN_DECISION_MATRIX.md`, `docs/architecture/system-architecture.md` | 🔄 In Progress |
| Rerank/설명 모델 고정: `OPENAI_AGENT_MODEL` (기본 `gpt-4.1-mini`) | R2.2 | `src/backend/core/settings.py`, `src/backend/services/agent_orchestration_service.py` | ✅ Done |
| 모델 선택 근거(비용/속도/단순성)와 확장 경로 문서화 | R5.2, R5.3 | `docs/governance/DESIGN_DECISION_MATRIX.md`, 본 문서 | 🔄 In Progress |
| Mongo 데이터 품질 기반 feature 우선순위(core/conditional) 문서화 | R1.3, R5.3 | `docs/governance/DESIGN_DECISION_MATRIX.md`, `docs/ingestion_normalization_design.md` | ✅ Done |

---

## 2. 구현 컴포넌트 ↔ 설계 결정 ↔ 요구사항 역추적

| 컴포넌트 | 경로 | 커버하는 Req IDs | 관련 ADR / 설계 결정 |
|---------|------|-----------------|-------------------|
| FastAPI API Layer | `src/backend/api/` | R1.6, R3.5, R4.3 | Layered Architecture (ADR-001) |
| IngestionService | `src/backend/services/ingest_resumes.py` | R1.1 | Dataset normalization to single schema |
| MatchingService | `src/backend/services/matching_service.py` | R1.2, R1.3, R1.4, R1.5, R2.3 | Hybrid retrieval (Top 30) + scoring/rerank orchestration |
| ScoringService | `src/backend/services/scoring_service.py` | R1.3, R1.5, R2.2 | Deterministic + agent weighted hybrid rank policy |
| HybridRetriever | `src/backend/repositories/hybrid_retriever.py` | R2.3 | Milvus-primary + Mongo fallback |
| MongoDB Repository | `src/backend/repositories/mongo_repo.py` | R1.3, R1.4, R2.3 | MongoDB as domain data store |
| Milvus Vector Store | `src/backend/core/vector_store.py` | R1.1, R1.2, R1.4 | Milvus as vector store |
| Agent Orchestrator | `src/agents/orchestrator.py` | R2.1, R2.4 | OpenAI Agents SDK I/O scaffold + backend adapter |
| SkillMatchingAgent | `src/agents/skill_agent.py` | R2.1 | Atomic domain agent contract (I/O fixed) |
| ExperienceEvalAgent | `src/agents/experience_agent.py` | R2.1 | Atomic domain agent contract (I/O fixed) |
| TechnicalEvalAgent | `src/agents/technical_agent.py` | R2.1 | Atomic domain agent contract (I/O fixed) |
| CultureFitAgent | `src/agents/culture_agent.py` | R2.1 | Atomic domain agent contract (I/O fixed) |
| RankingAgent | `src/agents/ranking_agent.py` | R2.2 | Weighted scoring + explanation contract |
| Agent Orchestration Adapter | `src/backend/services/agent_orchestration_service.py` | R2.1, R2.2, R2.4 | Live OpenAI scoring + A2A weight negotiation + fallback |
| WeightNegotiationAgent | `src/agents/weight_negotiation_agent.py` | R2.4 | Recruiter/HiringManager proposal + final policy contract |
| DeepEval Tests | `(planned) src/eval/` | R3.1, R3.3 | LLM-as-Judge evaluation doctrine |
| LangSmith Tracer | `(planned) src/ops/langsmith_tracer.py` | R3.2 | Run/experiment tracking |
| Golden Set | `(planned) src/eval/golden_set.jsonl` | R3.3 | Ground-truth evaluation set |
| Frontend (Vite/React) | `src/frontend/` | R4.1, R4.2, R4.3 | Single-page demo UI |
| Health Endpoints | `src/backend/main.py` | R3.5 | `/api/health`, `/api/ready` |
| Governance Docs (Model Baseline) | `docs/governance/DESIGN_DECISION_MATRIX.md`, `docs/governance/AGENT.md` | R1.1, R1.2, R2.2, R2.3, R5.2, R5.3 | Retrieval/Rerank 모델 고정안 및 선택 근거 |

---

## 3. 평가 증거 ↔ 요구사항 매핑

| 평가 항목 | 평가 방법 | 커버하는 Req IDs | 증거 위치 | Status |
|---------|---------|-----------------|---------|--------|
| Retrieval Correctness | golden_set.jsonl 기반 hit-rate@K | R1.2, R3.3 | `docs/eval/eval-results.md` | ⬜ Pending |
| Skill Coverage Score | DeepEval LLM-as-Judge metric | R1.3, R2.1, R3.1 | `src/eval/test_skill_coverage.py` | ⬜ Pending |
| Experience Fit Score | DeepEval LLM-as-Judge metric | R2.1, R3.1 | `src/eval/test_experience_fit.py` | ⬜ Pending |
| Overall Match Quality | DeepEval relevance metric | R2.2, R3.1 | `src/eval/test_match_quality.py` | ⬜ Pending |
| Candidate Diversity | Category/skill 분포 분산 지표 | R2.1 | `src/eval/test_diversity.py` | ⬜ Pending |
| Fallback Behavior | Milvus 장애 mock + Mongo 검색 결과 비교 | R2.3 | `tests/test_retrieval_fallback.py` | ✅ Done |
| API Correctness | FastAPI TestClient + pytest | R1.6, R3.5 | `tests/test_api_endpoints.py` | ✅ Done |
| Agent I/O Contract Validation | Pydantic contract tests | R2.1, R2.2 | `tests/test_agent_io_contracts.py`, `tests/test_agent_orchestration_service.py` | ✅ Done |
| LangSmith Tracing | run trace 확인 (LangSmith UI) | R3.2 | LangSmith Project: `resume-matching` | ⬜ Pending |
| Latency / Throughput | match latency 로그, avg response time | R3.5 | `docs/eval/eval-results.md` | ⬜ Pending |

---

## 4. Senior Engineering Reviewer Checklist

| 카테고리 | 체크 항목 | 기준 | Status | 비고 |
|---------|---------|------|--------|------|
| **Architecture** | Layered architecture 적용 | api→service→repo→model 계층 분리 | ✅ | `src/backend/` 구조 구축 완료 |
| **Architecture** | 도메인 모델 명확성 | Pydantic 스키마로 도메인 모델 문서화 | ⬜ | `src/backend/schemas/` 작성 예정 |
| **Reliability** | Graceful degradation 전략 | 3단계 fallback (LLM→embedding-only→rules) | 🔄 | HybridRetriever(Mongo fallback) 완료, rule fallback 확장 예정 |
| **Reliability** | 입력 검증 | Pydantic validation + 길이 제한 | ⬜ | `src/backend/schemas/` |
| **Observability** | 구조화 JSON 로그 | request_id 포함 JSON 로그 | ⬜ | `src/ops/logging.py` |
| **Observability** | request_id / trace_id 전파 | HTTP 헤더 → 로그 → LangSmith | ⬜ | Middleware 구현 예정 |
| **Observability** | Health / Ready 엔드포인트 | Mongo·Milvus readiness 분리 체크 | ✅ | `src/backend/main.py` |
| **Evaluation** | Golden set 구성 | 최소 10–15개 job+candidate 라벨 | ⬜ | `src/eval/golden_set.jsonl` |
| **Evaluation** | LLM-as-Judge 메트릭 | DeepEval 기반 자동 평가 실행 | ⬜ | `src/eval/` |
| **Evaluation** | 평가 결과 문서화 | 최소 1회 eval 실행 결과 기록 | ⬜ | `docs/eval/eval-results.md` |
| **Security / PII** | 로그 내 PII 마스킹 | resume 원문을 로그에 직접 노출하지 않음 | ⬜ | 로깅 미들웨어에 마스킹 로직 추가 예정 |
| **Docs** | README 완성도 | 설치/실행/ingestion/예시 포함 | ⬜ | `README.md` |
| **Docs** | 아키텍처 다이어그램 | Mermaid 기반 다이어그램 포함 | 🔄 | `docs/architecture/system-architecture.md` 초안 작성됨 |
| **Docs** | TRACEABILITY 매트릭스 | 요구사항 ↔ 코드 ↔ 평가 연결 | 🔄 | 이 문서 |
| **Testing** | 단위 테스트 | 핵심 서비스 함수 단위 테스트 | ✅ | `tests/test_skill_overlap_scoring.py`, `tests/test_agent_orchestration_service.py` |
| **Testing** | 통합 테스트 | API 엔드투엔드 테스트 | ✅ | `tests/test_api_endpoints.py` |

**Legend**: ✅ Done · 🔄 In Progress · ⬜ Pending · ❌ Blocked

---

## 5. Phase별 진행 현황

| Phase | 설명 | 기간 목표 | Status | 완료 기준 |
|-------|-----|---------|--------|---------|
| Phase 0 | Scope & Contracts – 요구사항 확정, 아키텍처·폴더 구조 계약 | Day 1–2 | ✅ Done | `AGENT.md`, `requirements.md`, `system-architecture.md` 완성 |
| Phase 1 | Happy Path – Ingestion + 기본 매칭 API + 최소 UI | Day 2–3 | ✅ Done | `/api/jobs/match` E2E 통과(18개 테스트), Vite UI 구현 완료 |
| Phase 2 | Multi-Agent & Hybrid Retrieval – Agent SDK 통합 | Weekend 전반 | ✅ Done | Agent I/O 계약 + adapter + fallback + A2A 연동 완료 |
| Phase 3 | Evaluation & Observability – DeepEval + LangSmith | Weekend 후반 | 🔄 In Progress | golden set 구성·DeepEval stub 작성, structlog/request_id 미들웨어 완료 |
| Phase 4 | Reviewer Layer & Polish – 문서/다이어그램/Checklist | Day 7 | ⬜ Pending | README, TRACEABILITY, eval-results 완성, self-review 통과 |

---

## 6. 미해결 백로그 (Backlog)

| ID | 항목 | 이유 | 우선순위 |
|----|------|------|---------|
| BL-01 | Bias detection guardrails (언어·지역 편향 탐지) | 시간 부족, Nice-to-have | Low |
| BL-02 | per-IP / per-API key Rate Limiting | 시간 부족, 선택 사항 | Low |
| BL-03 | Feedback loop (랭킹 수정 학습) | `feedback` 컬렉션 설계는 완료, 구현 미착수 | Medium |
| BL-04 | Advanced analytics dashboard | 범위 외 | Low |
| BL-05 | suriyaganesh 구조화 데이터셋 enrichment 완성 | Phase 1에서 메인 데이터셋 우선 처리 후 추가 | Medium |
| BL-06 | IR metrics (precision@k, NDCG) 추가 | DeepEval 기반 기본 평가 후 추가 | Medium |

---

*Last updated: 2026-03-13 (Phase 1·2 ✅ 완료 확정, Phase 3 착수) | Maintainer: 프로젝트 팀*
