# TRACEABILITY MATRIX — AI Resume Matching System

기준 요구사항 문서: `requirements/requirements.md`  
상태 정의:

- `Implemented`: 코드/테스트/문서 증거가 모두 존재
- `Partial`: 일부 구현 또는 문서/운영 증거 미흡
- `Planned`: 구현 미완료, 계획 단계

---

## 1) Problem / Objective / Capability Trace

| ID | Requirement Summary | Evidence | Status | Gap / Next |
|---|---|---|---|---|
| PO.1 | 키워드 검색 이상 정합 평가 | `src/backend/services/matching_service.py`, `src/backend/services/scoring_service.py`, `src/backend/agents/runtime/service.py` | Implemented | 직군별 정밀도 리포트 추가 |
| PO.2 | 위치/학력/산업 메타 필터 | `src/backend/schemas/job.py`, `src/backend/repositories/hybrid_retriever.py`, `src/backend/services/candidate_enricher.py`, `tests/test_candidate_enricher_filters.py` | Implemented | 필터 explainability(왜 탈락했는지) 응답 필드 추가 |
| PO.3 | transferable skill 탐지 | `src/backend/services/job_profile_extractor.py`, `src/backend/services/skill_ontology/`, `tests/test_job_profile_extractor.py` | Implemented | 산업별 전이 스킬 calibration 리포트 추가 |
| PO.4 | 다양한 포맷 파싱 | `src/backend/services/ingest_resumes.py`, `src/backend/services/resume_parsing.py` | Partial | PDF/외부 포트폴리오 링크 파서 보강 |
| PO.5 | 인사이트 + 설명형 점수 | `src/backend/services/match_result_builder.py`, `src/frontend/src/components/ExplainabilityPanel.tsx` | Implemented | 설명 품질 자동평가 루프 강화 |
| PO.6 | 대규모 탐색 효율화 | `src/backend/services/retrieval_service.py`, `src/backend/repositories/hybrid_retriever.py`, `scripts/benchmark_retrieval.py` | Partial | 부하 테스트 자동화 및 기준선(환경별 baseline) 문서화 |
| KC.1 | 자연어 요구 의미 해석 | `src/backend/services/job_profile_extractor.py`, `tests/test_job_profile_extractor.py`, `src/eval/query_understanding_golden_set.jsonl` | Implemented | 질의 유형별 회귀 리포트 자동화 |
| KC.2 | 지능형 후보 매칭 | `src/backend/services/matching_service.py`, `src/backend/services/scoring_service.py` | Implemented | 산업별 calibration 필요 |
| KC.3 | 스킬 맥락 기반 숙련도 구분 | `src/backend/agents/contracts/technical_agent.py`, `src/backend/agents/contracts/skill_agent.py`, `src/backend/agents/runtime/service.py`, `tests/test_agent_orchestration_service.py` | Implemented | evidence sentence 품질 자동평가 지표 추가 |
| KC.4 | 경력 성장/전환 분석 | `src/backend/agents/contracts/experience_agent.py`, `src/backend/services/resume_parsing.py`, `src/backend/services/match_result_builder.py`, `tests/test_ranking_policy.py` | Implemented | trajectory 시각화(UI) 및 경력 단절 해석 규칙 보강 |
| KC.5 | 인접 스킬 추천 | `src/backend/services/skill_ontology/`, `src/backend/services/match_result_builder.py`, `src/backend/schemas/job.py`, `tests/test_ranking_policy.py` | Implemented | adjacent score 가중치 정책 문서화/튜닝 |
| KC.6 | 구조화 후보 인사이트 | `src/backend/schemas/job.py`, `src/backend/services/match_result_builder.py` | Implemented | 인사이트 템플릿 일관성 개선 |
| KC.7 | explainable matching score | `src/backend/services/scoring_service.py`, `src/backend/services/match_result_builder.py`, `src/frontend/src/components/MatchScorePill.tsx` | Implemented | 근거 추적 링크 추가 |

---

## 2) Requirement 1 (Basic) Trace

| ID | Requirement Summary | Evidence | Status | Gap / Next |
|---|---|---|---|---|
| R1.1 | Basic RAG 후보 검색 | `src/backend/services/retrieval_service.py`, `src/backend/core/vector_store.py` | Implemented | 검색 품질 벤치마크 문서화 |
| R1.2 | 스킬 기반 semantic matching | `src/backend/services/matching_service.py`, `tests/test_skill_overlap_scoring.py` | Implemented | 난이도별 threshold 튜닝 |
| R1.3 | skill-overlap ranking agent | `src/backend/agents/contracts/ranking_agent.py`, `tests/test_ranking_policy.py` | Implemented | 정책 버전관리 강화 |
| R1.4 | job category filtering | `src/backend/repositories/hybrid_retriever.py`, `src/backend/schemas/job.py` | Implemented | category taxonomy 확장 |
| R1.5 | basic job-resume alignment score | `src/backend/services/scoring_service.py`, `src/backend/schemas/job.py` | Implemented | weight calibration 실험 |
| R1.6 | 입력 guardrails | `src/backend/schemas/job.py`, `tests/test_api_endpoints.py` | Implemented | 악성 입력 패턴 차단 규칙 추가 |
| R1.7 | resume parsing validation | `src/backend/services/resume_parsing.py`, `src/backend/services/ingest_resumes.py` | Implemented | 파싱 실패 유형별 대시보드 |
| R1.8 | metadata filtering(exp/role/edu) | `src/backend/repositories/hybrid_retriever.py`, `src/backend/services/candidate_enricher.py` | Implemented | 필터 explainability 개선 |
| R1.9 | API endpoint 노출 | `src/backend/main.py`, `src/backend/api/jobs.py`, `src/backend/api/candidates.py`, `src/backend/api/ingestion.py`, `tests/test_api_endpoints.py` | Implemented | ingestion endpoint에 인증/레이트리밋 baseline 적용 |

---

## 3) Requirement 2 (Advanced) Trace

| ID | Requirement Summary | Evidence | Status | Gap / Next |
|---|---|---|---|---|
| R2.1 | DeepEval quality + diversity | `src/eval/test_match_quality.py`, `src/eval/eval_metrics.py`, `src/eval/golden_set.jsonl`, `docs/eval/eval-results.md`, `.github/workflows/eval-archive.yml` | Implemented | metric drift 모니터링 대시보드 추가 |
| R2.2 | custom eval(skill/exp/culture) | `src/eval/test_skill_coverage.py`, `src/eval/test_match_quality.py`, `src/eval/eval_metrics.py`, `docs/eval/eval-results.md` | Implemented | 직군별 임계치 차등화 검토 |
| R2.3 | fine-tuned embedding rerank | `src/backend/services/cross_encoder_rerank_service.py`, `src/backend/core/settings.py`, `tests/test_rerank_pipeline.py` | Partial | embedding rerank baseline과 optional LLM rerank는 구현됨. 실제 fine-tuned embedding 학습/버전관리/A-B/rollback/runbook 증거를 추가해야 함 |
| R2.4 | LLM-as-judge(soft skill/potential) | `src/eval/test_skill_coverage.py`, `src/backend/agents/contracts/culture_agent.py`, `scripts/generate_eval_results.py`, `src/backend/core/model_routing.py`, `docs/eval/llm_judge_softskill_potential_rubric.md`, `docs/eval/eval-results.md`, `.github/workflows/eval-archive.yml` | Implemented | score explanation 템플릿 표준화 |
| R2.5 | token usage optimization | `docs/governance/PLAN.md` | Planned | 토큰 예산/캐시/배치 전략 구현 |
| R2.6 | performance benchmark(candidates/sec) | `scripts/benchmark_retrieval.py`, `scripts/generate_retrieval_benchmark_archive.py`, `.github/workflows/retrieval-benchmark-archive.yml`, `src/backend/services/retrieval_service.py`, `src/backend/repositories/hybrid_retriever.py`, `docs/eval/retrieval-benchmark.md` | Partial | 성공 baseline 수치는 확보됨. 다음 단계는 고부하 부하 테스트 자동화와 환경별 기준선 관리 |
| R2.7 | bias detection guardrails | `src/backend/services/matching_service.py`, `tests/test_matching_service_fairness.py`, `src/backend/core/settings.py`, `src/frontend/src/components/BiasGuardrailBanner.tsx`, `docs/architecture/system-architecture.md` | Implemented | fairness metric 운영 대시보드 및 정책 튜닝 고도화 |
| R2.8 | simple frontend interface | `src/frontend/src/App.tsx`, `src/frontend/src/components/JobRequirementForm.tsx`, `src/frontend/src/components/CandidateResults.tsx` | Implemented | UX polishing 및 에러 상태 강화 |

---

## 4) Hybrid Retrieval / Multi-Agent / Additional Intelligence Trace

| ID | Requirement Summary | Evidence | Status | Gap / Next |
|---|---|---|---|---|
| HCR.1 | vector + keyword hybrid search | `src/backend/repositories/hybrid_retriever.py`, `src/backend/services/retrieval_service.py` | Implemented | fusion weight 실험 자동화 |
| HCR.2 | dynamic filtering(exp/skill/edu/industry) | `src/backend/schemas/job.py`, `src/backend/repositories/hybrid_retriever.py`, `src/backend/services/candidate_enricher.py`, `tests/test_candidate_enricher_filters.py` | Implemented | 필터별 drop-off 모니터링 지표 추가 |
| HCR.3 | cross-encoder reranking | `src/backend/services/cross_encoder_rerank_service.py`, `src/backend/services/matching_service.py`, `src/backend/core/settings.py`, `src/backend/core/model_routing.py`, `tests/test_rerank_pipeline.py`, `scripts/compare_rerank_modes.py`, `docs/eval/llm-rerank-comparison.md` | Partial | 조건부 게이트(top score gap/query ambiguity), top_n cap, timeout/fallback, 모델 라우팅/버전 라벨 정책은 구현됨. 다만 현재 샘플에서는 proxy quality 개선이 일관되지 않아 optional 경로 유지가 적절 |
| MSA.1 | multi-agent pipeline | `src/backend/agents/contracts/orchestrator.py`, `src/backend/agents/runtime/service.py`, `src/backend/agents/runtime/sdk_runner.py` | Partial | negotiation handoff는 SDK 적용 완료, 4-agent 실행 경로 handoff-native 확장 필요 |
| MSA.2 | Resume Parsing Agent | `src/backend/services/resume_parsing.py` | Implemented | 파싱 신뢰도 점수 노출 |
| MSA.3 | Skill Matching Agent | `src/backend/agents/contracts/skill_agent.py` | Implemented | 근거 span 추출 강화 |
| MSA.4 | Experience Evaluation Agent | `src/backend/agents/contracts/experience_agent.py` | Implemented | 경력 단절/전환 해석 보강 |
| MSA.5 | Technical Evaluation Agent | `src/backend/agents/contracts/technical_agent.py` | Implemented | 아키텍처 역량 평가 정교화 |
| MSA.6 | Culture Fit Agent | `src/backend/agents/contracts/culture_agent.py` | Implemented | 편향 완화 규칙 추가 |
| AHI.1 | explainable ranking breakdown | `src/backend/services/match_result_builder.py`, `src/frontend/src/components/ExplainabilityPanel.tsx` | Implemented | 근거 문장 링크화 |
| AHI.2 | recruiter feedback loop | `docs/governance/PLAN.md` | Planned | 피드백 수집 API/저장 모델 추가 |
| AHI.3 | hiring analytics dashboard | `docs/governance/PLAN.md` | Planned | 대시보드 구현 및 지표 정의 |
| AHI.4 | interview scheduling handoff | `docs/governance/PLAN.md` | Planned | 스케줄링 에이전트/이벤트 연동 필요 |
| AHI.5 | recruiter↔hiring manager A2A | `src/backend/agents/runtime/service.py`, `src/backend/agents/runtime/sdk_runner.py`, `src/backend/agents/runtime/prompts.py`, `src/backend/agents/contracts/weight_negotiation_agent.py`, `src/backend/core/observability.py`, `src/ops/middleware.py`, `src/ops/logging.py` | Implemented | request_id 기반 로그↔trace 상관관계 운영 대시보드 고도화 |

---

## 5) Deliverables / Dataset Trace

| ID | Requirement Summary | Evidence | Status | Gap / Next |
|---|---|---|---|---|
| D.1 | Architecture Diagram 제출 | `docs/architecture/system-architecture.md` | Partial | JPEG/PDF 산출본 추가 필요 |
| D.2 | Design + trade-off 문서 | `docs/governance/DESIGN_DECISION_MATRIX.md`, `docs/scoring_design.md`, `docs/ingestion_normalization_design.md` | Implemented | 최신 결정 반영 점검 |
| D.3 | Full executable microservice + README | `src/backend/main.py`, `docker-compose.yml`, `README.md` | Implemented | 배포 시나리오 문서 보강 |
| D.4 | 10분 패널 발표 자료 | `README.md`, `docs/architecture/system-architecture.md` | Partial | 발표용 슬라이드/데모 스크립트 작성 필요 |
| DS.1 | primary dataset 지원 | `src/backend/services/ingest_resumes.py` | Implemented | 데이터 버전 고정 문서화 |
| DS.2 | alternative datasets 지원 | `src/backend/services/ingest_resumes.py` | Implemented | 데이터 품질 비교표 추가 |
| DS.3 | CSV/JSON/PDF 포맷 처리 | `src/backend/services/ingest_resumes.py`, `src/backend/services/resume_parsing.py` | Partial | PDF 품질 회귀 테스트 추가 |
| DS.4 | key fields 정규화(skills/exp/edu/category/text) | `src/backend/schemas/candidate.py`, `src/backend/services/ingest_resumes.py` | Implemented | 필드 누락율 모니터링 |
| DS.5 | semantic/filter/ranking 활용 | `src/backend/services/matching_service.py`, `src/backend/repositories/hybrid_retriever.py`, `src/backend/services/scoring_service.py` | Implemented | 직무군별 성능 리포트 추가 |

---

## 6) Reviewer Checklist (Senior+ Self-Review)

| 질문 | 답변 | 근거 |
|---|---|---|
| 핵심 API로 매칭이 가능한가 | Yes | `src/backend/api/jobs.py`, `tests/test_api_endpoints.py` |
| 하이브리드 검색(벡터+키워드+필터)이 동작하는가 | Yes | `src/backend/repositories/hybrid_retriever.py`, `tests/test_retrieval_fallback.py` |
| 멀티에이전트 평가와 가중치 협의가 있는가 | Yes (SDK handoff + fallback) | `src/backend/agents/runtime/service.py`, `src/backend/agents/runtime/sdk_runner.py`, `src/backend/agents/contracts/*` |
| 설명 가능한 결과를 UI까지 확인 가능한가 | Yes | `src/backend/services/match_result_builder.py`, `src/frontend/src/components/*` |
| 평가/편향/성능 요구가 완결됐는가 | No (Partial) | eval(density/custom/potential)과 bias guardrails backend v1은 구현 완료, perf는 자동 아카이브 구현/고부하 자동화 보완 필요 |
| deliverable 산출물 완성도가 충분한가 | No (Partial) | 아키텍처 JPEG/PDF, 발표자료, eval 결과 문서 추가 필요 |

---

## 7) Backlog (Remaining Work)

1. `R2.3` actual fine-tuned embedding 모델 학습/배포 증거(runbook, rollback, A/B)와 calibration 자동화.
2. `R2.5` token 최적화와 `R2.6` 고부하 부하 테스트/벤치마크 자동화 고도화.
3. `R2.7` fairness metric 운영 대시보드 및 경고 정책 튜닝.
4. `AHI.2~AHI.4` feedback loop, analytics dashboard, interview scheduling handoff 구현.
5. `D.1`, `D.4` 제출용 아키텍처 이미지(JPEG/PDF)와 발표자료 완성.
