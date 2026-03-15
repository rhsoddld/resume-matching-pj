# AGENT.md — AI Resume Matching System

## Mission

AI-powered Resume Intelligence & Candidate Matching 시스템을 다음 원칙으로 구현하고 문서화한다.

- deterministic ingestion pipeline
- deterministic query understanding
- hybrid retrieval
- multi-agent evaluation
- agent-to-agent weight negotiation
- explainable ranking
- DeepEval / LLM-as-Judge / Bias guardrails

문서의 목적은 “현재 코드가 어디까지 왔는지”와 “최종적으로 어떤 시스템을 만들 것인지”를 동시에 명확하게 유지하는 것이다.

## Canonical Documentation Rules

| 무엇을 기록할까 | 어디에 기록할까 |
|------|------|
| 목표 아키텍처, 레이어 책임, 데이터 흐름 | `docs/architecture/system-architecture.md` |
| 현재 실행 계획, 다음 우선순위, 미구현 항목 | `docs/governance/PLAN.md` |
| 요구사항과 구현/평가 증거 연결 | `docs/governance/TRACEABILITY.md` |
| 실행 방법, 진입점, 구현 상태 요약 | `README.md` |
| 설계 결정과 trade-off | `docs/adr/DECISIONS.md` |

새 결정이 생기면 나중에 한 번에 정리하지 말고, 결정 시점에 바로 문서화한다.

## 시스템 계약

### 1. Offline Layer

- 입력은 PDF / CSV / Text 이력서 데이터셋이다.
- parsing / normalization은 deterministic pipeline으로 수행한다.
- 결과는 MongoDB candidate profile과 Milvus candidate embedding으로 분리 저장한다.

### 2. Query Understanding Layer

- Recruiter Job Description은 deterministic query understanding layer에서 구조화된다.
- 이 단계는 LLM agent가 아니다.
- 최소 출력 계약:
  - `job_category`
  - `roles`
  - `required_skills`
  - `related_skills`
  - `skill_signals`
  - `capability_signals`
  - `seniority_hint`
  - `filters`
  - `metadata_filters`
  - `query_text_for_embedding`
  - `lexical_query`
  - `semantic_query_expansion`
  - `signal_quality`
  - `confidence`
  - `fallback_used`
  - `fallback_reason`
  - `fallback_rationale`
  - `fallback_trigger`

### 3. Retrieval Layer

- retrieval은 아래 세 경로의 hybrid 전략을 따른다.
  - semantic vector search
  - keyword search
  - metadata filtering
- 산출물은 top-K candidate shortlist다.

### 4. Evaluation Layer

후보 shortlist는 아래 4개 agent로 평가한다.

- SkillMatchingAgent
- ExperienceEvaluationAgent
- TechnicalEvaluationAgent
- CultureFitAgent

각 agent는 `Evaluation Score Pack`에 자신의 점수와 근거를 남긴다.
또한, 이력서 원문에 대한 추가 증거가 필요할 경우 스스로 RAG 도구(`search_candidate_evidence`)를 호출하여 탐색한다.

### 5. Negotiation and Ranking Layer

- RecruiterAgent와 HiringManagerAgent는 서로 다른 관점의 weight proposal을 만든다.
- WeightNegotiationAgent는 이를 통합해 최종 ranking weight를 만든다.
- Ranking Engine은 negotiated weight를 적용해 final score를 계산한다.

### 6. Explainability and Guardrails

최종 응답은 아래를 포함하는 explainable recommendation이어야 한다.

- final score
- per-dimension score
- matched skills
- relevant experience
- technical strengths
- possible gaps
- weighting summary

품질 검증은 DeepEval, LLM-as-Judge, Bias guardrails를 기준으로 확장한다.

## 현재 저장소 해석 기준

| 목표 요소 | 현재 상태 | 기준 경로 |
|----------|----------|----------|
| Offline ingestion / normalization | 구현됨 | `src/backend/services/ingest_resumes.py` |
| Deterministic query understanding | v3 baseline 구현 | `src/backend/services/job_profile_extractor.py`, `src/backend/services/matching_service.py`, `src/backend/services/query_fallback_service.py` |
| Hybrid retrieval | baseline 구현 | `src/backend/repositories/hybrid_retriever.py` |
| 4-agent evaluation | baseline 구현 (hybrid runtime) | `src/backend/agents/contracts/`, `src/backend/agents/runtime/service.py` |
| Recruiter / Hiring Manager weight negotiation | baseline 구현 (SDK handoff + fallback) | `src/backend/agents/runtime/sdk_runner.py`, `src/backend/agents/contracts/weight_negotiation_agent.py` |
| Explainable ranking output | v3 baseline 구현 | `src/backend/services/match_result_builder.py`, `src/frontend/src/components/ResultCard.tsx`, `src/frontend/src/components/CandidateDetailModal.tsx` |
| DeepEval / LLM-as-Judge | Implemented | `src/eval/`, `docs/eval/eval-results.md`, `.github/workflows/eval-archive.yml` |
| Bias guardrails | Implemented (backend v1) | `src/backend/services/matching_service.py`, `tests/test_matching_service_fairness.py` |

문서에서는 이 상태를 `Implemented`, `Partial`, `Planned`로 일관되게 표시한다.

## 작업 원칙

1. Query Understanding은 deterministic layer로 유지한다.
2. 평가 agent는 shortlist 이후에만 사용하고 retrieval 전 단계로 확장하지 않는다.
3. ranking은 언제나 explainable output을 반환해야 한다.
4. 편향 가능성이 있는 속성은 scoring 근거에서 제외한다.
5. README, architecture, traceability는 서로 같은 상태 값을 사용한다.

## 현재 우선순위

1. (완료) negotiation 구간에 도입된 SDK handoff 경로를 4-agent 실행까지 확장해 handoff-native orchestration для 전환 및 RAG Tool 연동
2. ontology 기반 role/skill/capability 추출 품질 release gate를 CI에 연결하고 실패 시 배포 차단 정책을 고정
3. fusion retrieval 가중치 실험 및 calibration
4. DeepEval / LLM-as-Judge 결과 추세 리포트 고도화
5. (진행 중) Bias/Fairness metrics 운영 고도화 및 부하 테스트 자동화

## Reviewer Focus

Reviewer가 이 저장소를 볼 때 바로 확인할 수 있어야 하는 질문은 아래와 같다.

- JD가 어떻게 deterministic query로 변환되는가
- hybrid retrieval이 어떤 증거를 결합하는가
- 4개 evaluation agent의 역할이 어떻게 분리되고, RAG 도구를 어떻게 자율적으로 사용하는가
- recruiter와 hiring manager의 weight 차이를 어떻게 조정하는가
- 병렬 평가 및 Fallback 구조(SDK -> Live -> Heuristic)가 장애를 어떻게 막는가
- 최종 추천이 왜 explainable한가
- 품질과 공정성을 어떻게 검증하는가
