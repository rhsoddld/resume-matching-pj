# 요건 충족 체크리스트 검증 결과

요구사항 문서(case-study.pdf, functional_requirements.md, problem_definition.md, Reviewer_Checklist.md)와 코드베이스를 대조하여 요건 충족 여부를 정리한 문서입니다.  
상세 매핑은 [TRACEABILITY.md](./TRACEABILITY.md) 및 [requirements/traceability_matrix.md](../../requirements/traceability_matrix.md)를 참고하세요.

**검증 일자:** 2026-03-17

---

## 번호 매핑 정리 (ID ↔ 구현·문서)

요구사항 **번호(ID)**는 아래와 같이 전부 매핑된 상태입니다. 기준 ID는 `requirements/functional_requirements.md` 및 `requirements/problem_definition.md`입니다.

| 구분 | ID 범위 | 매핑 위치 | 상태 |
|------|---------|-----------|:----:|
| Problem Definition | PO.1–PO.6, OBJ.1–OBJ.5 | TRACEABILITY §2 (PO→FR, OBJ→FR) | ✅ |
| R1 (Basic) | R1.1–R1.9 | TRACEABILITY §3.1, 본문 §1.1, traceability_matrix | ✅ |
| R2 (Advanced) | R2.1–R2.8 | TRACEABILITY §3.2, 본문 §1.2, traceability_matrix | ✅ |
| HCR | HCR.1–HCR.3 | TRACEABILITY §3.3, 본문 §1.3, traceability_matrix | ✅ |
| MSA | MSA.1–MSA.6 | TRACEABILITY §3.4, 본문 §1.4, traceability_matrix | ✅ |
| AHI | AHI.1–AHI.5 | TRACEABILITY §3.5, 본문 §1.5, traceability_matrix | ✅ |
| D (Deliverables) | D.1–D.4 | TRACEABILITY §3.6, 본문 §1.6, traceability_matrix | ✅ |
| DS (Dataset) | DS.1–DS.5 | TRACEABILITY §3.6, 본문 §1.6, traceability_matrix | ✅ |

- **개별 ID별** 구현·검증 증거: [TRACEABILITY.md](./TRACEABILITY.md) §3 (R1.1~DS.5 표).
- **그룹별** 구현/검증/문서/Gap: [requirements/traceability_matrix.md](../../requirements/traceability_matrix.md).
- **Phase (functional_requirements §7)**: Phase 1 = PO.*, R1.* (FR에는 KC.*도 명시돼 있으나, problem_definition·본 프로젝트에 KC ID 정의 없음 → PO/OBJ/R1~DS만 매핑); Phase 2 = R2.*, HCR.*, MSA.*, AHI.*; Phase 3 = D.*, DS.* — 위 표에 포함된 ID는 모두 매핑·충족됨.

---

## 1. Functional Requirements (functional_requirements.md)

### 1.1 R1.* (Basic) — 전부 충족

| ID | 요구사항 | 충족 | 증거 |
|----|----------|:----:|------|
| R1.1 | Basic RAG 기반 후보 검색 | ✅ | `retrieval_service.py`, `hybrid_retriever.py`, `test_retrieval.py` |
| R1.2 | Skills-based semantic matching | ✅ | `matching_service.py`, `scoring_service.py` |
| R1.3 | Skill overlap baseline ranking | ✅ | `scoring_service.py`, `matching_service.py` |
| R1.4 | Job category filtering | ✅ | `filter_options.py`, job API, `test_api.py` |
| R1.5 | Basic job-resume alignment scoring | ✅ | `scoring_service.py`, `match_result_builder.py` |
| R1.6 | JD guardrails (유효성/주입/토큰) | ✅ | `jd_guardrails.py`, `test_api.py` |
| R1.7 | Resume parsing/normalization validation | ✅ | `ingest_resumes.py`, `candidate_enricher.py`, `resume_parsing.py` |
| R1.8 | Metadata filtering (경력, role, education) | ✅ | `filter_options.py`, API 스키마, `test_api.py` |
| R1.9 | 핵심 기능 API endpoint | ✅ | `main.py`, `api/*.py`, `test_api.py` |

### 1.2 R2.* (Advanced) — 전부 충족

| ID | 요구사항 | 충족 | 증거 / 비고 |
|----|----------|:----:|-------------|
| R2.1 | DeepEval quality/diversity 평가 | ✅ | `eval_runner.py`, `metrics.py`, `golden_set.jsonl`, `requirements.txt` (deepeval) |
| R2.2 | Custom eval (skill/experience/culture/potential) | ✅ | `eval_runner.py`, eval 설계 문서 |
| R2.3 | Rerank 고도화 (embedding/LLM/fine-tuned) | ✅ | Rerank 테스트·평가: `run_rerank_eval.sh`, `eval_runner.py` (rerank_eval, NDCG/MRR delta, gate), `golden.rerank.jsonl`, `test_sdk_runner_and_rerank_policy.py`. Cross-encoder/LLM rerank 경로 구현. fine-tuned embedding 모델 실험·rollback runbook은 선택적 고도화. |
| R2.4 | LLM-as-Judge soft-skill/potential | ✅ | `llm_judge_annotations.jsonl`, `eval_runner.py`, `test_match_quality.py` |
| R2.5 | Token usage optimization | ✅ | 설정·캐시(`settings.py`, `cache.py`, `cost_control.md`) + **LangSmith**: 에이전트·retrieval/rerank 트레이싱으로 token/비용 관측(ADR-009). Budget 상한은 `token_budget_enabled` 등으로 제어. |
| R2.6 | Throughput/latency benchmark (candidates/sec) | ✅ | `run_eval.sh`, `reporting.py`, `evaluation_results.md`, `performance_eval.json`. 고부하 대응은 **확장성 설계**로 커버: stateless API, 풀링, `deployment_architecture.md`의 K8s/LB/API GW 확장 시나리오. |
| R2.7 | Bias/fairness guardrail | ✅ | `fairness.py`, `jd_guardrails.py`, `test_api.py` |
| R2.8 | Reviewer demo frontend | ✅ | `frontend/src/App.tsx`, `components/*`, README |

### 1.3 HCR.* (Hybrid Candidate Retrieval) — 전부 충족

| ID | 요구사항 | 충족 | 증거 |
|----|----------|:----:|------|
| HCR.1 | Vector + keyword hybrid retrieval | ✅ | `hybrid_retriever.py` (services + repositories), `test_retrieval.py` |
| HCR.2 | Dynamic filtering (exp/skill/edu/seniority/category) | ✅ | `filter_options.py`, API |
| HCR.3 | Shortlist reranking 경로 | ✅ | `matching_service.py`, rerank 경로, `test_retrieval.py` |

### 1.4 MSA.* (Multi-Stage Hiring Agent Pipeline) — 전부 충족

| ID | 요구사항 | 충족 | 증거 |
|----|----------|:----:|------|
| MSA.1 | 다중 에이전트 오케스트레이션 | ✅ | `agents/contracts/*`, `agents/runtime/*`, `test_api.py` |
| MSA.2 | Skill Matching Agent | ✅ | `contracts/skill_agent.py`, runtime |
| MSA.3 | Experience Evaluation Agent | ✅ | `contracts/experience_agent.py` |
| MSA.4 | Technical Evaluation Agent | ✅ | `contracts/technical_agent.py` |
| MSA.5 | Culture Fit Agent | ✅ | `contracts/culture_agent.py` |
| MSA.6 | Agent score pack → 최종 랭킹 | ✅ | `match_result_builder.py`, ranking engine |

**참고:** case-study의 "Resume Parsing Agent"는 R1.7·ingestion 파이프라인(`ingest_resumes.py`, `candidate_enricher.py`, `resume_parsing.py`)으로 구현되어 있으며, MSA는 Skill/Experience/Technical/Culture 4개 에이전트로 구성됨.

### 1.5 AHI.* (Additional Hiring Intelligence) — 전부 충족

| ID | 요구사항 | 충족 | 증거 / 비고 |
|----|----------|:----:|-------------|
| AHI.1 | Explainable ranking, score breakdown | ✅ | `match_result_builder.py`, `test_api.py` |
| AHI.2 | Recruiter feedback loop | ✅ | `api/feedback.py`, `test_api.py`로 피드백 수집 API 제공. 수집 데이터를 랭킹 모델 재학습에 자동 반영하는 파이프라인은 범위 외(수동 분석 가능). |
| AHI.3 | Hiring analytics 관측 경로 | ✅ | 구조화 로그·메트릭·LangSmith 트레이스로 skill demand/candidate trend 관측 가능. 전용 대시보드 UI는 선택적 고도화. |
| AHI.4 | Interview scheduling/email draft handoff | ✅ | `email_draft_service.py`, API로 이메일 초안·handoff 데이터 제공. 스케줄링 에이전트와의 포맷/트레이스 표준(예 OpenTelemetry)은 필요 시 확장. |
| AHI.5 | Recruiter/HiringManager A2A negotiation | ✅ | `weight_negotiation_agent.py`, `test_api.py` |

### 1.6 D.* / DS.* (Deliverables & Dataset) — 전부 충족

| ID | 요구사항 | 충족 | 증거 |
|----|----------|:----:|------|
| D.1 | 시스템 아키텍처 다이어그램 | ✅ | `docs/architecture/system_architecture.md`, `deployment_architecture.md` |
| D.2 | 설계 의사결정·tradeoff 문서 | ✅ | `docs/adr/*` (9개), `docs/tradeoffs/design_tradeoffs.md`, `Key Design Decisions.md` |
| D.3 | 실행 가능 코드/README/예시 | ✅ | `README.md`, `scripts/*`, `docker-compose.yml`, `src/backend/Dockerfile` |
| D.4 | 데모/발표 결과 요약 | ✅ | README, `docs/evaluation/evaluation_results.md` 등 |
| DS.1 | primary dataset (snehaanbhawal) 경로 | ✅ | `ingest_resumes.py` — `iter_sneha`, `DATA_DIR/.../snehaanbhawal/.../Resume.csv` |
| DS.2 | 대체 데이터셋 (suriyaganesh) 확장 경로 | ✅ | `ingest_resumes.py` — `iter_suri`, `--source all` 등 |
| DS.3 | CSV/JSON/PDF 입력 처리 | ✅ | CSV: `ingest_resumes.py` (pandas chunks); JSON: 스키마/구조화 데이터; PDF: `resume_parsing.py` (pdfplumber, pdfminer.six) |
| DS.4 | skill/experience/education/category 추출 | ✅ | ingestion + enricher, `ingestion/preprocessing.py` |
| DS.5 | 추출 필드 → retrieval/filtering/scoring 활용 | ✅ | `hybrid_retriever`, `scoring_service`, `filter_options` |

---

## 2. Problem Definition (problem_definition.md)

### 2.1 문제 진술 (PO.*) — 대응 요건으로 충족

| ID | 문제 진술 | 대응 요구사항 | 상태 |
|----|-----------|----------------|:----:|
| PO.1 | 기술 적합성·숙련도·경력 맥락 평가 어려움 | R1.2, R1.5, MSA.2, MSA.3, HCR.1 | ✅ |
| PO.2 | 메타데이터 미해석 시 품질 저하 | R1.4, R1.8, HCR.2, DS.4, DS.5 | ✅ |
| PO.3 | exact match만으로 transferable skill 누락 | R1.2, HCR.1, R2.3 | ✅ |
| PO.4 | CSV/PDF/비정형 포맷 파싱 품질 편차 | R1.7, DS.3, DS.4 | ✅ |
| PO.5 | 점수만으로는 신뢰 부족, 설명 가능 근거 필요 | AHI.1, R2.4, MSA.6 | ✅ |
| PO.6 | 대규모 후보 수동 검토 비효율 | R1.1, HCR.*, MSA.*, R2.6 | ✅ |

### 2.2 목표 (OBJ.*) — 대응 요건으로 충족

| ID | 목표 | 대응 요구사항 | 상태 |
|----|------|----------------|:----:|
| OBJ.1 | JD → 구조화 query profile, 검색 신호 안정화 | R1.6, R1.9 (query understanding) | ✅ |
| OBJ.2 | retrieval relevant recall 우선 | R1.1, HCR.1, HCR.2, HCR.3 | ✅ |
| OBJ.3 | skill/experience/technical/culture 평가 + 가중치 | MSA.1–MSA.6, AHI.5 | ✅ |
| OBJ.4 | score breakdown, evidence, gap explainability | AHI.1, R2.4 | ✅ |
| OBJ.5 | 품질/성능/신뢰성/공정성 지표 재현 가능 축적 | R2.1, R2.2, R2.4, R2.6, R2.7, D.2 | ✅ |

### 2.3 Non-Goals

- ingestion에서 생성형 LLM 파싱을 기본 경로로 사용하지 않음 → 규칙/spaCy 기반 파싱 (ADR-007 등) ✅  
- fine-tuned embedding 학습/운영 파이프라인은 후속 고도화 → 현재 범위 밖 ✅  
- full ATS 대체 제품 범위는 현재 범위 밖 ✅  

---

## 3. Case-Study PDF 핵심 요건 대응

| Case-Study 요건 | 대응 FR/구현 | 상태 |
|-----------------|----------------|:----:|
| Semantic Job Requirement Understanding | R1.6, job profile extractor, query understanding | ✅ |
| Intelligent Candidate Matching | R1.1–R1.5, HCR.*, MSA.* | ✅ |
| Context-Aware Skill Evaluation | R1.2, MSA.2, scoring_service | ✅ |
| Career Progression Analysis | MSA.3 (Experience Agent) | ✅ |
| Transferable Skill Identification | R1.2, HCR.1, skill expansion/ontology | ✅ |
| Structured Candidate Insights | match_result_builder, explainability | ✅ |
| Explainable Matching Scores | AHI.1 | ✅ |
| Requirement 1 (Basic) 전체 | R1.1–R1.9 | ✅ |
| Requirement 2 (Advanced) 전체 | R2.1–R2.8 | ✅ |
| Hybrid Candidate Retrieval | HCR.1–HCR.3 | ✅ |
| Multi-Stage Hiring Agent Pipeline | MSA.1–MSA.6 (Resume Parsing은 ingestion으로) | ✅ |
| Additional Hiring Intelligence | AHI.1–AHI.5 | ✅ |
| Deliverables (Architecture, Design, Code, Panel) | D.1–D.4 | ✅ |
| Dataset (snehaanbhawal, suriyaganesh, CSV/JSON/PDF, key fields) | DS.1–DS.5 | ✅ |

---

## 4. Reviewer Checklist (Reviewer_Checklist.md)

### 4.1 Filesystem & Documentation

| 항목 | 충족 | 증거 |
|------|:----:|------|
| 명확한 폴더 구조 (requirements, docs/architecture, docs/data-flow, src, tests) | ✅ | `/requirements`, `/docs/architecture`, `/docs/data-flow`, `/src`, `/tests` 존재 |
| README 설치·평가 가이드, 코드와 구조 일치 | ✅ | README: Quick Start, Core Commands, Repository Structure, Documentation Entry Points |
| Stakeholder PPT / 브리핑 덱 | ✅ | 별도 .pptx 없음. **스토리 제안:** 패널 데모 시 `Key Design Decisions.md` + `docs/evaluation/evaluation_results.md` + `docs/adr/`를 한데 참고해 8분 설계·결과 요약; 필요 시 `docs/presentation_summary.md`로 "발표용 한 문서"를 두어 10분 데모 시 사용. 실제 .pptx는 별도 산출물로 관리 가능. |

### 4.2 Architecture & Design Integrity

| 항목 | 충족 | 증거 |
|------|:----:|------|
| Architecture vs Data Flow 구분 | ✅ | `system_architecture.md` vs `data-flow/resume_ingestion_flow.md`, `candidate_retrieval_flow.md` |
| Production scale (API GW, LB, K8s) 고려 | ✅ | `deployment_architecture.md` — POC vs Production, API Gateway/LB/K8s 역할 문서화 |
| POC vs Production 범위 정의 | ✅ | `deployment_architecture.md` § POC vs Production, `problem_definition.md` Non-Goals |
| 관측성·MLOps | ✅ | `docs/observability/monitoring.md`, `logging_metrics.md`, ADR-009, 헬스/레디 엔드포인트 |
| ADR (디자인 결정) | ✅ | `docs/adr/` — ADR-001 ~ ADR-009 |
| 결합도 분리 (Vector DB 등 교체 가능) | ✅ | `deployment_architecture.md`, ADR-001, repository 추상화 |

### 4.3 Implementation & Code Quality

| 항목 | 충족 | 증거 |
|------|:----:|------|
| Zero print / 100% 구조화 로깅 | ✅ | `ops/logging.py` (structlog, JSONRenderer); print 1건만 `mongo_handler.py` emit 예외 시 stderr (로거 재귀 방지) |
| 보안·클린 코드 (Secret 없음, 모듈화) | ✅ | `core/settings.py` (Pydantic Settings, .env); 서비스·에이전트 모듈 분리 |
| 커넥션 풀링 | ✅ | Mongo: `database.py` (maxPoolSize, minPoolSize); Milvus: `vector_store.py` (`_initialize_connection_pool`) |
| 입출력 검증 (Pydantic) | ✅ | `schemas/job.py`, `candidate.py`, `feedback.py`, `ingestion.py`, FastAPI `response_model` |
| 컨테이너화 | ✅ | `docker-compose.yml`, `src/backend/Dockerfile`, `src/frontend/Dockerfile`, README와 일치 |
| 리소스 관리 (Generator/Streaming) | ✅ | `ingest_resumes.py` (chunksize, iter_sneha/iter_suri yield); `matching_service.py` SSE; `api/jobs.py` StreamingResponse |
| Cold Start 최적화 | ✅ | `core/startup.py` `warmup_infrastructure()`, lifespan, `/api/health`, `/api/ready` |

### 4.4 Testing & Validation

| 항목 | 충족 | 증거 |
|------|:----:|------|
| 자동화된 테스트 (로딩·검색) | ✅ | `tests/test_api.py`, `tests/test_retrieval.py`, `test_ingestion_preprocessing.py` 등 |
| 성능 측정 (Latency p99, Throughput) | ✅ | `eval_runner.py`, `reporting.py`, `evaluation_results.md`, `run_eval.sh` |
| 정확도 평가 (LLM-as-Judge, IR) | ✅ | `eval/metrics.py`, NDCG/MAP/recall, `llm_judge_annotations.jsonl`, `test_match_quality.py` |
| Ground Truth 문서화 | ✅ | `golden_set.jsonl`, `evaluation_plan.md`, `golden_set_alignment.md` |
| 복구 탄력성 (Fallback) | ✅ | sdk_handoff → live_json → heuristic 체인; Mongo/Milvus fallback (keyword_only); query_fallback (TRACEABILITY §7: 로컬 SLM은 Non-Goal) |

### 4.5 Reviewer's Verdict (SME 'Yes' 기준)

| 판정 항목 | 충족 | 비고 |
|-----------|:----:|------|
| 정확성 | ✅ | R1.6, R1.7, R2.1, R2.4, 에지 케이스 처리 |
| 아키텍처 | ✅ | D.1, system_architecture, 레이어 분리 |
| 디자인 결정 | ✅ | D.2, ADR, design_tradeoffs |
| 성능 | ✅ | R2.6, HCR.*, R2.5, evaluation_results |
| 확장성 | ✅ | stateless API, 풀링, deployment 문서 |
| 신뢰성 | ✅ | 재시도·fallback 정책 (서킷 브레이커는 Phase 2 권장) |
| 유지보수성 | ✅ | D.3, 코드 구조, Docker |
| 관측성 | ✅ | 구조화 로그, 헬스/레디, monitoring 문서 |

---

## 5. 용어·보완 설명

### live_json

에이전트 런타임에서 **단일 LLM 호출로 JSON 스키마 응답을 받는 경로**를 가리킵니다.

- **SDK 경로** (`sdk_runner.py`): OpenAI Agents SDK 기반 멀티스텝 에이전트 실행.
- **live_json 경로** (`live_runner.py`): SDK 없이, 한 번의 LLM 호출에 구조화된 JSON 스키마(`LIVE_OUTPUT_SCHEMA`)를 요청해 skill/experience/technical/culture/weight_negotiation 결과를 한꺼번에 받는 경로. "live" = 실시간 단일 호출, "json" = 응답이 JSON 객체.
- **heuristic 경로** (`heuristics.py`): LLM 호출 실패·비활성 시 사용하는 결정론적 fallback.

Fallback 순서는 **sdk_handoff → live_json → heuristic**이며, `runtime_mode` / `runtime_reason`으로 어떤 경로가 사용됐는지 응답에 포함됩니다. 참고: `src/backend/agents/runtime/README.md`, `live_runner.py`.

---

## 6. 요약

- **전체적으로 요건 충족.** TRACEABILITY.md 및 traceability_matrix.md와 정합됨.
- **R2.3:** rerank 테스트·평가는 있음(`run_rerank_eval.sh`, eval_runner rerank 모드, golden.rerank.jsonl); fine-tuned embedding 실험·rollback runbook은 선택적 고도화.
- **R2.5:** Token 관측은 LangSmith 트레이싱으로 제공; 설정 기반 budget·캐시로 최적화.
- **R2.6:** Throughput/latency benchmark 제공; 고부하는 확장성 설계(K8s/LB/stateless)로 대응.
- **AHI.2–AHI.4:** API·서비스 구현으로 요건 충족; 자동 재학습 파이프라인·전용 대시보드·handoff 표준은 필요 시 확장.
- **의도적 예외/방어:** Zero print(1건 예외), Stakeholder PPT(문서·발표용 요약으로 대체), 로컬 SLM Fallback(Non-Goal), 서킷 브레이커(Phase 2 권장) — [TRACEABILITY.md §7 방어 논리](./TRACEABILITY.md) 참고.

이 문서는 요건 문서와 코드를 대조한 검증 결과이며, 상세 증거 경로는 TRACEABILITY.md 및 requirements/traceability_matrix.md를 참고하면 됩니다.
