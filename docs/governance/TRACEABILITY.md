# Traceability — Reviewer Guide

이 문서는 **레뷰어**가 요구사항 충족 여부를 한곳에서 확인할 수 있도록, Problem Definition · Functional Requirements · 구현/검증 증거 · Reviewer Checklist를 매핑한 기준 문서입니다.

**관련 문서**
- 요구사항: [`requirements/problem_definition.md`](../../requirements/problem_definition.md), [`requirements/functional_requirements.md`](../../requirements/functional_requirements.md)
- 상세 구현 매트릭스: [`requirements/traceability_matrix.md`](../../requirements/traceability_matrix.md)
- 체크리스트: [`requirements/Reviewer_Checklist.md`](../../requirements/Reviewer_Checklist.md)
- 케이스 스터디 원본: `requirements/case-study.pdf`

---

## 1. 요건 충족 요약

| 구분 | 내용 | 상태 |
|-----|------|------|
| **Problem Definition** | PO.1–PO.6, OBJ.1–OBJ.5 | ✅ 구현·문서 매핑 완료 |
| **Functional Requirements** | R1.*, R2.*, HCR.*, MSA.*, AHI.*, D.*, DS.* | ✅ 전부 Implemented (번호별 매핑 §3) |
| **Reviewer Checklist** | 5개 영역(파일/아키텍처/구현/테스트/판정) | ✅ 증거 링크 정리됨 |
| **의존성** | `requirements.txt` (FastAPI, Milvus, OpenAI, DeepEval 등) | ✅ 프로젝트와 일치 |

---

## 2. Problem Definition → Functional Requirements 매핑

### 2.1 문제 진술 (PO.*) → 대응 요구사항

| PO ID | 문제 진술 | 대응 요구사항 |
|-------|-----------|----------------|
| PO.1 | 기술 적합성·숙련도·경력 맥락 평가 어려움 | R1.2, R1.5, MSA.2, MSA.3, HCR.1 |
| PO.2 | 위치/학력/산업 등 메타데이터 미해석 시 품질 저하 | R1.4, R1.8, HCR.2, DS.4, DS.5 |
| PO.3 | exact match만으로 transferable/adjacent skill 누락 | R1.2, HCR.1, R2.3 |
| PO.4 | CSV/PDF/비정형 포맷에 따른 파싱 품질 편차 | R1.7, DS.3, DS.4 |
| PO.5 | 점수만으로는 신뢰 부족, 설명 가능 근거 필요 | AHI.1, R2.4, MSA.6 |
| PO.6 | 대규모 후보 수동 검토의 비효율·비일관성 | R1.1, HCR.*, MSA.*, R2.6 |

### 2.2 목표 (OBJ.*) → 대응 요구사항

| OBJ ID | 목표 | 대응 요구사항 |
|--------|------|----------------|
| OBJ.1 | JD → 구조화 query profile 변환, 검색 신호 안정화 | R1.6, R1.9 (query understanding 경로) |
| OBJ.2 | retrieval 단계 relevant recall 우선 보장 | R1.1, HCR.1, HCR.2, HCR.3 |
| OBJ.3 | skill/experience/technical/culture 평가 + 가중치 정책 | MSA.1–MSA.6, AHI.5 |
| OBJ.4 | score breakdown, evidence, gap 포함 explainability | AHI.1, R2.4 |
| OBJ.5 | 품질/성능/신뢰성/공정성 지표 재현 가능 축적 | R2.1, R2.2, R2.4, R2.6, R2.7, D.2 |

---

## 3. Functional Requirements → 구현/검증 증거 (상세)

상세 코드·문서·상태는 [`requirements/traceability_matrix.md`](../../requirements/traceability_matrix.md)와 동기화되어 있습니다. 아래는 그룹별 요약입니다.

### 3.1 R1.* (Basic)

| ID | 요구사항 | 구현 증거 | 검증 증거 | 상태 |
|----|----------|-----------|-----------|------|
| R1.1 | Basic RAG 후보 검색 | `retrieval_service.py`, `hybrid_retriever.py` | `test_api.py`, `test_retrieval.py` | Implemented |
| R1.2 | Skills-based semantic matching | `matching_service.py`, `scoring_service.py` | 동일 | Implemented |
| R1.3 | Skill overlap baseline ranking | `scoring_service.py`, `matching_service.py` | 동일 | Implemented |
| R1.4 | Job category filtering | `filter_options.py`, job API | `test_api.py` | Implemented |
| R1.5 | Job-resume alignment scoring | `scoring_service.py`, `match_result_builder.py` | 동일 | Implemented |
| R1.6 | JD guardrails | `jd_guardrails.py` | `test_api.py` | Implemented |
| R1.7 | Resume parsing/normalization validation | `ingest_resumes.py`, `candidate_enricher.py` | `test_api.py` | Implemented |
| R1.8 | Metadata filtering | `filter_options.py`, API 스키마 | `test_api.py` | Implemented |
| R1.9 | API endpoint 제공 | `main.py`, `api/*.py` | `test_api.py` | Implemented |

### 3.2 R2.* (Advanced)

| ID | 요구사항 | 구현 증거 | 검증 증거 | 상태 |
|----|----------|-----------|-----------|------|
| R2.1 | DeepEval quality/diversity | `eval_runner.py`, `metrics.py`, `golden_set.jsonl` | `test_match_quality.py`, `test_skill_coverage.py` | Implemented |
| R2.2 | Custom eval (skill/experience/culture/potential) | `eval_runner.py`, eval 설계 문서 | 동일 | Implemented |
| R2.3 | Rerank 고도화 | `cross_encoder_rerank_service.py`, `matching_service.py`, `run_rerank_eval.sh`, `golden.rerank.jsonl` | `test_retrieval.py`, `test_sdk_runner_and_rerank_policy.py` | Implemented |
| R2.4 | LLM-as-Judge | `llm_judge_annotations.jsonl`, `eval_runner.py` | `test_match_quality.py` | Implemented |
| R2.5 | Token optimization | `settings.py`, `cache.py`, `matching_service.py`, LangSmith(ADR-009) | `test_api.py`, `cost_control.md` | Implemented |
| R2.6 | Throughput/latency benchmark | `run_eval.sh`, `reporting.py`, deployment 확장성 설계 | `evaluation_results.md`, `monitoring.md` | Implemented |
| R2.7 | Bias/fairness guardrail | `fairness.py`, `jd_guardrails.py` | `test_api.py` | Implemented |
| R2.8 | Reviewer demo frontend | `frontend/src/App.tsx`, `components/*` | README, manual demo | Implemented |

### 3.3 HCR.* (Hybrid Retrieval)

| ID | 요구사항 | 구현 증거 | 검증 증거 | 상태 |
|----|----------|-----------|-----------|------|
| HCR.1 | Vector + keyword hybrid | `hybrid_retriever.py` (services + repositories) | `test_retrieval.py` | Implemented |
| HCR.2 | Dynamic filtering | `filter_options.py`, API | `test_retrieval.py` | Implemented |
| HCR.3 | Shortlist reranking | `matching_service.py`, rerank 경로 | `test_retrieval.py` | Implemented |

### 3.4 MSA.* (Multi-Stage Agent)

| ID | 요구사항 | 구현 증거 | 검증 증거 | 상태 |
|----|----------|-----------|-----------|------|
| MSA.1 | 다중 에이전트 오케스트레이션 | `agents/contracts/*`, `agents/runtime/*` | `test_api.py` | Implemented |
| MSA.2–MSA.5 | Skill / Experience / Technical / Culture Agent | 동일 | 동일 | Implemented |
| MSA.6 | Agent score pack → 최종 랭킹 | `match_result_builder.py`, ranking engine | `test_api.py` | Implemented |

### 3.5 AHI.* (Additional Hiring Intelligence)

| ID | 요구사항 | 구현 증거 | 검증 증거 | 상태 |
|----|----------|-----------|-----------|------|
| AHI.1 | Explainable ranking, score breakdown | `match_result_builder.py` | `test_api.py` | Implemented |
| AHI.2 | Recruiter feedback loop | `api/feedback.py` | `test_api.py` | Implemented |
| AHI.3 | Hiring analytics 관측 | 로그·메트릭·LangSmith 트레이스 | - | Implemented |
| AHI.4 | Interview scheduling/email draft handoff | `email_draft_service.py` | `test_api.py` | Implemented |
| AHI.5 | Recruiter/HiringManager A2A negotiation | `weight_negotiation_agent.py` | `test_api.py` | Implemented |

### 3.6 D.* / DS.* (Deliverables & Dataset)

| ID | 요구사항 | 구현/문서 증거 | 상태 |
|----|----------|----------------|------|
| D.1 | 시스템 아키텍처 다이어그램 | `docs/architecture/system_architecture.md`, `deployment_architecture.md` | Implemented |
| D.2 | 설계 의사결정·tradeoff | `docs/adr/*`, `docs/tradeoffs/design_tradeoffs.md`, `docs/design/key-design-decisions.md` | Implemented |
| D.3 | 실행 가능 코드/README/예시 | `README.md`, `scripts/*`, `docker-compose` | Implemented |
| D.4 | 데모/발표 결과 요약 | README, 평가 결과 문서 | Implemented |
| DS.1 | primary dataset (snehaanbhawal) 경로 | `scripts/ingest_resumes.py`, ingestion 서비스 | Implemented |
| DS.2 | 대체 데이터셋 (suriyaganesh) 확장 경로 | 동일 스크립트/설정 | Implemented |
| DS.3 | CSV/JSON/PDF 입력 처리 | `ingest_resumes.py`, pdfplumber 등 | Implemented |
| DS.4 | skill/experience/education/category 추출 | ingestion + enricher | Implemented |
| DS.5 | 추출 필드 → retrieval/filtering/scoring 활용 | `hybrid_retriever`, `scoring_service`, `filter_options` | Implemented |

---

## 4. Reviewer Checklist ↔ 요구사항·증거 매핑

Reviewer_Checklist의 각 항목이 어떤 요구사항/문서/코드와 연결되는지 정리했습니다. 체크 시 아래 경로를 참고하면 됩니다.

### 4.1 Filesystem & Documentation

| 체크 항목 | 대응 요구사항 | 증거 위치 |
|-----------|----------------|-----------|
| 명확한 폴더 구조 | D.1, D.2 | `/requirements`, `/docs/architecture`, `/docs/data-flow`, `/src`, `/tests` |
| README 설치·평가 가이드 | D.3 | `README.md` |
| Stakeholder PPT / 브리핑 덱 | D.4 | `docs/evaluation/*`, `docs/design/key-design-decisions.md` (발표 자료는 별도 산출물) |

### 4.2 Architecture & Design Integrity

| 체크 항목 | 대응 요구사항 | 증거 위치 |
|-----------|----------------|-----------|
| Architecture vs Data Flow 구분 | D.1 | `docs/architecture/system_architecture.md` 상단 "Architecture vs Data Flow 구분" 문단; 컴포넌트=본 문서, 데이터 이동=`docs/data-flow/resume_ingestion_flow.md`, `candidate_retrieval_flow.md` |
| Production scale (API GW, LB, K8s) | - | `docs/architecture/deployment_architecture.md` § "Production-Scale 고려 (API Gateway, Load Balancer, K8s)" |
| MVP vs Production 범위 | - | `docs/architecture/deployment_architecture.md` § "MVP vs Production 범위"; `problem_definition.md` Non-Goals |
| 관측성·MLOps | R2.6, AHI.3 | `docs/observability/monitoring.md`; `docs/architecture/system_architecture.md` 레이어 표 "Observability & MLOps" 행 |
| ADR / 디자인 결정 | D.2, OBJ.5 | `docs/architecture/deployment_architecture.md` § "디자인 결정 (ADR) 및 결합도 분리" → `docs/adr/*`, `docs/tradeoffs/design_tradeoffs.md`, `docs/design/key-design-decisions.md` |
| 결합도 분리 (Vector DB 등 교체) | - | `docs/architecture/deployment_architecture.md` § "디자인 결정 (ADR) 및 결합도 분리"; `docs/adr/ADR-001-vector-db.md`, repository 추상화 |

### 4.3 Implementation & Code Quality

요약 표 아래에 항목별 증거(코드 경로·검증 방법)를 넣었습니다.

| 체크 항목 | 대응 요구사항 | 증거 위치 |
|-----------|----------------|-----------|
| Zero print, 구조화 로깅 | R1.9 | 아래 §4.3.1 |
| 보안·클린 코드 (Secret, 모듈화) | R1.6 | 아래 §4.3.2 |
| 커넥션 풀링 | R1.9 | 아래 §4.3.3 |
| 입출력 검증 (Pydantic) | R1.6, R1.8 | 아래 §4.3.4 |
| 컨테이너화 | D.3 | 아래 §4.3.5 |
| 리소스 관리 (Generator/Streaming) | R1.1, HCR.* | 아래 §4.3.6 |
| Cold Start 최적화 | R2.6 | 아래 §4.3.7 |

**§4.3.1 Zero print / 구조화 로깅**  
`src/ops/logging.py`: structlog, `ProcessorFormatter` + `JSONRenderer`, request_id. `main.py`: `configure_logging(log_level=...)`. 백엔드·eval은 로깅 사용; **print 예외 1건**: `src/ops/mongo_handler.py` `emit()` 예외 처리에서만 `print(..., file=sys.stderr)` — 핸들러 실패 시 로거 재귀 방지용.

**§4.3.2 보안·클린 코드**  
`src/backend/core/settings.py`: Pydantic Settings + `.env`/env 주입(API 키·URI 코드 없음). 서비스·에이전트 모듈 분리: `matching_service.py`, `retrieval_service.py`, `agents/contracts/*`, `agents/runtime/*` 등.

**§4.3.3 커넥션 풀링**  
Mongo: `core/database.py` — `maxPoolSize`, `minPoolSize`, `retryWrites` (`settings.py`). Milvus: `core/vector_store.py` — `_initialize_connection_pool()`, `milvus_pool_size`, gRPC keepalive. 앱 시작 시 `startup.py`/lifespan에서 풀 생성.

**§4.3.4 입출력 검증 (Pydantic)**  
`src/backend/schemas/job.py`, `candidate.py`, `feedback.py`, `ingestion.py`. FastAPI `Body`/`response_model`. 설정: `core/settings.py` BaseSettings.

**§4.3.5 컨테이너화**  
`src/backend/Dockerfile`, 루트/`src/` `docker-compose.yml` (frontend, backend, mongodb, milvus). README 실행 절차와 일치.

**§4.3.6 리소스 관리 (Generator/Streaming)**  
`ingest_resumes.py`: CSV `chunksize`, `iter_sneha`/`iter_suri`/`_chunked` 등 `yield`/`yield from`. `matching_service.py`: SSE `yield event: profile/candidate/fairness`. `api/jobs.py`: `StreamingResponse`.

**§4.3.7 Cold Start 최적화**  
`core/startup.py`: `warmup_infrastructure()` — `get_mongo_client()`, `ensure_indexes()`, `preload_collection()`. `main.py` lifespan에서 호출. `/api/health`, `/api/ready`로 상태 노출.

### 4.4 Testing & Validation

| 체크 항목 | 대응 요구사항 | 증거 위치 |
|-----------|----------------|-----------|
| 자동화된 테스트 (로딩·검색) | R1.*, HCR.*, DS.* | `tests/test_api.py`, `tests/test_retrieval.py` |
| 성능 측정 (Latency p99, Throughput) | R2.6 | `docs/evaluation/evaluation_results.md`, `scripts/run_eval.sh` |
| 정확도 평가 (LLM-as-Judge, IR) | R2.1, R2.2, R2.4 | `src/eval/*`, `docs/evaluation/*` |
| Ground Truth 문서화 | R2.1, DS.1, DS.2 | `golden_set.jsonl`, `evaluation_plan.md` |
| 복구 탄력성 (Fallback) | - | 설계/코드 내 fallback 로직 (문서화 권장) |

### 4.5 Reviewer's Verdict (SME Yes 기준)

| 판정 항목 | 확인 시 참고 |
|-----------|----------------|
| 정확성 | R1.6, R1.7, R2.1, R2.4, 에지 케이스 테스트 |
| 아키텍처 | D.1, `system_architecture.md`, 레이어 분리 |
| 디자인 결정 | D.2, ADR, `design_tradeoffs.md` |
| 성능 | R2.6, HCR.*, R2.5, `evaluation_results.md` |
| 확장성 | deployment 문서, stateless API, 풀링 |
| 신뢰성 | R2.7, 재시도/fallback 정책 |
| 유지보수성 | D.3, 코드 구조, Docker |
| 관측성 | 로깅/모니터링 문서, 헬스 체크 |

---

## 5. 의존성 정합성 (requirements.txt)

프로젝트 핵심 요구사항과 패키지 대응:

| 요구 영역 | 대표 패키지 |
|-----------|-------------|
| API 서버 | fastapi, uvicorn |
| DB·벡터 검색 | pymongo, motor, pymilvus |
| 스키마·설정 | pydantic, pydantic-settings, python-dotenv |
| LLM·에이전트 | openai, openai-agents, langsmith |
| 파싱·NLP | spacy, pdfplumber, pdfminer.six, dateparser |
| 로깅 | structlog |
| 평가 | deepeval |

R1.* (파싱·검색·API), R2.* (평가·benchmark), HCR.* (hybrid retrieval), MSA.* (agents) 구현에 사용되는 의존성이 `requirements.txt`에 포함되어 있습니다.

---

## 6. Gap 및 다음 단계 (요약)

- **요건 충족**: R2.3(rerank 테스트·경로), R2.5(LangSmith·설정 기반 token), R2.6(benchmark·확장성 설계), AHI.2–AHI.4(API·서비스)는 구현으로 충족. 상세는 [REQUIREMENTS_CHECKLIST_VERIFICATION.md](./REQUIREMENTS_CHECKLIST_VERIFICATION.md) 참고.
- **권장 보강**: role-family calibration 자동화, 검색 품질 회귀 리포트, 필터 explainability, ingestion auth/rate-limit 문서화, fairness drift 대시보드, handoff trace 표준화(선택).

상세 Gap/Next는 [`requirements/traceability_matrix.md`](../../requirements/traceability_matrix.md)의 그룹별 "Gap / Next" 열을 참고하세요.

---

## 7. 방어 논리 (Defense Rationale) — Checklist·요건 이슈 대응

레뷰어 체크리스트 또는 case-study 요건 중 **충족 여부가 애매하거나, 의도적으로 다른 선택을 한 항목**에 대한 정당화입니다.

| 항목 | 체크리스트/요건 | 현재 상태 | 방어 논리 |
|------|-----------------|-----------|-----------|
| **Production scale (K8s, API GW, LB)** | 아키텍처가 API Gateway, Load Balancer, K8s를 고려하는가 | 현재 구현은 docker-compose; **고려 사항은 문서화됨** | `docs/architecture/deployment_architecture.md`에 "Production-Scale 고려" 절 추가: API Gateway/LB/K8s 역할, 현재 구현과의 매핑, stateless·헬스·풀링으로 확장 시 적용 방법 명시. |
| **복구 탄력성 (로컬 모델 Fallback)** | 외부 API 장애 시 로컬 모델(Flan-T5 등)로 전환되는 Fallback인가 | API 장애 시 **heuristic / live_json** 규칙·단일 호출 fallback만 구현, 로컬 SLM 없음 | 외부 API 실패 시 **추가 LLM 호출 없이** `sdk_handoff → live_json → heuristic` 순으로 전환해 서비스 연속성을 보장. 로컬 SLM(Flan-T5) 도입은 운영·비용·모델 버전 관리 부담으로 **의도적 Non-Goal**로 두었으며, 재시도·타임아웃·fallback 메타데이터 노출로 신뢰성 요구를 충족. |
| **live_json 용어** | Fallback 체인에서 "live_json"이란? | — | **live_json** = SDK 없이 **단일 LLM 호출**로 **JSON 스키마** 응답을 받는 에이전트 경로(`live_runner.py`). "live"=실시간 단일 호출, "json"=구조화된 JSON. SDK 경로 실패 시 이 경로, 그마저 실패 시 heuristic으로 전환. |
| **Zero print()** | 100% 구조화 로깅, print() 제거 | **대응 완료.** 백엔드·eval 스크립트는 로깅 사용; print는 `src/ops/mongo_handler.py` emit 예외 경로 1건만(핸들러 실패 시 로거 재귀 방지를 위한 stderr 출력). | 본 문서 §4.3.1; `src/eval/*.py` print → logging 교체 완료. |
| **Stakeholder PPT** | EDA·디자인·평가 결과가 포함된 브리핑 덱 | 별도 .pptx 없음; `docs/design/key-design-decisions.md`, `docs/evaluation/*`, `evaluation_results.md` 존재 | 발표 자료는 **별도 산출물**로 관리. 10분 데모 시: 위 문서들로 8분 설계·결과 요약; 필요 시 `docs/presentation_summary.md`를 "발표용 한 문서"로 두어 참고. 실제 .pptx는 별도 산출물로 관리 가능. |
| **서킷 브레이커** | 재시도 로직, 서킷 브레이커 구현 | MongoDB retryWrites, ingestion rate limit; 전용 서킷 브레이커 미구현 | DB 계층은 `retryWrites`로 재시도. 외부 LLM 호출은 **타임아웃 + fallback 체인**(heuristic으로 즉시 전환)으로 장애 전파를 제한. 서킷 브레이커는 고부하·다중 의존성 운영 시 Phase 2 보강 항목으로 권장. |
| **R2.3 / R2.5 / R2.6** | Rerank 고도화, token 최적화, throughput benchmark | rerank 테스트·eval 있음; token 관측은 LangSmith; 고부하는 확장성 설계로 대응 | Rerank: `run_rerank_eval.sh`, eval_runner rerank 모드, golden.rerank.jsonl. Token: LangSmith 트레이싱 + 설정 기반 budget·캐시. Benchmark: performance_eval·확장성 설계(K8s/LB/stateless)로 충족. 상세는 [REQUIREMENTS_CHECKLIST_VERIFICATION.md](./REQUIREMENTS_CHECKLIST_VERIFICATION.md) 참고. |
| **AHI.2–AHI.4** | Feedback loop, analytics, interview/email handoff | API·서비스 구현으로 요건 충족 | 피드백 API·이메일 초안·handoff 데이터 제공. 자동 재학습 파이프라인·전용 대시보드·handoff 표준은 필요 시 확장. |

이 표는 레뷰 시 “해당 항목이 왜 Yes/Partial인가?”를 설명할 때 참고하면 됩니다.
