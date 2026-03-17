## Requirements Checklist Verification

This document collects evidence paths so you can quickly verify **where** to check compliance for the checklist/requirements referenced in `docs/governance/TRACEABILITY.md` (R2.3, R2.5, R2.6, AHI.2–AHI.4).

---

## R2.3 — Rerank tests and execution path

- **Script**: `scripts/run_rerank_eval.sh`
- **golden subset**: `src/eval/subsets/golden.rerank.jsonl`
- **Related evaluation docs**:
  - `docs/evaluation/evaluation_plan.md`
  - `docs/evaluation/evaluation_results.md`

---

## R2.5 — LangSmith token observability + config-driven optimization

- **Tracing**: LangSmith integration (see `.env.example` and backend settings for env/config)
- **Config-driven control (e.g., budget/caching)**:
  - `src/backend/core/settings.py`
  - `src/backend/services/matching/cache.py`

---

## R2.6 — Throughput benchmark / performance evidence

- **Performance output (sample artifact)**: `src/eval/outputs/short_eval/manual/agent6_livejson_top4_v4_judged/performance_eval.json`
- **Architecture scalability evidence (docs)**:
  - `docs/architecture/deployment_architecture.md`

---

## AHI.2–AHI.4 — Feedback / analytics / handoff (interview + email draft)

- **API/service implementation evidence**:
  - `src/backend/api/`
  - `src/backend/services/`
- **End-to-end flow docs**:
  - `docs/data-flow/candidate_retrieval_flow.md`
  - `docs/data-flow/resume_ingestion_flow.md`

