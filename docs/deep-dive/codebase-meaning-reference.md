# 전체 코드 의미 상세 가이드

**목적:** 저장소의 각 디렉터리·파일이 **무엇을 의미하는지**, 비즈니스·기술 관점에서 한눈에 이해할 수 있도록 상세히 정리합니다.  
흐름·시퀀스는 [코드 구조 및 핵심 흐름 가이드](../guides/codebase-core-flows.md), [스코어링 전체 흐름 가이드](../guides/scoring-flow-guide.md)를 참고하세요.

---

## 1. 프로젝트가 의미하는 것 (한 문장)

**"JD(채용 공고)를 넣으면, 이력서 DB에서 의미 기반으로 후보를 검색하고, 에이전트가 스킬/경력/기술/문화 적합도를 평가한 뒤, 설명 가능한 순위와 점수를 내주는 시스템"**입니다.

- **오프라인:** 이력서 CSV/텍스트를 파싱·정규화해 MongoDB(프로필) + Milvus(임베딩)에 적재
- **온라인:** JD → 구조화 쿼리(Query Understanding) → 하이브리드 검색(벡터+키워드+메타) → rerank(선택) → 에이전트 평가 → 가중치 협상 → 최종 점수·설명·fairness 경고

---

## 2. 루트 디렉터리 — 각 파일/폴더가 의미하는 것

| 경로 | 의미 |
|------|------|
| **README.md** | 프로젝트 소개, 설치·실행·핵심 명령, 문서 진입점. 처음 보는 사람용 요약. |
| **requirements.txt** | Python 런타임 의존성. FastAPI, PyMongo, PyMilvus, OpenAI, spaCy, DeepEval 등. |
| **docker-compose.yml** | 로컬에서 backend, frontend, MongoDB, Milvus, Attu를 한 번에 띄우기 위한 정의. |
| **pytest.ini** | pytest 설정(마커, 경로 등). 테스트 실행 시 사용. |
| **.env.example** | 환경 변수 템플릿. `.env`는 이걸 복사해 실제 키·URI를 넣음(저장소에 올리지 않음). |
| **config/** | **설정 데이터.** 스킬 택소노미, 별칭, 직무 필터 등. Query Understanding·검색의 입력이 됨. |
| **docs/** | 아키텍처, ADR, 데이터 플로우, 에이전트, 평가, 거버넌스 등 **모든 문서**. |
| **src/** | **실제 소스.** backend(FastAPI), frontend(React), eval(평가 러너). |
| **scripts/** | **CLI/배치 스크립트.** 이력서 수집(ingest), 평가 실행(run_eval 등), golden set 유지보수. |
| **tests/** | **단위·통합 테스트.** API, retrieval, scoring, ingestion, golden set 등. |
| **ops/** | **공통 운영 코드.** 로깅, 미들웨어, (선택) MongoDB 로그 핸들러. backend와 분리된 패키지. |
| **requirements/** | 문제 정의, 기능 요구사항, 추적 행렬 등 요구사항 산출물. |

---

## 3. config/ — 각 설정 파일이 의미하는 것

모두 **YAML**이며, **LLM 없이** Query Understanding·검색에서 사용하는 **결정론(deterministic) 데이터**입니다.

| 파일 | 의미 |
|------|------|
| **skill_taxonomy.yml** | 스킬 계층·직군 매핑. 어떤 스킬이 어떤 직군/역할에 속하는지 정의. JD 해석 시 역할·스킬 추출에 사용. |
| **skill_aliases.yml** | 스킬 별칭 → 정규화된 스킬명 매핑. "Python3" → "python" 등 검색·매칭 일관성 확보. |
| **skill_capability_phrases.yml** | 역량 문구와 스킬 매핑. "시스템 통합 경험" 같은 문구를 어떤 스킬 시그널로 볼지. |
| **skill_review_required.yml**, **versioned_skills.yml**, **skill_role_candidates.yml** | 스킬/역할 보조 데이터. 검토 필요 스킬, 버전 관리, 역할 후보 등. |
| **job_filters.yml** | 직군(category), 학력(education), 지역(region), 산업(industry) 등 **필터 옵션** 소스. API에서 필터 목록을 줄 때 사용. |

---

## 4. src/backend/ — 백엔드 코드가 의미하는 것

### 4.1 진입점: main.py

- **의미:** FastAPI 앱의 **유일한 진입점**.
- **하는 일:** 앱 생성, lifespan(기동 시 `warmup_infrastructure`), 미들웨어(CORS, RequestId, API 로깅), 예외 핸들러(`AppError`·일반 예외), `/api/health`·`/api/ready`(Mongo·Milvus 연결 확인), 그리고 `candidates`·`jobs`·`ingestion`·`feedback` 라우터 등록.

### 4.2 api/ — REST 엔드포인트가 의미하는 것

| 파일 | 의미 |
|------|------|
| **jobs.py** | **매칭·JD 관련 API.** `POST /api/jobs/match`(매칭), match/stream, extract-pdf, draft-email 등. 사용자 요청이 여기서 들어옴. |
| **candidates.py** | 후보 목록 조회, 필터 옵션(category/education/region/industry) 조회. |
| **ingestion.py** | `POST /api/ingestion/resumes` — 이력서 배치 적재 API(CLI와 별도로 HTTP로 넣을 때). |
| **feedback.py** | 매칭 결과에 대한 피드백 수집 API. |

### 4.3 core/ — 인프라·설정·공통이 의미하는 것

| 파일 | 의미 |
|------|------|
| **settings.py** | 환경 변수 기반 **전역 설정**. DB URI, Milvus URI, 캐시 TTL, rerank/agent 관련 플래그·한도 등. |
| **database.py** | **MongoDB 연결** 획득. 싱글톤 클라이언트. |
| **vector_store.py** | **Milvus 래핑.** 연결, 컬렉션 존재 확인, 임베딩 검색 등. 벡터 DB를 바꿀 때 이 인터페이스만 맞추면 됨. |
| **filter_options.py** | `job_filters.yml` + `skill_taxonomy.yml` 병합해 **필터 옵션** 로드. API·Query Understanding에서 사용. |
| **jd_guardrails.py** | JD 텍스트 **보안·정제.** 민감 정보·과도한 길이 등 검사. |
| **model_routing.py** | **Rerank 모델 라우팅.** 기본/고품질(ambiguity·tie-break) 등 조건별로 어떤 모델 쓸지 결정. |
| **observability.py** | 트레이싱·span. `traceable_op` 데코레이터 등. |
| **exceptions.py** | `AppError` 등 **앱 공통 예외** 정의. |
| **startup.py** | 기동 시 **인프라 워밍업**(DB, Milvus, 스킬 온톨로지 등). |
| **collections.py** | 리스트 중복 제거 등 **공통 컬렉션 유틸**. |
| **providers.py** | 스킬 온톨로지 등 **런타임 프로바이더** 주입. |

### 4.4 schemas/ — 요청·응답·도메인 모델이 의미하는 것

| 파일 | 의미 |
|------|------|
| **job.py** | **매칭 요청/응답·Query 이해 결과.** `JobMatchRequest`, `JobMatchResponse`, `QueryUnderstandingProfile`, `JobMatchCandidate`, `FairnessAudit` 등. API 계약과 내부 전달 구조. |
| **candidate.py** | 후보 스키마. API·저장소 간 후보 표현. |
| **ingestion.py** | ingestion API 요청/응답 스키마. |
| **feedback.py** | 피드백 API 스키마. |

### 4.5 repositories/ — 저장소 계층이 의미하는 것

| 파일 | 의미 |
|------|------|
| **mongo_repo.py** | **MongoDB 접근.** 후보 ID로 조회, 필터 옵션 조회(`get_filter_options`). 실제 쿼리는 여기서 수행. |
| **hybrid_retriever.py** | `services/hybrid_retriever`를 **재export.** 라우터·서비스는 이 경로로 HybridRetriever를 씀. |
| **session_repo.py** | JD 세션 저장/조회. 매칭 세션 상태 유지용. |

### 4.6 services/ — 비즈니스 로직이 의미하는 것 (핵심)

| 파일 | 의미 |
|------|------|
| **matching_service.py** | **매칭 파이프라인 오케스트레이션.** 캐시 → JobProfile 빌드 → 검색 → Enrichment → Shortlist → 스코어·에이전트 → Fairness → 응답. 전체 흐름의 **진입점**. |
| **job_profile_extractor.py** | **JD → 구조화 쿼리(JobProfile).** 규칙+택소노미 기반(deterministic). 역할, 필수/관련 스킬, 시니어리티, lexical_query, query_text_for_embedding, filters, confidence 등 출력. LLM 없이 비용·일관성 확보. |
| **hybrid_retriever.py** | **하이브리드 검색.** 키워드(항상, Mongo) + 벡터(가능 시, Milvus) + 메타데이터 점수를 fusion해 후보 리스트 반환. 벡터 실패 시 키워드만 사용하는 fallback 포함. |
| **retrieval_service.py** | **임베딩 생성 + Milvus 검색.** JD 텍스트를 embed하고 벡터 DB에서 유사도 검색. |
| **candidate_enricher.py** | **hit → Mongo 문서 보강.** 검색 hit에 전체 후보 문서를 붙이고, 경력연차/학력/지역/산업 등 **메타 필터** 적용해 조건 미충족 후보 제외. |
| **cross_encoder_rerank_service.py** | **Rerank 서비스.** Shortlist 후보에 대해 Cross-Encoder(또는 설정에 따라 LLM) rerank. 게이트 통과 시에만 호출됨. |
| **scoring_service.py** | **최종 점수 계산.** deterministic 점수(스킬 겹침, 경력 적합도, 시니어리티, category 등), 에이전트 가중 점수와의 blend, must_have_penalty 적용. 스코어링 공식의 **핵심 구현**. |
| **match_result_builder.py** | **응답 DTO 조립.** 한 후보에 대해 `JobMatchCandidate`(점수, 설명, evidence, bias_warnings 등) 생성. |
| **query_fallback_service.py** | **Query Understanding fallback.** confidence/unknown_ratio가 나쁠 때 대체 쿼리·전략 사용. |
| **ingest_resumes.py** | **이력서 수집 오케스트레이션.** CSV 소스 로드 → 파싱·정규화 → Mongo/Milvus 적재. `scripts/ingest_resumes.py`가 이 모듈을 호출. |
| **resume_parsing.py** | **이력서 파싱.** 규칙/regex, spaCy, dateparser 등으로 텍스트에서 스킬·경력·학력 추출. |
| **email_draft_service.py** | 이메일 초안 생성 등 **채용 연락용** 서비스. |
| **eval_adapter.py** | 평가 러너(eval)가 백엔드 매칭 로직을 호출할 때 쓰는 **어댑터**. |

#### services 하위 패키지

| 경로 | 의미 |
|------|------|
| **job_profile/** | JobProfile **시그널 품질·중복 제거.** `signals.py`에서 시그널 품질 계산, 시그널 디듀프. |
| **skill_ontology/** | **스킬 온톨로지** 로더, 정규화, 런타임 타입/상수. config YAML을 읽어 스킬 계층·별칭 제공. |
| **ingestion/** | 이력서 **전처리, 변환, 상태, 상수.** 파이프라인 내 전처리 단계·상태 머신·매핑 상수. |
| **matching/** | **캐시**(LRU+TTL), **fairness**(편향 경고), **evaluation**(에이전트 평가 대상 인덱스 선택), **profile 병합**, **rerank_policy**(게이트, top_n, 풀 크기 등). |
| **retrieval/** | **hybrid_scoring.** vector/keyword/metadata 점수 fusion 공식(가중치 0.48/0.37/0.15 등). |

### 4.7 agents/ — 에이전트가 의미하는 것

- **의미:** JD·후보 쌍에 대해 **스킬/경력/기술/문화** 4개 관점으로 평가하고, **Recruiter vs Hiring Manager** 가중치를 **협상**해 최종 가중 점수와 설명을 만드는 **Multi-Agent 파이프라인**.

#### agents/contracts/ — 에이전트 “계약”(입출력 정의)

| 파일 | 의미 |
|------|------|
| **skill_agent.py** | **스킬 매칭 에이전트.** JD 필수 스킬 vs 후보 스킬 정렬. skill_fit_score, matched/missing_skills, evidence. |
| **experience_agent.py** | **경력 평가 에이전트.** 요구 연차·시니어리티 vs 후보 경력. experience_fit_score, career_trajectory 등. |
| **technical_agent.py** | **기술 깊이·엔지니어링 경험** 평가. 스택 커버리지, 벡터 유사도 활용. |
| **culture_agent.py** | **문화 적합성·도메인 정렬.** category/역할 일치, 협업 시그널 등. |
| **orchestrator.py** | 4개 에이전트 **오케스트레이션** 계약(입출력 정의). |
| **ranking_agent.py** | **가중 점수 + 설명** 생성. Evaluation Score Pack을 가중치로 합쳐 rank_score·설명. |
| **weight_negotiation_agent.py** | **Recruiter / Hiring Manager** 제안을 받아 **최종 가중치** 합의. |

#### agents/runtime/ — 실제 실행

| 파일 | 의미 |
|------|------|
| **service.py** | **AgentOrchestrationService.** 에이전트 파이프라인 **진입점.** `run_for_candidate()`에서 후보 1명당 4개 에이전트 실행 후 Recruiter→HiringManager→WeightNegotiation 체인. |
| **sdk_runner.py** | **SDK handoff** 실행. Recruiter→HiringManager→Negotiation을 SDK 호출로 수행. 1순위 경로. |
| **live_runner.py** | **Live JSON** fallback. SDK 실패 시 LLM을 직접 호출해 JSON 응답 받는 경로. |
| **heuristics.py** | **규칙 기반 fallback.** SDK·Live 모두 실패 시 스킬/경력/기술/문화 점수를 공식으로 계산. |
| **candidate_mapper.py** | 에이전트에 넘길 **후보 입력 번들** 생성(JD·JobProfile·hit·문서 조합). |
| **helpers.py** | `compute_skill_score`, `compute_experience_fit`, `compute_seniority_fit`, `compute_weighted_score` 등 **점수 계산 유틸**. |
| **prompts.py** | 에이전트·협상용 **프롬프트** 버전·내용. |
| **models.py**, **types.py** | 에이전트 입출력 **타입·모델** 정의. |

---

## 5. src/frontend/ — 프론트엔드가 의미하는 것

- **의미:** **React(Vite) + TypeScript** 웹 UI. JD 입력, 필터 선택, 매칭 요청, 결과·점수·설명·fairness 경고 표시.

| 경로/파일 | 의미 |
|-----------|------|
| **src/App.tsx**, **main.tsx**, **index.html** | 앱 **진입점**·라우팅. |
| **src/api/** | **match.ts**, **feedback.ts** — 백엔드 매칭·피드백 API 호출. |
| **src/components/** | **JobRequirementForm**, **MatchForm** — JD·필터 입력; **CandidateResults**, **CandidateRow**, **CandidateCard**, **CandidateDetailModal** — 결과 목록·상세; **MatchScorePill**, **ExplainabilityPanel** — 점수·설명; **RecruiterHero**, **BiasGuardrailBanner**, **ResultCard** — UI 블록. |
| **src/types.ts** | 프론트 **공통 타입** (API 응답 등). |
| **src/utils/agentEvaluation.ts** | 에이전트 평가 결과 **표시/가공** 유틸. |
| **theme.css**, **index.css** | 전역·테마 **스타일**. |
| **vite.config.ts**, **package.json**, **Dockerfile**, **nginx.conf** | **빌드·배포** 설정. |

---

## 6. src/eval/ — 평가 코드가 의미하는 것

- **의미:** **Retrieval / Rerank / Agent** 품질을 **golden set**과 **LLM-as-Judge**로 평가하는 오프라인 파이프라인.

| 파일 | 의미 |
|------|------|
| **eval_runner.py** | **평가 실행** 진입점. retrieval/rerank/agent 메트릭 실행. |
| **config.py** | 평가 **설정**(경로, 모델, golden set 등). |
| **golden_set_maintenance.py** | **Golden set** 유지보수(추가·수정·검증). |
| **create_mode_subsets.py** | Golden set **서브셋** 생성(예: agent 전용). |
| **generate_llm_judge_annotations.py** | **LLM-as-Judge** 어노테이션 생성. |
| **regen_golden_set.py** | Golden set **재생성** 로직. |
| **reporting.py**, **metrics.py** | 평가 **리포트·메트릭** 산출. |
| **subsets/** | golden set JSONL 파일들(예: `golden.agent.jsonl`). |
| **outputs/** | 평가 결과 **아카이브** 디렉터리. |

---

## 7. scripts/ — 스크립트가 의미하는 것

| 파일 | 의미 |
|------|------|
| **ingest_resumes.py** | **이력서 수집 CLI.** `--source all`, `--target mongo`/`milvus`, `--suri-limit` 등. MongoDB 적재 후 Milvus 인덱싱(`--milvus-from-mongo`)까지. |
| **run_eval.sh** | **전체 평가** 실행(agent 등). |
| **run_retrieval_eval.sh** | **Retrieval** 전용 평가. |
| **run_rerank_eval.sh** | **Rerank** 전용 평가. |
| **update_golden_set.sh**, **regen_golden_set.sh** | Golden set **갱신·재생성** 실행. |

---

## 8. tests/ — 테스트가 의미하는 것

각 파일은 **해당 모듈·플로우의 동작**을 검증합니다.

| 파일 | 의미 |
|------|------|
| **test_api.py** | **API** 엔드포인트(health, match 등) 테스트. |
| **test_retrieval.py** | **Retrieval**(hybrid, keyword, vector) 동작 테스트. |
| **test_scoring_service.py** | **scoring_service** 점수·blend·penalty 테스트. |
| **test_hybrid_scoring.py** | **Fusion** 공식·가중치 테스트. |
| **test_ingestion_preprocessing.py** | **Ingestion 전처리** 테스트. |
| **test_golden_set_alignment.py**, **test_regen_golden_set.py** | **Golden set** 정렬·재생성 테스트. |
| **test_job_profile_extractor.py** | **JobProfile** 추출(역할, 스킬, 시니어리티 등) 테스트. |
| **test_sdk_runner_and_rerank_policy.py** | **SDK runner**·**rerank 정책** 테스트. |
| **test_resume_parsing.py** | **이력서 파싱** 테스트. |
| **test_matching_evaluation.py** | **매칭·에이전트 평가** 플로우 테스트. |

---

## 9. ops/ — 공통 운영이 의미하는 것

| 파일 | 의미 |
|------|------|
| **logging.py** | **로깅 설정** 및 `get_logger`. 구조화 로그·레벨. |
| **middleware.py** | **RequestIdMiddleware**(요청당 ID), **APILoggingMiddleware**(요청/응답 로깅). |
| **mongo_handler.py** | (선택) **MongoDB 로그 핸들러.** 로그를 MongoDB에 쓸 때 사용. |

---

## 10. 코드를 읽는 추천 순서

1. **전체 의미:** 이 문서(전체 코드 의미 상세 가이드)로 디렉터리·파일 역할 파악.
2. **요청부터 응답까지:** [코드 구조 및 핵심 흐름 가이드](../guides/codebase-core-flows.md)의 매칭 파이프라인 다이어그램과 표.
3. **점수·인원 수:** [스코어링 전체 흐름 가이드](../guides/scoring-flow-guide.md)로 “몇 명을 필터하고, 어떤 식으로 점수를 내는지” 추적.
4. **구현 추적:**  
   - `api/jobs.py` → `MatchingService.match_jobs()` → `_build_query_profile`(job_profile_extractor) → `_retrieve_candidates`(hybrid_retriever) → `_enrich_candidates`(candidate_enricher) → `_shortlist_candidates`(rerank_policy, cross_encoder_rerank_service) → `_score_candidates`(scoring_service, agents, match_result_builder) → `_run_fairness_guardrails`.
5. **확장·설정:** [CODE_STRUCTURE.md](../CODE_STRUCTURE.md)의 Extensibility와 config 설명.

---

## 11. 관련 문서

- [코드 구조 및 핵심 흐름 가이드](../guides/codebase-core-flows.md) — 흐름도·단계별 담당 모듈
- [스코어링 전체 흐름 가이드](../guides/scoring-flow-guide.md) — 스코어링 단계·수식·인원 수
- [CODE_STRUCTURE.md](../CODE_STRUCTURE.md) — 폴더 구조·확장 가이드
- [architecture/system_architecture.md](../architecture/system_architecture.md) — 시스템 아키텍처·레이어
- [data-flow/resume_ingestion_flow.md](../data-flow/resume_ingestion_flow.md) — 이력서 수집 플로우
- [data-flow/candidate_retrieval_flow.md](../data-flow/candidate_retrieval_flow.md) — 후보 검색·매칭 플로우
- [agents/multi_agent_pipeline.md](../agents/multi_agent_pipeline.md) — 에이전트 파이프라인 상세
