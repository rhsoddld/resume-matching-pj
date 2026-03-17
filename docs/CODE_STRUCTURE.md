# Code Structure & Extensibility Guide

This document explains the project’s folder structure and provides an extensibility guide for adding new functionality or swapping components.

## Folder Structure

### Root Directory

- **`README.md`**: project overview, quick start, core commands, documentation entry points
- **`requirements.txt`**: Python dependencies (FastAPI, PyMongo, PyMilvus, OpenAI, spaCy, DeepEval, etc.)
- **`docker-compose.yml`**: local dev services (backend, frontend, MongoDB, Milvus, etc.)
- **`pytest.ini`**: pytest configuration
- **`config/`**: YAML configuration (skill taxonomy, aliases, job filters, etc.)
- **`docs/`**: architecture, ADRs, data flows, evaluation, observability docs
- **`src/`**: backend, frontend, and evaluation module source
- **`scripts/`**: ingestion/eval/golden set maintenance scripts
- **`tests/`**: unit/integration tests
- **`ops/`**: shared operational code (logging, middleware, etc.) packaged separately from backend

### `config/` Directory

- **`skill_taxonomy.yml`**: skill hierarchy and job-family mapping
- **`skill_aliases.yml`**: skill alias normalization
- **`skill_capability_phrases.yml`**: capability phrase mapping
- **`skill_review_required.yml`**, **`versioned_skills.yml`**, **`skill_role_candidates.yml`**: auxiliary skill/role data
- **`job_filters.yml`**: filter options source (job family, education, region, industry, etc.)

### `src/` Directory

- **`backend/`**: FastAPI app, API routers, services, agents, repositories, schemas
- **`frontend/`**: React (Vite) + TypeScript web UI
- **`eval/`**: evaluation runner, golden set, LLM-as-Judge, subset creation, etc.

### `src/backend/` Directory

| Path | Description |
|------|------|
| **`main.py`** | FastAPI entrypoint: lifespan, middleware, `/api/health`, `/api/ready`, router registration |
| **`api/`** | REST routers: `candidates`, `jobs`, `ingestion`, `feedback` |
| **`core/`** | settings, DB, vector store, exceptions, startup, observability, filter_options, model_routing, JD guardrails, providers |
| **`schemas/`** | Pydantic models: `job.py` (JobMatchRequest/Response, QueryUnderstandingProfile, etc.), `candidate.py`, `ingestion.py`, `feedback.py` |
| **`repositories/`** | `mongo_repo.py` (candidate queries + filter-options API entry), `hybrid_retriever.py` (re-export; real impl in `services/hybrid_retriever.py`), `session_repo.py` (JD sessions) |
| **`services/`** | core services: `matching_service.py` (orchestration), `hybrid_retriever.py`, `retrieval_service.py`, `job_profile_extractor.py`, `match_result_builder.py`, `scoring_service.py`, `cross_encoder_rerank_service.py`, `query_fallback_service.py`, `candidate_enricher.py`, `ingest_resumes.py`, `resume_parsing.py`, `email_draft_service.py`, etc. |
| **`services/job_profile/`** | JD profile helpers: signal quality, signal dedupe, etc. |
| **`services/skill_ontology/`** | skill ontology loader, normalization, runtime types/constants |
| **`services/ingestion/`** | resume ingestion pipeline: preprocessing, transforms, state, constants |
| **`services/matching/`** | cache, fairness, evaluation, profile merging, rerank_policy |
| **`services/retrieval/`** | `hybrid_scoring.py` (fusion/keyword/metadata scoring) |
| **`agents/`** | multi-agent pipeline |
| **`agents/contracts/`** | agent contracts: skill/experience/technical/culture/orchestrator/ranking/weight_negotiation |
| **`agents/runtime/`** | `service.py` (orchestration entry), `sdk_runner.py`, `live_runner.py`, `heuristics.py`, candidate_mapper, helpers, prompts, models, types |

### `src/frontend/` Directory

- **`src/App.tsx`**, **`main.tsx`**, **`index.html`**: app entry points
- **`src/api/`**: `match.ts`, `feedback.ts` — backend API calls
- **`src/components/`**: `JobRequirementForm.tsx`, `MatchForm.tsx`, `CandidateResults.tsx`, `CandidateRow.tsx`, `CandidateCard.tsx`, `CandidateDetailModal.tsx`, `MatchScorePill.tsx`, `ExplainabilityPanel.tsx`, `RecruiterHero.tsx`, `BiasGuardrailBanner.tsx`, `ResultCard.tsx`
- **`src/types.ts`**: shared types
- **`src/utils/agentEvaluation.ts`**: agent evaluation utilities
- **`theme.css`**, **`index.css`**: styling
- **`vite.config.ts`**, **`package.json`**, **`Dockerfile`**, **`nginx.conf`**: build/deployment

### `src/eval/` Directory

- **`eval_runner.py`**, **`config.py`**: eval execution and configuration
- **`golden_set_maintenance.py`**, **`create_mode_subsets.py`**: golden set maintenance
- **`generate_llm_judge_annotations.py`**: generate LLM-as-Judge annotations
- **`subsets/`**: golden set subsets (e.g. `golden.agent.jsonl`)
- **`outputs/`**: evaluation output archives

### `docs/` Directory

- **`architecture/`**: system_architecture.md, deployment_architecture.md
- **`adr/`**: ADR-001 ~ ADR-009 (vector-db, embedding, hybrid-retrieval, agent-orchestration, deterministic-query-understanding, rerank-policy, ingestion-parsing-rule-based, bias-fairness-guardrails, observability-strategy)
- **`data-flow/`**: resume_ingestion_flow.md, candidate_retrieval_flow.md, test_datasets_and_commands.md
- **`agents/`**: multi_agent_pipeline.md
- **`evaluation/`**: evaluation_plan.md, evaluation_results.md, llm_judge_design.md, golden_set_alignment.md, etc.
- **`observability/`**: logging_metrics.md, monitoring.md
- **`governance/`**: cost_control.md
- **`design/`**: design decisions/rationale (key decisions, rationale)
- **`guides/`**: onboarding/flow guides (core flows, scoring)
- **`deep-dive/`**: deep references (codebase meaning, etc.)
- **`docs/design/key-design-decisions.md`**: key design decisions summary (pair with this doc)
- **`CODE_STRUCTURE.md`**: this document

### `scripts/` Directory

- **`ingest_resumes.py`**: resume ingestion (source: all, target: mongo/milvus)
- **`run_eval.sh`**, **`run_retrieval_eval.sh`**, **`run_rerank_eval.sh`**: run evaluations
- **`update_golden_set.sh`**, **`regen_golden_set.sh`**: update/regenerate golden set

### `tests/` Directory

- **`test_api.py`**, **`test_retrieval.py`**, **`test_scoring_service.py`**, **`test_hybrid_scoring.py`**, **`test_ingestion_preprocessing.py`**, **`test_golden_set_alignment.py`**, **`test_regen_golden_set.py`**, **`test_job_profile_extractor.py`**, **`test_sdk_runner_and_rerank_policy.py`**, **`test_resume_parsing.py`**, **`test_matching_evaluation.py`**, etc.

### `ops/` Directory (shared operations)

- **`logging.py`**: configure_logging, get_logger
- **`middleware.py`**: RequestIdMiddleware, APILoggingMiddleware
- **`mongo_handler.py`**: (optional) MongoDB log handler

---

## Extensibility

The codebase is organized for modularity and extensibility, making it relatively straightforward to add features or swap components.

### 1. Change embedding model

- **Location**: `backend.core.settings` (`openai_embedding_model`), `backend.services.retrieval_service.RetrievalService` (OpenAI Embeddings API calls)
- **How**:
  1. Change `OPENAI_EMBEDDING_MODEL` in `.env`, or implement a service for another embedding provider
  2. If embedding dimensions change, update Milvus collection `dim` and re-index
  3. Configure rerank embedding model separately via `rerank_embedding_model`

### 2. Swap vector DB / document store

- **Vector**: Milvus calls are wrapped in `backend.core.vector_store`. To swap vector DBs, implement the same interface (search_embeddings, etc.) and wire it into `retrieval_service` / `hybrid_retriever`.
- **Document**: MongoDB queries are in `backend.repositories.mongo_repo`. To swap stores, implement a new store with the same function signatures and update call sites.

### 3. Extend query understanding (deterministic)

- **Location**: `backend.services.job_profile_extractor` (JD → JobProfile), `backend.core.filter_options` (filter options loader), `config/*.yml`
- **How**:
  1. Add new signal types/rules by extending `job_profile_extractor` and `job_profile/signals`
  2. Add filter options by editing `config/job_filters.yml`. The API calls `repositories.mongo_repo.get_filter_options()`, but actual data is loaded via `core.filter_options` from YAML (merging `job_filters.yml` + `skill_taxonomy.yml`).
  3. Query fallback is already wired in `query_fallback_service` using confidence/unknown_ratio thresholds; adjust thresholds to change behavior.

### 4. Tune hybrid retrieval / fusion

- **Location**: `backend.services.hybrid_retriever.HybridRetriever`, `backend.services.retrieval.hybrid_scoring`
- **How**:
  1. Adjust fusion weights and keyword/metadata scoring formulas in `hybrid_scoring`
  2. Update keyword candidate pool generation in `HybridRetriever._search_keyword_candidates`, `_merge_fusion_hits`, etc.
  3. Industry/category mapping is in `hybrid_scoring.INDUSTRY_CATEGORY_MAP` and settings.

### 5. Change rerank policy / models

- **Location**: `backend.services.matching.rerank_policy` (gate conditions, top_n, model routing), `backend.services.cross_encoder_rerank_service`, `backend.core.model_routing`
- **How**:
  1. Toggle rerank via `RERANK_ENABLED` and `should_apply_rerank` conditions
  2. Change gate behavior via `rerank_gate_*` settings and logic in `rerank_policy`
  3. LLM rerank vs embedding rerank: `rerank_mode`, swap the service implementation or extend routing

### 6. Extend multi-agent evaluation / negotiation chain

- **Location**: `backend.agents.contracts` (agent classes), `backend.agents.runtime.service`, `sdk_runner`, `live_runner`, `heuristics`
- **How**:
  1. Add a new agent: implement a new agent class in contracts, call it from orchestration, and merge into the ScorePack
  2. Change negotiation logic: modify `weight_negotiation_agent` and recruiter/hiring-manager proposal formats
  3. Change fallback order: adjust SDK → live_json → heuristic chain in runtime

### 7. Change fairness / bias policies

- **Location**: `backend.services.matching.fairness`, `backend.core.jd_guardrails`
- **How**: update `fairness_*` settings and add/modify checks in the fairness module. The frontend only displays warnings via `BiasGuardrailBanner`, so keeping the backend response schema consistent is sufficient.

### 8. Add new API endpoints

- **Location**: `backend.api` (new router or add to existing `candidates`, `jobs`, `ingestion`, `feedback`)
- **How**: define a new route in FastAPI routers and register via `app.include_router` in `main.py`

### 9. Add frontend components / pages

- **Location**: `src/frontend/src/components/`, `src/api/`
- **How**: create a component and connect it in `App.tsx` (or an existing page); add API calls in `api/`

### 10. Extend the evaluation pipeline

- **Location**: `src/eval/` (eval_runner, golden set, LLM judge scripts)
- **How**: add steps to eval_runner and related scripts for new metrics/judge criteria; keep golden set JSONL backward compatible

---

## Documentation entry points (linked from README)

- Architecture: [docs/architecture/system_architecture.md](./architecture/system_architecture.md)
- Key design decisions: [docs/design/key-design-decisions.md](./design/key-design-decisions.md)
- Design rationale (ontology/cost/eval): [docs/design/rationale-ontology-eval-cost.md](./design/rationale-ontology-eval-cost.md)
- Core flows guide: [docs/guides/codebase-core-flows.md](./guides/codebase-core-flows.md)
- End-to-end scoring flow: [docs/guides/scoring-flow-guide.md](./guides/scoring-flow-guide.md)
- Codebase meaning (deep dive): [docs/deep-dive/codebase-meaning-reference.md](./deep-dive/codebase-meaning-reference.md)
- Code structure & extensibility: **docs/CODE_STRUCTURE.md** (this document)
- Deployment: [docs/architecture/deployment_architecture.md](./architecture/deployment_architecture.md)
- Data flow: [docs/data-flow/resume_ingestion_flow.md](./data-flow/resume_ingestion_flow.md), [docs/data-flow/candidate_retrieval_flow.md](./data-flow/candidate_retrieval_flow.md)
- Agents: [docs/agents/multi_agent_pipeline.md](./agents/multi_agent_pipeline.md)
- Evaluation: [docs/evaluation/evaluation_plan.md](./evaluation/evaluation_plan.md), [docs/evaluation/evaluation_results.md](./evaluation/evaluation_results.md)
