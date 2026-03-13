# DECISIONS — Architecture Decision Records (ADR Index)

> 각 ADR은 **맥락 → 결정 → 결과** 구조로 기록합니다.  
> 새로운 결정은 이 파일의 테이블에 추가하고 상세 내용을 하단에 작성합니다.

---

## ADR 목록

| ID | 제목 | 날짜 | Status |
|----|------|------|--------|
| ADR-001 | Backend Layered Architecture 채택 | 2026-03-13 | ✅ Accepted |
| ADR-002 | Milvus + MongoDB 이중 저장소 전략 | 2026-03-13 | ✅ Accepted |
| ADR-003 | Ingestion = Rule-based Only, LLM은 RAG Pipeline에서만 | 2026-03-13 | ✅ Accepted |
| ADR-004 | OpenAI Agents SDK 기반 Multi-Agent 아키텍처 (ResumeParsingAgent 제외) | 2026-03-13 | ✅ Accepted |
| ADR-005 | DeepEval + LangSmith 평가 스택 선택 | 2026-03-13 | ✅ Accepted |

---

## ADR-001: Backend Layered Architecture 채택

### 맥락 (Context)
FastAPI 기반 백엔드를 구성할 때 코드베이스가 커짐에 따라 유지보수성과 테스트 가능성이 중요해진다.  
Agent SDK, MongoDB, Milvus 등 다수의 외부 의존성을 갖는 프로젝트에서 의존성 관리가 필요하다.

### 결정 (Decision)
`api → services → repositories → core` 순서의 **단방향 의존 계층 구조**를 고정한다.

| 계층 | 경로 | 역할 |
|------|------|------|
| API | `src/backend/api/` | HTTP 요청/응답 처리, 라우팅 |
| Service | `src/backend/services/` | 도메인 비즈니스 로직 |
| Repository | `src/backend/repositories/` | DB/벡터스토어 CRUD |
| Core | `src/backend/core/` | 설정, 로깅, DB 클라이언트, 공통 예외 |
| Schema | `src/backend/schemas/` | Pydantic 요청/응답/도메인 모델 |

### 결과 (Consequences)
- **긍정**: 각 계층을 독립적으로 mock하여 단위 테스트 가능. Agent와 Backend의 경계가 명확.
- **부정**: 단순한 CRUD도 여러 계층을 거쳐야 하는 boilerplate 증가.
- **완화**: 간단한 admin/health 엔드포인트는 Service 없이 Repository 직접 호출 허용.

---

## ADR-002: Milvus + MongoDB 이중 저장소 전략

### 맥락 (Context)
Resume 매칭은 **의미 기반 벡터 검색**(자연어 job description → 유사 후보)과  
**메타데이터 필터링**(category, 연차, seniority) 두 가지를 동시에 요구한다.

### 결정 (Decision)

| 저장소 | 역할 | 컬렉션 |
|--------|------|--------|
| **Milvus** | 벡터 유사도 검색 + 메타 필터 (category, experience_years, seniority_level) | `candidate_embeddings` |
| **MongoDB** | 전체 구조화 도메인 데이터 저장, Milvus 장애 시 fallback 검색 | `candidates`, `jobs`, `match_results` |

Milvus를 **primary 검색 경로**, MongoDB를 **fallback + 도메인 데이터 소스**로 사용한다.  
Abstraction layer(`HybridRetriever`)를 두어 Milvus → FAISS/Chroma 교체 가능하게 설계한다.

### 결과 (Consequences)
- **긍정**: Hybrid search(벡터 + 필터) 지원. Milvus 장애 시 Mongo fallback으로 graceful degradation.
- **부정**: 두 저장소 간 데이터 동기화 관리 필요 (Ingestion 시 동시 upsert로 해결).

---

## ADR-003: Ingestion = Rule-based Only, LLM은 RAG Pipeline에서만

### 맥락 (Context)

대량 이력서 적재 구간에서 생성형 LLM 파싱을 사용하면 다음 문제가 발생한다:

| 문제 | 내용 |
|------|------|
| **비용 급증** | 수천 건 × 호출 단가로 초기 적재/재처리 비용이 빠르게 증가 |
| **비결정성** | 동일 입력에서도 파싱 결과가 달라져 회귀 검증이 어려움 |
| **운영 리스크** | 외부 API 장애/레이트리밋 시 ingestion 작업 전체가 중단됨 |
| **처리 시간** | 대량 배치에서 레이턴시 누적으로 적재 시간이 과도하게 늘어남 |
| **과잉 복잡도** | ingestion은 대부분 정형 전처리로도 충분히 처리 가능 |

또한 `ResumeParsingAgent`를 독립 Agent로 유지하면 시스템 경계가 모호해지고 비용 통제가 어려워진다.

### 결정 (Decision)

1. **Ingestion 파싱은 rule-based only**로 고정한다. (regex + programmatic parser)
2. **ResumeParsingAgent는 운용 대상에서 제외**한다.
3. **LLM 사용 허용 구간은 매칭 시점(RAG scoring/explanation)으로 제한**한다.
4. 벡터 검색 인덱스 구축을 위한 **Embedding API 호출은 허용**한다.  
   이 호출은 파싱 로직이 아니라 인덱싱 단계로 분리한다.
5. 운영 모드는 **초기 1회 Full Load + 이후 Incremental(변경분만)**으로 고정한다.

| 구간 | 수행 주체 | 생성형 LLM |
|---------|------|-----|
| 텍스트 클리닝/정규화/파생 필드 계산 | `ingest_resumes.py` | ❌ 금지 |
| 임베딩 생성 및 Milvus 적재 | `ingest_resumes.py` + Embedding model | 제한적 허용 |
| 매칭 점수/설명 생성 | Agent RAG Pipeline | ✅ 허용 |

구조화 필드가 비어 있는 문서(Sneha 등)는 ingestion에서 무리하게 LLM 파싱하지 않고,  
RAG 요청 시 `raw.resume_text`를 컨텍스트로 포함해 Agent가 해당 요청 범위에서만 해석한다.

### 결과 (Consequences)
- **긍정**
  - 비용 통제: 재실행 시 변경분만 upsert/embedding하여 비용과 시간을 절감.
  - 재현성: 동일 입력은 동일 정규화 결과를 보장.
  - 운영성: ingestion이 생성형 LLM 장애에 영향받지 않음.
- **부정**
  - 비구조화 이력서의 일부 필드는 null로 남을 수 있음.
- **완화**
  - parser 강화(spaCy), 동의어 맵 확장, 파생 규칙 추가.
  - RAG fallback: null 필드가 있으면 `raw.resume_text`를 CandidateContext에 포함.
- **실행 원칙**
  - 초기 적재: Mongo 정규화 적재 → Milvus embedding 적재.
  - 이후 운영: `normalization_hash`/`embedding_hash` 기준 증분 처리.

---

## ADR-004: OpenAI Agents SDK 기반 Multi-Agent 아키텍처

### 맥락 (Context)
Resume 매칭은 Skill / Experience / Technical / Culture 등 여러 차원을 독립적으로 평가해야 한다.  
각 차원의 평가 로직이 복잡해짐에 따라 Monolithic LLM 호출보다 역할 분리가 유리하다.

### 결정 (Decision)

| Agent | 역할 | 출력 |
|-------|------|------|
| `OrchestratorAgent` | 매칭 요청 조율, 하위 Agent 호출, raw_text 컨텍스트 포함 여부 결정 | - |
| `SkillMatchingAgent` | Skill coverage 점수 (0–1) + 매칭 스킬 목록 | `SkillScore` |
| `ExperienceEvalAgent` | 경력 fit 점수 + seniority 적합성 (parsed 필드 우선, null이면 raw_text 참조) | `ExperienceScore` |
| `TechnicalEvalAgent` | 기술 스택 깊이 분석 (parsed 필드 우선, null이면 raw_text 참조) | `TechnicalScore` |
| `CultureFitAgent` | Soft-skill / domain fit 시그널 | `CultureScore` |
| `RankingAgent` | 가중 합산 + 자연어 explanation 생성 | `MatchResult` |
| `RecruiterAgent` ↔ `HiringManagerAgent` | A2A weight 협의 | 조정된 weight |

모든 Agent I/O는 Pydantic 모델로 타입 지정. Tool 함수를 통해서만 DB 접근.

### 결과 (Consequences)
- **긍정**: 각 Agent 독립 테스트 가능. Weight 조정이 유연함(A2A). 설명 가능한 점수 breakdown.
- **부정**: Agent 간 직렬 호출 시 지연 증가. 병렬화 최적화 필요.

---

## ADR-005: DeepEval + LangSmith 평가 스택 선택

### 맥락 (Context)
RAG + Agent 파이프라인의 품질을 정량적으로 측정하고 변경에 따른 회귀를 탐지해야 한다.

### 결정 (Decision)

| 도구 | 역할 |
|------|------|
| **DeepEval** | LLM-as-Judge 메트릭 정의 및 자동 평가 실행 |
| **LangSmith** | run/experiment/dataset 추적, 파라미터·프롬프트·결과 버전 관리 |
| **golden_set.jsonl** | ground-truth (job_description + expected_candidates) |

### 결과 (Consequences)
- **긍정**: 자동화된 품질 루프. 실험 단위 재현 가능. LangSmith로 프롬프트 변경 효과 추적.
- **부정**: LangSmith API Key 필요. Eval 실행 시 LLM 비용 발생.
