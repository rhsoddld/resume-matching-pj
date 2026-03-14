# TRACEABILITY MATRIX — AI Resume Matching System

이 문서는 목표 아키텍처의 각 단계가 현재 저장소 어디에 반영되어 있는지, 그리고 무엇이 아직 남아 있는지 추적하기 위한 매트릭스다.

## 1. 목표 흐름 기준 추적

| ID | 목표 단계 | 설계 의도 | 현재 증거 | 상태 | 다음 작업 |
|----|----------|----------|----------|------|----------|
| T1 | Offline ingestion pipeline | 이력서를 deterministic하게 파싱 / 정규화하고 MongoDB / Milvus에 적재 | `src/backend/services/ingest_resumes.py` | Implemented | parsing quality 측정치와 버전 문서화 보강 |
| T2 | Deterministic query understanding | JD를 structured query object로 변환 | `src/backend/services/job_profile_extractor.py`, `src/backend/services/matching_service.py`, `src/backend/services/query_fallback_service.py`, `src/eval/test_query_understanding_quality.py`, `src/eval/query_understanding_golden_set.jsonl` | Implemented v3 baseline | ontology-aligned role/skill/capability 정확도 검증과 threshold 운영 + constrained LLM fallback |
| T3 | Hybrid retrieval | vector + keyword + metadata 신호 결합으로 shortlist 생성 | `src/backend/repositories/hybrid_retriever.py`, `src/backend/services/retrieval_service.py` | Implemented baseline | 직군별 fusion weight 실험 및 calibration |
| T4 | Multi-agent evaluation | skill / experience / technical / culture 관점 분리 평가 | `src/agents/*.py`, `src/backend/services/agent_orchestration_service.py` | Implemented baseline | agent evidence quality와 output schema 확장 |
| T5 | Recruiter / Hiring Manager weight proposal | 서로 다른 채용 관점을 반영한 weight 제안 | `src/agents/weight_negotiation_agent.py` | Implemented baseline | role-specific weight policy 실험 |
| T6 | Weight negotiation | conflicting priorities를 조정해 최종 weight 생성 | `src/backend/services/agent_orchestration_service.py`, `src/agents/weight_negotiation_agent.py` | Implemented baseline | rationale와 audit field 강화 |
| T7 | Explainable ranking | 점수뿐 아니라 이유와 gap을 함께 반환 | `src/backend/services/scoring_service.py`, `src/backend/services/match_result_builder.py`, `src/frontend/src/components/ResultCard.tsx` | Implemented baseline | evidence 품질, 문장 간결성, 누락 근거 보강 |
| T8 | Evaluation and guardrails | quality / fairness 검증 체계 확보 | `src/eval/`, `docs/architecture/system-architecture.md` | Partial | DeepEval runs, LLM-as-Judge rubric, bias guardrails 구현 |

## 2. 설계 요구사항 ↔ 구현 위치

| Requirement | 구현 위치 | 상태 |
|------------|----------|------|
| Resume parsing & normalization pipeline | `src/backend/services/ingest_resumes.py`, `src/backend/services/resume_parsing.py` | Implemented |
| Candidate profiles in MongoDB | `src/backend/repositories/mongo_repo.py`, Mongo `candidates` collection | Implemented |
| Candidate embeddings in Milvus | `src/backend/core/vector_store.py` | Implemented |
| JD deterministic parser | `src/backend/services/job_profile_extractor.py` | Implemented v3 baseline |
| Low-confidence query fallback | `src/backend/services/query_fallback_service.py`, `src/backend/services/matching_service.py` | Implemented |
| Query object as shared context | `src/backend/services/matching_service.py`, `src/backend/schemas/job.py` | Implemented v3 baseline |
| Semantic retrieval | `src/backend/services/retrieval_service.py` | Implemented |
| Keyword retrieval | `src/backend/repositories/hybrid_retriever.py` keyword score path | Implemented baseline |
| Metadata filters | `src/backend/repositories/hybrid_retriever.py`, `src/backend/core/vector_store.py` | Implemented baseline |
| SkillMatchingAgent | `src/agents/skill_agent.py` | Implemented baseline |
| ExperienceEvaluationAgent | `src/agents/experience_agent.py` | Implemented baseline |
| TechnicalEvaluationAgent | `src/agents/technical_agent.py` | Implemented baseline |
| CultureFitAgent | `src/agents/culture_agent.py` | Implemented baseline |
| RecruiterAgent / HiringManagerAgent viewpoint | `src/backend/services/agent_orchestration_service.py` live or heuristic negotiation payload | Implemented baseline |
| WeightNegotiationAgent | `src/agents/weight_negotiation_agent.py` | Implemented baseline |
| Ranking engine | `src/backend/services/scoring_service.py` | Implemented current policy |
| Explainable recommendation payload | `src/backend/services/match_result_builder.py`, `src/frontend/src/App.tsx`, `src/frontend/src/components/ResultCard.tsx` | Implemented baseline |
| DeepEval / LLM-as-Judge | `src/eval/` | Partial |
| Bias guardrails | not yet implemented | Planned |

## 3. 문서 증거

| 주제 | 문서 |
|------|------|
| 목표 아키텍처 | [docs/architecture/system-architecture.md](../architecture/system-architecture.md) |
| 거버넌스 기준 | [docs/governance/AGENT.md](./AGENT.md) |
| 실행 계획 | [docs/governance/PLAN.md](./PLAN.md) |
| 프로젝트 개요 / 실행 방법 | [README.md](../../README.md) |
| 설계 결정 | [docs/adr/DECISIONS.md](../adr/DECISIONS.md) |

## 4. Reviewer Checklist

| 질문 | 현재 답변 가능 여부 | 비고 |
|------|------------------|------|
| 이력서가 어디서 어떻게 구조화되는가 | Yes | offline ingestion pipeline 문서화됨 |
| JD가 LLM 없이 어떻게 구조화되는가 | Yes | query_profile 응답에서 추출 결과를 직접 확인 가능 |
| retrieval이 어떤 신호를 결합하는가 | Yes | vector + keyword + metadata fusion score로 동작 |
| 4개 evaluation agent가 무엇을 평가하는가 | Yes | 역할 분리는 문서화됨 |
| recruiter와 hiring manager의 관점 차이를 어떻게 반영하는가 | Yes | weight negotiation baseline 존재 |
| 결과가 왜 explainable한가 | Yes | relevant_experience / possible_gaps / weighting_summary 포함 |
| 품질과 공정성을 어떻게 검증하는가 | Partial | DeepEval stub 존재, bias guardrails는 계획 단계 |

## 5. 남은 갭

1. Query understanding 추출 정확도(role/skill/capability + strength)를 직군별로 측정하는 운영 대시보드가 아직 없다.
2. fusion weight(0.55/0.30/0.15)의 직군별 최적값 검증이 아직 없다.
3. DeepEval / LLM-as-Judge 결과 artifact가 문서 증거로 축적되지 않았다.
4. Bias guardrails가 아직 문서 수준을 넘지 못했다.
5. fallback 사용 비율과 품질 개선 효과를 운영 대시보드로 추적하는 경로가 아직 없다.
