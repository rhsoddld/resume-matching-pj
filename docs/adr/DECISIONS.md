# DECISIONS — Architecture Decision Records (ADR Index)

> 각 ADR은 **맥락 → 결정 → 결과** 구조로 기록합니다.  
> 새로운 결정은 이 파일의 테이블에 추가하고 상세 내용을 하단에 작성합니다.

---

## 사용 원칙

이 문서는 **나중에 발표 직전에 회고용으로 쓰는 문서가 아니라**, 구현 중간중간 핵심 판단을 바로 남기는 작업 로그로 사용합니다.

- 새로운 기술/구조/운영 방식 중 하나를 **선택했을 때**
- 두 개 이상의 대안 중 하나를 **포기하거나 채택했을 때**
- 성능, 비용, 품질, 운영성 사이에서 **trade-off가 생겼을 때**
- 발표에서 "왜 이렇게 했나요?" 질문이 나올 가능성이 있을 때

짧게라도 먼저 기록하고, 필요하면 나중에 보강합니다.

### 빠른 기록 템플릿

아래 템플릿을 복사해서 새 ADR로 추가합니다.

```md
## ADR-XXX: [짧은 결정 제목]

### 맥락 (Context)
- 어떤 문제를 해결하려는가?
- 어떤 제약이 있었는가?
- 왜 지금 이 결정이 필요했는가?

### 고려한 대안 (Alternatives Considered)
- 대안 A:
- 대안 B:
- 대안 C:

### 결정 (Decision)
- 최종 선택:
- 선택 이유:

### 결과 (Consequences)
- 긍정:
- 부정:
- 완화 방안:

### Demo / Panel에서 강조할 포인트
- 이 결정이 사용자 가치 또는 시스템 품질에 준 영향
- 포기한 대안과 비교했을 때의 장점
```

---

## ADR 목록

| ID | 제목 | 날짜 | Status |
|----|------|------|--------|
| ADR-001 | Backend Layered Architecture 채택 | 2026-03-13 | ✅ Accepted |
| ADR-002 | Milvus + MongoDB 이중 저장소 전략 | 2026-03-13 | ✅ Accepted |
| ADR-003 | Ingestion = Rule-based Only, LLM은 RAG Pipeline에서만 | 2026-03-13 | ✅ Accepted |
| ADR-004 | Custom Multi-Agent Orchestration 우선 + OpenAI Agents SDK 단계적 전환 | 2026-03-13 | ✅ Accepted |
| ADR-005 | DeepEval + LangSmith 평가 스택 선택 | 2026-03-13 | ✅ Accepted |
| ADR-006 | Runtime Skill Ontology를 Config 파일로 외부화 | 2026-03-13 | ✅ Accepted |
| ADR-007 | Deterministic Scoring Baseline을 먼저 구현 | 2026-03-13 | ✅ Accepted |
| ADR-008 | 현재 제출 기준 문서/폴더 구조는 As-Is 기준으로 동기화 | 2026-03-13 | ✅ Accepted |
| ADR-009 | Embedding 기본 모델을 `text-embedding-3-small`로 고정 | 2026-03-13 | ✅ Accepted |
| ADR-010 | Negotiation 구간 OpenAI Agents SDK handoff 도입 + Runtime fallback 표준화 | 2026-03-15 | ✅ Accepted |

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

## ADR-004: Custom Multi-Agent Orchestration 우선 + OpenAI Agents SDK 단계적 전환

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

현재 실행 경로는 hybrid runtime으로 운영한다.

- 4-agent score pack은 SDK/live/heuristic 경로를 지원한다.
- negotiation 구간은 SDK에서 `RecruiterAgent -> HiringManagerAgent -> WeightNegotiationAgent` handoff를 우선 시도한다.
- SDK 실패/비활성 시 live JSON 경로, 그마저 실패 시 heuristic으로 degrade한다.
- 모든 Agent I/O는 Pydantic 모델로 타입 지정한다.

### 결과 (Consequences)
- **긍정**: fallback 안정성을 유지하면서 negotiation에 handoff 기반 A2A를 적용할 수 있다.
- **부정**: 4-agent 실행 경로는 여전히 완전 handoff-native가 아니어서 이중 런타임 복잡도가 남는다.
- **완화**: SDK migration backlog를 별도 워크스트림으로 운영해 score pack 구간까지 점진 전환한다.

---

## ADR-010: Negotiation 구간 OpenAI Agents SDK handoff 도입 + Runtime fallback 표준화

### 맥락 (Context)
기존 recruiter/hiring manager/negotiation은 오케스트레이터 순차 실행이었다.  
A2A를 실제로 구현하려면 agent 간 handoff가 필요했고, 동시에 운영 안정성을 위해 fallback을 유지해야 했다.

### 고려한 대안 (Alternatives Considered)
- 대안 A: 기존 순차 실행 유지 (handoff 미도입)
- 대안 B: 전체 4-agent + negotiation을 한 번에 handoff-native로 전환
- 대안 C: negotiation 구간부터 handoff를 도입하고 runtime fallback을 표준화

### 결정 (Decision)
- `sdk_runner.py`에서 negotiation 체인을 handoff로 전환한다.
  - `RecruiterAgent -> HiringManagerAgent -> WeightNegotiationAgent`
- run_context에 payload/score_pack/constraints(`max_turns`, disagreement threshold)를 공유한다.
- 최종 출력은 `WeightNegotiationOutput` 스키마로 강제한다.
- 실패 시 `service.py`에서 live JSON, heuristic fallback을 순차 적용한다.
- API/UI에 runtime mode와 fallback reason을 노출해 운영 가시성을 확보한다.

### 결과 (Consequences)
- **긍정**
  - negotiation 구간 A2A를 실제 handoff로 구현.
  - fallback 기반 안정성 유지.
  - UI에서 runtime/fallback 상태와 recruiter/hiring/final policy를 확인 가능.
- **부정**
  - score pack(4-agent) 구간은 아직 handoff-native가 아님.
  - runtime 경로가 다중이라 디버깅 복잡도 증가.
- **완화 방안**
  - runtime reason을 표준 필드로 남기고, traceability/plan에 단계별 전환 상태를 명시.
  - 다음 단계에서 4-agent 실행 경로 handoff-native 전환을 진행.

### Demo / Panel에서 강조할 포인트
- “A2A”를 문구가 아니라 실제 handoff 체인으로 구현했다.
- 실패 시 graceful degradation을 유지해 데모 안정성을 보장했다.
- 결과 화면에서 runtime mode, fallback reason, 협의된 가중치 정책을 확인할 수 있다.

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
- **운영 보충 (2026-03-15)**: Confident AI 업로드 연동은 optional이며 현재 검토 보류. 기본 운영은 DeepEval 로컬/CI 실행 + 문서 아카이브를 우선 사용하고, 대시보드는 MongoDB(상세 보관) + Prometheus/Grafana(시계열/알림) 경로를 검토한다.

---

## ADR-006: Runtime Skill Ontology를 Config 파일로 외부화

### 맥락 (Context)
스킬 정규화 품질은 taxonomy, alias, capability phrase, review-required 목록에 크게 좌우된다.  
이 로직을 코드에 하드코딩하면 ontology를 보정할 때마다 코드 수정과 배포가 필요해지고, 데이터 품질 개선 이력이 분리되지 않는다.

### 고려한 대안 (Alternatives Considered)
- 대안 A: skill mapping을 Python 상수로 코드에 직접 하드코딩
- 대안 B: MongoDB에 ontology를 저장하고 런타임에 읽기
- 대안 C: YAML config 파일로 버전 관리하고 런타임에 로드

### 결정 (Decision)
- `config/skill_aliases.yml`, `config/skill_taxonomy.yml`, `config/skill_role_candidates.yml`, `config/versioned_skills.yml` 등을 **운영 기준 런타임 설정**으로 사용한다.
- ontology 분석/초안/리뷰 이력은 `docs/ontology/`에 두고, 실제 ingestion/matching은 `config/`만 참조한다.
- `RuntimeSkillOntology.load_from_config(...)`로 로딩 경로를 단일화한다.

### 결과 (Consequences)
- **긍정**: ontology 품질 개선과 애플리케이션 코드 변경을 분리할 수 있다. reviewer에게도 "설정 기반 품질 개선" 근거를 보여주기 쉽다.
- **부정**: config 파일 간 정합성이 깨지면 런타임 오류 가능성이 있다.
- **완화 방안**: startup/load 시점 검증, quality gate 테스트, 버전 파일 유지로 변경 이력을 남긴다.

### Demo / Panel에서 강조할 포인트
- 스킬 정규화 정확도 개선을 코드 변경이 아닌 config iteration으로 빠르게 진행할 수 있었다.
- ontology 연구용 문서와 운영용 설정을 분리해 실험과 배포 경계를 명확히 했다.

---

## ADR-007: Deterministic Scoring Baseline을 먼저 구현

### 맥락 (Context)
최종 목표는 Multi-Agent scoring이지만, 제출 전 반드시 동작하는 매칭 API와 설명 가능한 점수 구조가 필요하다.  
초기부터 LLM-only 평가로 가면 비용, 지연, 회귀 검증 난도가 커지고 장애 시 데모 리스크도 높아진다.

### 고려한 대안 (Alternatives Considered)
- 대안 A: 처음부터 LLM rerank / multi-agent scoring을 필수 경로로 구현
- 대안 B: 벡터 검색 결과를 그대로 반환
- 대안 C: deterministic scoring baseline을 먼저 만들고 이후 agent layer를 증분 확장

### 결정 (Decision)
- 현재 매칭 API의 기본 동작은 **embedding retrieval + deterministic scoring**으로 고정한다.
- 점수는 semantic similarity, skill overlap, experience fit, seniority fit, category fit으로 분해한다.
- Multi-Agent scoring과 explanation은 Phase 2 확장 범위로 둔다.

### 결과 (Consequences)
- **긍정**: 지금 단계에서도 E2E 데모가 가능하고, 점수 breakdown을 명확히 설명할 수 있다. 테스트와 회귀 검증도 단순해진다.
- **부정**: 정성적 적합도나 nuanced reasoning은 아직 반영이 제한적이다.
- **완화 방안**: deterministic baseline 위에 rerank/agent 레이어를 추가하는 계층형 구조로 확장한다.

### Demo / Panel에서 강조할 포인트
- "먼저 동작하고 설명 가능한 baseline"을 확보한 뒤 AI 레이어를 증분 확장하는 전략을 택했다.
- 단순 벡터 유사도만 반환하지 않고 score breakdown을 제공해 reviewer가 결과 근거를 확인할 수 있게 했다.

---

## ADR-008: 현재 제출 기준 문서/폴더 구조는 As-Is 기준으로 동기화

### 맥락 (Context)
심사자는 제출 직후 README와 폴더 구조를 먼저 본다.  
목표 구조를 실제 구현처럼 적어두면 문서 신뢰도가 떨어지고, 발표 전 질문에서 "문서와 저장소가 왜 다르냐"는 리스크가 생긴다.

### 고려한 대안 (Alternatives Considered)
- 대안 A: 목표 구조를 그대로 유지하고 추후 구현 예정이라고 구두 설명
- 대안 B: 현재 저장소 구조와 향후 목표 구조를 문서에서 명확히 분리

### 결정 (Decision)
- `README.md`와 `PLAN.md`의 폴더 구조는 **현재 저장소에 실제 존재하는 파일/디렉토리 기준**으로 우선 맞춘다.
- 이후 구조 변경 시에는 실제 디렉터리(`src/backend/agents/contracts`, `src/eval`, `src/frontend`, `docs/eval`) 기준으로 문서를 갱신한다.
- 심사용 문서는 항상 "현재 구현"과 "향후 확장"을 구분해서 기록한다.

### 결과 (Consequences)
- **긍정**: 제출물과 문서의 정합성이 올라가고, reviewer가 현재 상태를 빠르게 이해할 수 있다.
- **부정**: 미래 구조를 한 눈에 보여주는 느낌은 줄어들 수 있다.
- **완화 방안**: README/PLAN에 목표 구조를 별도 섹션으로 유지해 roadmap은 계속 보여준다.

### Demo / Panel에서 강조할 포인트
- 문서를 aspirational하게 쓰지 않고, 제출 시점의 실제 구현 상태와 정확히 맞췄다.
- reviewer가 저장소를 열자마자 현재 구현 범위와 이후 확장 범위를 구분할 수 있게 했다.

---

## ADR-009: Embedding 기본 모델을 `text-embedding-3-small`로 고정

### 맥락 (Context)
현재 capstone 단계에서는 정확도 상향 실험보다, 반복 실행 가능한 ingestion/retrieval 파이프라인과 안정적인 데모 운영이 더 중요하다.  
대량 문서 임베딩/재임베딩이 반복되는 상황에서 모델 단가와 지연은 운영 리스크로 직결된다.

### 고려한 대안 (Alternatives Considered)
- 대안 A: 기본값을 `text-embedding-3-large`로 설정
- 대안 B: 기본값을 `text-embedding-3-small`로 설정하고 필요 시 large로 전환

### 결정 (Decision)
- 기본 embedding 모델은 `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`로 고정한다.
- 품질 실험에서 필요성이 확인되면 환경변수만 변경해 `text-embedding-3-large`로 전환한다.

### 결과 (Consequences)
- **긍정**: 비용 절감, 빠른 반복 실험, 데모 안정성 확보.
- **부정**: 일부 semantic edge case에서 large 대비 retrieval 품질 손실 가능.
- **완화 방안**: golden set 기반 평가에서 품질 임계치 미달 시 large 전환 또는 rerank 강화.

### Demo / Panel에서 강조할 포인트
- small 선택은 임의가 아니라 capstone의 비용/속도/재현성 제약을 반영한 의도적 결정이다.
- 모델 선택은 하드코딩이 아니라 환경변수 기반 정책이라 운영 단계에서 쉽게 상향 가능하다.
