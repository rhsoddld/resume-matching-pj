# Code Structure & Extensibility Guide

이 문서는 프로젝트의 폴더 구조를 설명하고, 새 기능을 추가하거나 컴포넌트를 교체할 때 참고할 수 있는 확장 가이드를 제공합니다.

## Folder Structure

### Root Directory

- **`README.md`**: 프로젝트 소개, Quick Start, Core Commands, 문서 진입점
- **`requirements.txt`**: Python 의존성 (FastAPI, PyMongo, PyMilvus, OpenAI, spaCy, DeepEval 등)
- **`docker-compose.yml`**: 로컬 실행용 서비스 (backend, frontend, MongoDB, Milvus 등)
- **`pytest.ini`**: pytest 설정
- **`config/`**: 스킬 택소노미, 별칭, 직무 필터 등 YAML 설정
- **`docs/`**: 아키텍처, ADR, 데이터 플로우, 평가, 관측성 문서
- **`src/`**: 백엔드, 프론트엔드, 평가 모듈 소스
- **`scripts/`**: ingestion, eval, golden set 유지보수 스크립트
- **`tests/`**: 단위/통합 테스트
- **`ops/`**: 로깅, 미들웨어 등 공통 운영 코드 (backend와 분리된 패키지)

### `config/` Directory

- **`skill_taxonomy.yml`**: 스킬 계층 및 직군 매핑
- **`skill_aliases.yml`**: 스킬 별칭 정규화
- **`skill_capability_phrases.yml`**: 역량 문구 매핑
- **`skill_review_required.yml`**, **`versioned_skills.yml`**, **`skill_role_candidates.yml`**: 스킬/역할 보조 데이터
- **`job_filters.yml`**: 직군/학력/지역/산업 등 필터 옵션 소스

### `src/` Directory

- **`backend/`**: FastAPI 앱, API 라우터, 서비스, 에이전트, 저장소, 스키마
- **`frontend/`**: React(Vite) + TypeScript 웹 UI
- **`eval/`**: 평가 러너, golden set, LLM-as-Judge, 서브셋 생성 등

### `src/backend/` Directory

| 경로 | 설명 |
|------|------|
| **`main.py`** | FastAPI 앱 진입점, lifespan, 미들웨어, `/api/health`, `/api/ready`, 라우터 등록 |
| **`api/`** | REST 라우터: `candidates`, `jobs`, `ingestion`, `feedback` |
| **`core/`** | 설정(`settings`), DB(`database`), 벡터 스토어(`vector_store`), 예외, startup, observability, filter_options, model_routing, jd_guardrails, providers |
| **`schemas/`** | Pydantic 모델: `job.py` (JobMatchRequest, JobMatchResponse, QueryUnderstandingProfile 등), `candidate.py`, `ingestion.py`, `feedback.py` |
| **`repositories/`** | `mongo_repo.py` (후보 조회, 필터 옵션 API 진입점), `hybrid_retriever.py` (재export; 실제 구현은 `services/hybrid_retriever.py`), `session_repo.py` (JD 세션) |
| **`services/`** | 핵심 서비스: `matching_service.py` (매칭 오케스트레이션), `hybrid_retriever.py`, `retrieval_service.py`, `job_profile_extractor.py`, `match_result_builder.py`, `scoring_service.py`, `cross_encoder_rerank_service.py`, `query_fallback_service.py`, `candidate_enricher.py`, `ingest_resumes.py`, `resume_parsing.py`, `email_draft_service.py` 등 |
| **`services/job_profile/`** | 시그널 품질, 시그널 중복 제거 등 JD 프로필 보조 로직 |
| **`services/skill_ontology/`** | 스킬 온톨로지 로더, 정규화, 런타임 타입/상수 |
| **`services/ingestion/`** | 이력서 수집 파이프라인: 전처리, 변환, 상태, 상수 |
| **`services/matching/`** | 캐시, fairness, evaluation, profile 병합, rerank_policy |
| **`services/retrieval/`** | `hybrid_scoring.py` (fusion, keyword, metadata 점수) |
| **`agents/`** | Multi-agent 파이프라인 |
| **`agents/contracts/`** | 에이전트 계약: skill_agent, experience_agent, technical_agent, culture_agent, orchestrator, ranking_agent, weight_negotiation_agent |
| **`agents/runtime/`** | `service.py` (오케스트레이션 진입), `sdk_runner.py`, `live_runner.py`, `heuristics.py`, candidate_mapper, helpers, prompts, models, types |

### `src/frontend/` Directory

- **`src/App.tsx`**, **`main.tsx`**, **`index.html`**: 앱 진입점
- **`src/api/`**: `match.ts`, `feedback.ts` — 백엔드 API 호출
- **`src/components/`**: `JobRequirementForm.tsx`, `MatchForm.tsx`, `CandidateResults.tsx`, `CandidateRow.tsx`, `CandidateCard.tsx`, `CandidateDetailModal.tsx`, `MatchScorePill.tsx`, `ExplainabilityPanel.tsx`, `RecruiterHero.tsx`, `BiasGuardrailBanner.tsx`, `ResultCard.tsx`
- **`src/types.ts`**: 공통 타입
- **`src/utils/agentEvaluation.ts`**: 에이전트 평가 유틸
- **`theme.css`**, **`index.css`**: 스타일
- **`vite.config.ts`**, **`package.json`**, **`Dockerfile`**, **`nginx.conf`**: 빌드/배포

### `src/eval/` Directory

- **`eval_runner.py`**, **`config.py`**: 평가 실행 및 설정
- **`golden_set_maintenance.py`**, **`create_mode_subsets.py`**: golden set 유지보수
- **`generate_llm_judge_annotations.py`**: LLM-as-Judge 어노테이션 생성
- **`subsets/`**: golden set 서브셋 (예: `golden.agent.jsonl`)
- **`outputs/`**: 평가 결과 아카이브

### `docs/` Directory

- **`architecture/`**: system_architecture.md, deployment_architecture.md
- **`adr/`**: ADR-001 ~ ADR-004 (vector-db, embedding, hybrid-retrieval, agent-orchestration)
- **`data-flow/`**: resume_ingestion_flow.md, candidate_retrieval_flow.md
- **`agents/`**: multi_agent_pipeline.md
- **`evaluation/`**: evaluation_plan.md, evaluation_results.md, llm_judge_design.md, golden_set_alignment.md 등
- **`observability/`**: logging_metrics.md, monitoring.md
- **`governance/`**: cost_control.md
- **`Key Design Decisions.md`**: 핵심 설계 결정 요약 (본 문서와 쌍으로 참고)
- **`CODE_STRUCTURE.md`**: 본 문서

### `scripts/` Directory

- **`ingest_resumes.py`**: 이력서 수집 (source: all 등, target: mongo / milvus)
- **`run_eval.sh`**, **`run_retrieval_eval.sh`**, **`run_rerank_eval.sh`**: 평가 실행
- **`update_golden_set.sh`**, **`regen_golden_set.sh`**: golden set 갱신

### `tests/` Directory

- **`test_api.py`**, **`test_retrieval.py`**, **`test_scoring_service.py`**, **`test_hybrid_scoring.py`**, **`test_ingestion_preprocessing.py`**, **`test_golden_set_alignment.py`**, **`test_regen_golden_set.py`**, **`test_job_profile_extractor.py`**, **`test_sdk_runner_and_rerank_policy.py`**, **`test_resume_parsing.py`**, **`test_matching_evaluation.py`** 등

### `ops/` Directory (공통 운영)

- **`logging.py`**: configure_logging, get_logger
- **`middleware.py`**: RequestIdMiddleware, APILoggingMiddleware
- **`mongo_handler.py`**: (선택) MongoDB 로그 핸들러

---

## Extensibility

코드베이스는 모듈화와 확장을 고려해 구성되어 있어, 새 기능 추가나 컴포넌트 교체가 비교적 수월합니다.

### 1. Embedding 모델 변경

- **위치**: `backend.core.settings` (`openai_embedding_model`), `backend.services.retrieval_service.RetrievalService` (OpenAI Embeddings API 호출)
- **방법**:
  1. `.env`에서 `OPENAI_EMBEDDING_MODEL` 변경하거나, 다른 embedding provider용 서비스 클래스를 구현
  2. 벡터 차원이 바뀌면 Milvus collection의 `dim` 및 재인덱싱 필요
  3. Rerank embedding 모델은 `rerank_embedding_model` 설정으로 별도 지정 가능

### 2. Vector DB / Document Store 교체

- **Vector**: `backend.core.vector_store`에서 Milvus 호출 래핑. 다른 벡터 DB로 교체 시 동일 인터페이스(search_embeddings 등)를 구현하고 `retrieval_service` / `hybrid_retriever`가 이를 사용하도록 연결
- **Document**: `backend.repositories.mongo_repo`에서 MongoDB 조회. 다른 저장소로 바꿀 경우 동일 함수 시그니처로 새 저장소 구현 후 호출부만 교체

### 3. Query Understanding 확장 (Deterministic)

- **위치**: `backend.services.job_profile_extractor` (JD → JobProfile), `backend.core.filter_options` (필터 옵션 로딩), `config/*.yml`
- **방법**:
  1. 새 시그널 타입이나 규칙을 추가하려면 `job_profile_extractor`와 `job_profile/signals` 확장
  2. 필터 옵션 추가는 `config/job_filters.yml` 수정. API는 `repositories.mongo_repo.get_filter_options()`를 호출하며, 실제 데이터는 `core.filter_options`에서 YAML(job_filters.yml + skill_taxonomy.yml 병합) 로드
  3. Query fallback은 `query_fallback_service`에서 confidence/unknown_ratio 기준으로 이미 연동됨 — 임계값 조정으로 동작 변경 가능

### 4. Hybrid Retrieval / Fusion 조정

- **위치**: `backend.services.hybrid_retriever.HybridRetriever`, `backend.services.retrieval.hybrid_scoring`
- **방법**:
  1. Fusion 가중치, 키워드/메타데이터 점수 공식은 `hybrid_scoring`에서 변경
  2. 키워드 후보 풀 생성 로직은 `HybridRetriever._search_keyword_candidates`, `_merge_fusion_hits` 등에서 조정
  3. 산업/카테고리 매핑은 `hybrid_scoring.INDUSTRY_CATEGORY_MAP` 및 설정 연동

### 5. Rerank 정책 / 모델 변경

- **위치**: `backend.services.matching.rerank_policy` (게이트 조건, top_n, 모델 라우팅), `backend.services.cross_encoder_rerank_service`, `backend.core.model_routing`
- **방법**:
  1. Rerank 사용 여부: `RERANK_ENABLED`, `should_apply_rerank` 조건 수정
  2. 게이트 조건: `rerank_gate_*` 설정 및 `rerank_policy` 내 조건 변경
  3. LLM rerank vs embedding rerank: `rerank_mode`, 해당 서비스 구현체 교체 또는 라우팅 확장

### 6. Multi-Agent 평가 / 협상 체인 확장

- **위치**: `backend.agents.contracts` (에이전트 클래스), `backend.agents.runtime.service`, `sdk_runner`, `live_runner`, `heuristics`
- **방법**:
  1. 새 에이전트 추가: contracts에 새 에이전트 클래스 구현 후, 오케스트레이션 서비스에서 호출 및 Score Pack 병합
  2. 가중치 협상 로직 변경: `weight_negotiation_agent` 및 Recruiter/HiringManager 제안 포맷 수정
  3. Fallback 순서 변경: SDK → live_json → heuristic 체인을 runtime에서 조정

### 7. Fairness / Bias 정책 변경

- **위치**: `backend.services.matching.fairness`, `backend.core.jd_guardrails`
- **방법**: `fairness_*` 설정과 fairness 모듈 내 검사 규칙 추가/수정; 프론트는 `BiasGuardrailBanner`로 경고만 노출하므로 백엔드 응답 스키마만 맞추면 됨

### 8. 새 API 엔드포인트 추가

- **위치**: `backend.api` (새 라우터 또는 기존 `candidates`, `jobs`, `ingestion`, `feedback`에 추가)
- **방법**: FastAPI 라우터에 새 경로 정의 후 `main.py`에서 `app.include_router`로 등록

### 9. 프론트엔드 컴포넌트 / 페이지 추가

- **위치**: `src/frontend/src/components/`, `src/api/`
- **방법**: 새 컴포넌트 작성 후 `App.tsx` 또는 기존 페이지에 연결; API 호출은 `api/`에 함수 추가

### 10. 평가 파이프라인 확장

- **위치**: `src/eval/` (eval_runner, golden set, LLM judge 스크립트)
- **방법**: 새 메트릭이나 judge 기준을 추가하려면 eval_runner 및 관련 스크립트에 단계 추가; golden set 포맷은 기존 JSONL과 호환 유지

---

## 문서 진입점 (README와의 연결)

- 아키텍처: [docs/architecture/system_architecture.md](./architecture/system_architecture.md)
- 설계 결정 요약: [docs/Key Design Decisions.md](./Key%20Design%20Decisions.md)
- 코드 구조 및 확장: **docs/CODE_STRUCTURE.md** (본 문서)
- 배포: [docs/architecture/deployment_architecture.md](./architecture/deployment_architecture.md)
- 데이터 플로우: [docs/data-flow/resume_ingestion_flow.md](./data-flow/resume_ingestion_flow.md), [docs/data-flow/candidate_retrieval_flow.md](./data-flow/candidate_retrieval_flow.md)
- 에이전트: [docs/agents/multi_agent_pipeline.md](./agents/multi_agent_pipeline.md)
- 평가: [docs/evaluation/evaluation_plan.md](./evaluation/evaluation_plan.md), [docs/evaluation/evaluation_results.md](./evaluation/evaluation_results.md)
