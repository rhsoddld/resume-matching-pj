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
| **Functional Requirements** | R1.*, R2.*, HCR.*, MSA.*, AHI.*, D.*, DS.* | ✅ 대부분 Implemented, 일부 Partial |
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
| R2.3 | Rerank 고도화 | `cross_encoder_rerank_service.py`, `matching_service.py` | `test_retrieval.py` | Partial |
| R2.4 | LLM-as-Judge | `llm_judge_annotations.jsonl`, `eval_runner.py` | `test_match_quality.py` | Implemented |
| R2.5 | Token optimization | `settings.py`, `cache.py`, `matching_service.py` | `test_api.py`, `cost_control.md` | Partial |
| R2.6 | Throughput/latency benchmark | `run_eval.sh`, `reporting.py` | `evaluation_results.md`, `monitoring.md` | Partial |
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
| AHI.2 | Recruiter feedback loop | `api/feedback.py` | `test_api.py` | Partial |
| AHI.3 | Hiring analytics 관측 | feedback/analytics 경로 | - | Partial |
| AHI.4 | Interview scheduling/email draft handoff | `email_draft_service.py` | `test_api.py` | Partial |
| AHI.5 | Recruiter/HiringManager A2A negotiation | `weight_negotiation_agent.py` | `test_api.py` | Implemented |

### 3.6 D.* / DS.* (Deliverables & Dataset)

| ID | 요구사항 | 구현/문서 증거 | 상태 |
|----|----------|----------------|------|
| D.1 | 시스템 아키텍처 다이어그램 | `docs/architecture/system_architecture.md`, `deployment_architecture.md` | Implemented |
| D.2 | 설계 의사결정·tradeoff | `docs/adr/*`, `docs/tradeoffs/design_tradeoffs.md`, `Key Design Decisions.md` | Implemented |
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
| Stakeholder PPT / 브리핑 덱 | D.4 | `docs/evaluation/*`, `Key Design Decisions.md` (발표 자료는 별도 산출물) |

### 4.2 Architecture & Design Integrity

| 체크 항목 | 대응 요구사항 | 증거 위치 |
|-----------|----------------|-----------|
| Architecture vs Data Flow 구분 | D.1 | `docs/architecture/system_architecture.md`, `docs/data-flow/*` |
| Production scale (API GW, LB, K8s) | - | `docs/architecture/deployment_architecture.md` |
| POC vs Production 범위 | - | `problem_definition.md` (Non-Goals), ADR |
| 관측성·MLOps | R2.6, AHI.3 | `docs/observability/monitoring.md`, `logging_metrics.md` |
| ADR / 디자인 결정 | D.2, OBJ.5 | `docs/adr/*`, `docs/tradeoffs/design_tradeoffs.md`, `Key Design Decisions.md` |
| 결합도 분리 (Vector DB 등 교체) | - | `docs/adr/ADR-001-vector-db.md`, repository 추상화 |

### 4.3 Implementation & Code Quality

| 체크 항목 | 대응 요구사항 | 증거 위치 |
|-----------|----------------|-----------|
| Zero print, 구조화 로깅 | R1.9 | structlog, `docs/observability/logging_metrics.md` |
| 보안·클린 코드 (Secret, 모듈화) | R1.6 | `jd_guardrails.py`, `core/settings.py`, `.env` |
| 커넥션 풀링 | R1.9 | Motor, Milvus client 설정 |
| 입출력 검증 (Pydantic) | R1.6, R1.8 | `schemas/*`, API 스키마 |
| 컨테이너화 | D.3 | `Dockerfile`, `docker-compose.yml` |
| 리소스 관리 (Generator/Streaming) | R1.1, HCR.* | ingestion/retrieval 경로 |
| Cold Start 최적화 | R2.6 | 인덱스/모델 사전 로드 |

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

- **Partial 항목**: R2.3 (rerank 고도화), R2.5 (token meter/alert), R2.6 (고부하 자동화), AHI.2–AHI.4 (analytics/reporting·handoff 강화).
- **권장 보강**: role-family calibration 자동화, 검색 품질 회귀 리포트, 필터 explainability, ingestion auth/rate-limit 문서화, fairness drift 대시보드, handoff trace 표준화.

상세 Gap/Next는 [`requirements/traceability_matrix.md`](../../requirements/traceability_matrix.md)의 그룹별 "Gap / Next" 열을 참고하세요.
