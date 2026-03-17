# Traceability Matrix

**레뷰어용 요건↔증거 매핑은 [`docs/governance/TRACEABILITY.md`](../docs/governance/TRACEABILITY.md)에서 Problem Definition · Functional Requirements · Reviewer Checklist와 함께 정리되어 있습니다.**

## Status Definition
- `Implemented`: 코드 + 문서 + 실행/테스트 증거가 존재
- `Partial`: 일부 경로는 구현됐지만 운영/검증 증거가 부족
- `Planned`: 설계/백로그 단계

## Core Traceability

| Requirement Group | Implementation Evidence | Validation Evidence | Document Evidence | Status | Gap / Next |
|---|---|---|---|---|---|
| PO / KC (problem/objective/capability) | `src/backend/services/matching_service.py`, `src/backend/services/job_profile_extractor.py`, `src/backend/services/scoring_service.py` | `tests/test_api.py`, `tests/test_retrieval.py` | `requirements/problem_definition.md`, `docs/architecture/system_architecture.md` | Implemented | role-family calibration 리포트 자동화 |
| R1.1-R1.5 (basic matching) | `src/backend/api/jobs.py`, `src/backend/services/retrieval_service.py`, `src/backend/repositories/hybrid_retriever.py` | `tests/test_api.py`, `tests/test_retrieval.py` | `docs/data-flow/candidate_retrieval_flow.md` | Implemented | 검색 품질 회귀 리포트 고도화 |
| R1.6-R1.8 (guardrail/parsing/filter) | `src/backend/core/jd_guardrails.py`, `src/backend/services/ingest_resumes.py`, `src/backend/services/candidate_enricher.py` | `tests/test_api.py` | `docs/security/guardrails_and_validation.md`, `docs/data-flow/resume_ingestion_flow.md` | Implemented | 필터 explainability 필드 추가 |
| R1.9 (API exposure) | `src/backend/main.py`, `src/backend/api/*.py` | `tests/test_api.py` | `README.md` | Implemented | ingestion endpoint auth/rate-limit 정책 문서화 |
| R2.1-R2.2 (evaluation) | `src/eval/eval_runner.py`, `src/eval/metrics.py`, `src/eval/golden_set.jsonl` | `src/eval/test_match_quality.py`, `src/eval/test_skill_coverage.py` | `docs/evaluation/evaluation_plan.md`, `docs/evaluation/evaluation_results.md` | Implemented | query family별 기준선 추가 |
| R2.3 (rerank) | `src/backend/services/cross_encoder_rerank_service.py`, `src/backend/services/matching_service.py` | `tests/test_retrieval.py` | `docs/tradeoffs/design_tradeoffs.md` | Partial | fine-tuned embedding 실험/rollback runbook 필요 |
| R2.4 (LLM-as-judge) | `src/eval/llm_judge_annotations.jsonl`, `src/eval/eval_runner.py` | `src/eval/test_match_quality.py` | `docs/evaluation/evaluation_results.md` | Implemented | sample size 확대 |
| R2.5 (token optimization) | `src/backend/core/settings.py`, `src/backend/services/matching/cache.py`, `src/backend/services/matching_service.py` | `tests/test_api.py` | `docs/governance/cost_control.md` | Partial | 실측 token meter + budget alert 추가 |
| R2.6 (benchmark) | `scripts/run_eval.sh`, `src/eval/reporting.py` | `src/eval/test_query_understanding_quality.py` | `docs/evaluation/evaluation_results.md`, `docs/observability/monitoring.md` | Partial | 고부하 시나리오 자동화 |
| R2.7 (bias/fairness) | `src/backend/services/matching/fairness.py`, `src/backend/core/jd_guardrails.py` | `tests/test_api.py` | `docs/security/guardrails_and_validation.md` | Implemented | fairness drift 대시보드 강화 |
| R2.8 (frontend demo) | `src/frontend/src/App.tsx`, `src/frontend/src/components/*` | manual demo + API tests | `README.md`, `docs/architecture/deployment_architecture.md` | Implemented | UX error state 고도화 |
| HCR.1-HCR.3 (hybrid retrieval) | `src/backend/services/hybrid_retriever.py`, `src/backend/repositories/hybrid_retriever.py` | `tests/test_retrieval.py` | `docs/data-flow/candidate_retrieval_flow.md` | Implemented | fusion weight 실험 자동화 |
| MSA.1-MSA.6 (multi-agent) | `src/backend/agents/contracts/*.py`, `src/backend/agents/runtime/*.py` | `tests/test_api.py` | `docs/agents/multi_agent_pipeline.md` | Implemented | handoff trace 표준화 |
| AHI.1 / AHI.5 | `src/backend/services/match_result_builder.py`, `src/backend/agents/contracts/weight_negotiation_agent.py` | `tests/test_api.py` | `docs/agents/multi_agent_pipeline.md` | Implemented | 조직별 weight profile 버전관리 |
| AHI.2-AHI.4 | `src/backend/api/feedback.py`, `src/backend/services/email_draft_service.py` | `tests/test_api.py` | `requirements/functional_requirements.md` | Partial | analytics/reporting 연동 강화 |
| D.* / DS.* (delivery/dataset) | `scripts/ingest_resumes.py`, `src/backend/services/ingest_resumes.py`, `README.md` | `tests/test_api.py`, `tests/test_retrieval.py`, runbook evidence: `docs/runbooks/evidence/clean_rebuild_*.md` | `docs/architecture/*`, `docs/data-flow/*`, `docs/adr/*`, `docs/runbooks/README.md` | Implemented | 발표 자료/운영 runbook 실행 evidence 누적 |
