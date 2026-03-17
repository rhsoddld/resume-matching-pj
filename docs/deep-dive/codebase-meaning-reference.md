# Deep dive: what the codebase means

**Purpose:** This document explains what each directory/file in the repo **means**, so you can understand the system quickly from both business and technical perspectives.  
For flows/sequences, see [Code structure & core flows](../guides/codebase-core-flows.md) and [End-to-end scoring flow](../guides/scoring-flow-guide.md).

---

## 1. What this project is (one sentence)

It is a system where **you enter a job description (JD), retrieve candidates semantically from a resume database, evaluate each candidate via agents across skill/experience/technical/culture fit, and return an explainable ranking with scores**.

- **Offline:** parse/normalize resume CSV/text and ingest into MongoDB (profiles) + Milvus (embeddings)
- **Online:** JD → structured query (query understanding) → hybrid retrieval (vector + keyword + metadata) → optional rerank → agent evaluation → weight negotiation → final score + explanation + fairness warnings

---

## 2. Repo root: what each file/folder means

| Path | Meaning |
|------|------|
| **README.md** | Overview, setup, core commands, and doc entry points. |
| **requirements.txt** | Python runtime dependencies (FastAPI, PyMongo, PyMilvus, OpenAI, spaCy, etc.). |
| **docker-compose.yml** | Local stack definition (backend, frontend, MongoDB, Milvus, Attu). |
| **pytest.ini** | pytest configuration (markers, paths, etc.). |
| **.env.example** | Environment variable template. Copy to `.env` and fill in keys/URIs (do not commit). |
| **config/** | **Configuration data**: skill taxonomy, aliases, job filters, etc. Inputs to query understanding and retrieval. |
| **docs/** | **All documentation**: architecture, ADRs, data flows, agents, evaluation, governance, etc. |
| **src/** | **Source code**: backend (FastAPI), frontend (React), eval runner. |
| **scripts/** | **CLI/batch scripts**: ingestion, eval runs, golden set maintenance. |
| **tests/** | **Unit/integration tests**: API, retrieval, scoring, ingestion, golden set, etc. |
| **ops/** | **Shared operational code**: logging, middleware, optional Mongo log handler (separate package from backend). |
| **requirements/** | Requirements artifacts: problem definition, functional requirements, traceability matrices, etc. |

---

## 3. `config/`: what each config file means

All of these are **YAML** files and are **deterministic data** used by query understanding and retrieval **without an LLM**.

| File | Meaning |
|------|------|
| **skill_taxonomy.yml** | Skill hierarchy + job-family mapping. Defines which skills belong to which families/roles. Used for role/skill extraction from JDs. |
| **skill_aliases.yml** | Skill alias → canonical skill mapping (e.g. “Python3” → “python”) to keep retrieval/matching consistent. |
| **skill_capability_phrases.yml** | Capability phrase → skill mapping. Encodes how to treat phrases like “systems integration experience” as skill signals. |
| **skill_review_required.yml**, **versioned_skills.yml**, **skill_role_candidates.yml** | Auxiliary skill/role data: review-required skills, versioning, role candidates, etc. |
| **job_filters.yml** | Source of **filter options** (job family/category, education, region, industry, etc.) used to populate filter lists in the API. |

---

## 4. `src/backend/`: what the backend code means

### 4.1 Entrypoint: `main.py`

- **Meaning:** the **single entrypoint** for the FastAPI app.
- **What it does:** creates the app; lifespan startup (calls `warmup_infrastructure`); middleware (CORS, RequestId, API logging); exception handlers (`AppError` + generic exceptions); `/api/health` and `/api/ready` (Mongo/Milvus connectivity checks); registers routers for `candidates`, `jobs`, `ingestion`, `feedback`.

### 4.2 `api/`: what the REST endpoints mean

| File | Meaning |
|------|------|
| **jobs.py** | **Matching + JD-related API.** `POST /api/jobs/match`, match/stream, extract-pdf, draft-email, etc. User requests enter here. |
| **candidates.py** | Candidate listing and filter option endpoints (category/education/region/industry). |
| **ingestion.py** | `POST /api/ingestion/resumes` — batch resume ingestion API (HTTP alternative to CLI). |
| **feedback.py** | Collect feedback on match results. |

### 4.3 `core/`: infrastructure, settings, and shared modules

| File | Meaning |
|------|------|
| **settings.py** | Env-driven **global settings**: DB URI, Milvus URI, cache TTLs, rerank/agent flags and limits, etc. |
| **database.py** | Obtain **MongoDB connections** (singleton client). |
| **vector_store.py** | **Milvus wrapper**: connection, collection checks, embedding search, etc. Swapping vector DBs primarily means matching this interface. |
| **filter_options.py** | Load **filter options** by merging `job_filters.yml` + `skill_taxonomy.yml`. Used by API and query understanding. |
| **jd_guardrails.py** | JD text **safety/sanitization** checks (sensitive info, excessive length, etc.). |
| **model_routing.py** | **Rerank model routing**: decide which model to use per condition (default vs high-quality ambiguity/tie-break, etc.). |
| **observability.py** | Tracing/spans (e.g. `traceable_op`). |
| **exceptions.py** | Shared app exceptions such as `AppError`. |
| **startup.py** | Startup **infrastructure warmup** (DB, Milvus, skill ontology, etc.). |
| **collections.py** | Shared collection utilities (e.g. list dedupe). |
| **providers.py** | Runtime provider injection (e.g. skill ontology provider). |

### 4.4 `schemas/`: request/response and domain models

| File | Meaning |
|------|------|
| **job.py** | **Match request/response + query understanding output.** `JobMatchRequest`, `JobMatchResponse`, `QueryUnderstandingProfile`, `JobMatchCandidate`, `FairnessAudit`, etc. Defines the API contract and internal transfer structures. |
| **candidate.py** | Candidate schema used across API and storage layers. |
| **ingestion.py** | Ingestion API request/response schemas. |
| **feedback.py** | Feedback API schemas. |

### 4.5 `repositories/`: repository layer

| File | Meaning |
|------|------|
| **mongo_repo.py** | **MongoDB access.** Query by candidate ID, load filter options (`get_filter_options`), etc. Real queries happen here. |
| **hybrid_retriever.py** | **Re-export** of `services/hybrid_retriever`. Routers/services import HybridRetriever through this path. |
| **session_repo.py** | Store/load JD sessions (matching session state). |

### 4.6 `services/`: what the business logic means (core)

| File | Meaning |
|------|------|
| **matching_service.py** | **Matching pipeline orchestration.** cache → build JobProfile → retrieval → enrichment → shortlist → scoring/agents → fairness → response. The **entrypoint** for the end-to-end flow. |
| **job_profile_extractor.py** | **JD → structured query (JobProfile).** Deterministic rules + taxonomy. Outputs role, required/related skills, seniority, lexical_query, query_text_for_embedding, filters, confidence, etc. Improves cost/consistency without an LLM. |
| **hybrid_retriever.py** | **Hybrid retrieval.** Keyword (always, Mongo) + vector (when available, Milvus) + metadata are fused into candidate lists. Includes keyword-only fallback on vector failure. |
| **retrieval_service.py** | **Embeddings + Milvus search.** Embeds JD text and searches vector DB by similarity. |
| **candidate_enricher.py** | **Hit → enrich with Mongo docs.** Attach full candidate docs to hits and apply metadata filters (experience, education, region, industry, etc.) to drop non-matching candidates. |
| **cross_encoder_rerank_service.py** | **Rerank service.** Rerank shortlisted candidates (Cross-Encoder or LLM depending on settings). Runs only when the gate passes. |
| **scoring_service.py** | **Final scoring.** Deterministic score (skill overlap, experience fit, seniority, category, etc.), blend with agent-weighted scores, apply must_have_penalty. Core scoring implementation. |
| **match_result_builder.py** | **Response DTO assembly.** Build `JobMatchCandidate` per candidate (scores, explanation, evidence, bias_warnings, etc.). |
| **query_fallback_service.py** | **Query-understanding fallback.** Alternative query/strategy when confidence/unknown_ratio is poor. |
| **ingest_resumes.py** | **Resume ingestion orchestration.** Load CSV sources → parse/normalize → ingest into Mongo/Milvus. Called by `scripts/ingest_resumes.py`. |
| **resume_parsing.py** | **Resume parsing.** Extract skills/experience/education via rules/regex, spaCy, dateparser. |
| **email_draft_service.py** | Hiring communication utilities such as email drafting. |
| **eval_adapter.py** | **Adapter** used by eval runner to call backend matching logic. |

#### `services/` subpackages

| Path | Meaning |
|------|------|
| **job_profile/** | JobProfile helpers for **signal quality + dedupe** (e.g. `signals.py`). |
| **skill_ontology/** | **Skill ontology** loader, normalization, runtime types/constants. Reads YAML to provide hierarchy and aliases. |
| **ingestion/** | Resume **preprocessing, transforms, state, constants** (pipeline stages, state machine, mapping constants). |
| **matching/** | **cache** (LRU+TTL), **fairness** warnings, **evaluation** (select agent-eval indices), **profile merging**, **rerank_policy** (gate/top_n/pool size). |
| **retrieval/** | **hybrid_scoring**: fusion formula for vector/keyword/metadata scores (e.g. 0.48/0.37/0.15). |

### 4.7 `agents/`: what agents mean

- **Meaning:** a **multi-agent pipeline** that evaluates each (JD, candidate) pair across **skill/experience/technical/culture** dimensions and negotiates **Recruiter vs Hiring Manager** weights to produce final weighted scores and explanations.

#### `agents/contracts/`: agent “contracts” (I/O definitions)

| File | Meaning |
|------|------|
| **skill_agent.py** | **Skill matching agent.** Align JD required skills vs candidate skills; outputs score, matched/missing skills, evidence. |
| **experience_agent.py** | **Experience evaluation agent.** Compare required years/seniority vs candidate experience; outputs score and career trajectory signals. |
| **technical_agent.py** | **Technical depth / engineering experience** evaluation (e.g. stack coverage, vector similarity signals). |
| **culture_agent.py** | **Culture fit / domain alignment** (category/role alignment, collaboration signals, etc.). |
| **orchestrator.py** | Orchestration contract for running the 4 agents (I/O definition). |
| **ranking_agent.py** | Build **weighted score + explanation** by combining score pack with weights. |
| **weight_negotiation_agent.py** | Negotiate **final weights** from Recruiter/Hiring Manager proposals. |

#### `agents/runtime/`: runtime execution

| File | Meaning |
|------|------|
| **service.py** | **AgentOrchestrationService.** Pipeline entrypoint. `run_for_candidate()` runs 4 agents per candidate, then Recruiter → HiringManager → WeightNegotiation. |
| **sdk_runner.py** | **SDK handoff** path: run Recruiter → HiringManager → Negotiation via SDK calls (primary path). |
| **live_runner.py** | **Live JSON** fallback: direct LLM call that returns JSON when SDK fails. |
| **heuristics.py** | **Rule-based fallback:** compute skill/experience/technical/culture scores via formulas when SDK and Live JSON fail. |
| **candidate_mapper.py** | Build the **candidate input bundle** passed to agents (JD + JobProfile + hit + doc). |
| **helpers.py** | Scoring utilities like `compute_skill_score`, `compute_experience_fit`, `compute_seniority_fit`, `compute_weighted_score`. |
| **prompts.py** | Prompt versions/content for agents and negotiation. |
| **models.py**, **types.py** | Agent I/O types and models. |

---

## 5. `src/frontend/`: what the frontend means

- **Meaning:** **React (Vite) + TypeScript** web UI for JD entry, filter selection, match requests, and displaying results/scores/explanations/fairness warnings.

| Path/file | Meaning |
|-----------|------|
| **src/App.tsx**, **main.tsx**, **index.html** | App entrypoints and routing. |
| **src/api/** | `match.ts`, `feedback.ts` — backend match/feedback API calls. |
| **src/components/** | JobRequirementForm/MatchForm (JD+filters), CandidateResults/Row/Card/DetailModal (results list/detail), MatchScorePill/ExplainabilityPanel (score/explanation), RecruiterHero/BiasGuardrailBanner/ResultCard (UI blocks). |
| **src/types.ts** | Shared frontend types (API responses, etc.). |
| **src/utils/agentEvaluation.ts** | Utilities for shaping/displaying agent evaluation results. |
| **theme.css**, **index.css** | Global/theme styles. |
| **vite.config.ts**, **package.json**, **Dockerfile**, **nginx.conf** | Build/deployment configuration. |

---

## 6. `src/eval/`: what the eval code means

- **Meaning:** an offline pipeline that evaluates **retrieval / rerank / agent** quality using a **golden set** and **LLM-as-Judge**.

| File | Meaning |
|------|------|
| **eval_runner.py** | Eval entrypoint: run retrieval/rerank/agent metrics. |
| **config.py** | Eval configuration (paths, models, golden set, etc.). |
| **golden_set_maintenance.py** | Golden set maintenance (add/edit/validate). |
| **create_mode_subsets.py** | Create golden-set subsets (e.g. agent-only). |
| **generate_llm_judge_annotations.py** | Generate LLM-as-Judge annotations. |
| **regen_golden_set.py** | Golden set regeneration logic. |
| **reporting.py**, **metrics.py** | Reporting and metrics computation. |
| **subsets/** | Golden set JSONL subsets (e.g. `golden.agent.jsonl`). |
| **outputs/** | Archived evaluation outputs. |

---

## 7. `scripts/`: what the scripts mean

| File | Meaning |
|------|------|
| **ingest_resumes.py** | **Resume ingestion CLI.** Options like `--source all`, `--target mongo`/`milvus`, `--suri-limit`, etc. Ingest to MongoDB, then build Milvus index (`--milvus-from-mongo`). |
| **run_eval.sh** | Run the **full evaluation** (including agents). |
| **run_retrieval_eval.sh** | Retrieval-only evaluation. |
| **run_rerank_eval.sh** | Rerank-only evaluation. |
| **update_golden_set.sh**, **regen_golden_set.sh** | Update/regenerate the golden set. |

---

## 8. `tests/`: what the tests mean

Each file validates the behavior of its corresponding module/flow.

| File | Meaning |
|------|------|
| **test_api.py** | Tests API endpoints (health, match, etc.). |
| **test_retrieval.py** | Tests retrieval behavior (hybrid, keyword, vector). |
| **test_scoring_service.py** | Tests `scoring_service` scoring, blending, penalties. |
| **test_hybrid_scoring.py** | Tests fusion formula and weights. |
| **test_ingestion_preprocessing.py** | Tests ingestion preprocessing. |
| **test_golden_set_alignment.py**, **test_regen_golden_set.py** | Tests golden-set alignment/regeneration. |
| **test_job_profile_extractor.py** | Tests JobProfile extraction (roles, skills, seniority, etc.). |
| **test_sdk_runner_and_rerank_policy.py** | Tests SDK runner and rerank policy. |
| **test_resume_parsing.py** | Tests resume parsing. |
| **test_matching_evaluation.py** | Tests matching + agent evaluation flow. |

---

## 9. `ops/`: what shared operations mean

| File | Meaning |
|------|------|
| **logging.py** | Logging configuration and `get_logger` (structured logs and levels). |
| **middleware.py** | `RequestIdMiddleware` (per-request ID), `APILoggingMiddleware` (request/response logging). |
| **mongo_handler.py** | (optional) MongoDB log handler used when writing logs to MongoDB. |

---

## 10. Recommended reading order

1. **Meaning overview:** use this doc to learn what each directory/file is responsible for.
2. **Request → response:** see the matching pipeline diagram/table in [Code structure & core flows](../guides/codebase-core-flows.md).
3. **Counts and formulas:** use [End-to-end scoring flow](../guides/scoring-flow-guide.md) to track how many candidates are filtered and how scores are computed.
4. **Implementation trace:**  
   - `api/jobs.py` → `MatchingService.match_jobs()` → `_build_query_profile`(job_profile_extractor) → `_retrieve_candidates`(hybrid_retriever) → `_enrich_candidates`(candidate_enricher) → `_shortlist_candidates`(rerank_policy, cross_encoder_rerank_service) → `_score_candidates`(scoring_service, agents, match_result_builder) → `_run_fairness_guardrails`.
5. **Extensibility and config:** see Extensibility and config notes in [CODE_STRUCTURE.md](../CODE_STRUCTURE.md).

---

## 11. Related docs

- [Code structure & core flows](../guides/codebase-core-flows.md) — diagrams and stage owners
- [End-to-end scoring flow](../guides/scoring-flow-guide.md) — scoring stages, formulas, head counts
- [CODE_STRUCTURE.md](../CODE_STRUCTURE.md) — folder structure and extensibility
- [architecture/system_architecture.md](../architecture/system_architecture.md) — system architecture and layers
- [data-flow/resume_ingestion_flow.md](../data-flow/resume_ingestion_flow.md) — resume ingestion flow
- [data-flow/candidate_retrieval_flow.md](../data-flow/candidate_retrieval_flow.md) — candidate retrieval/matching flow
- [agents/multi_agent_pipeline.md](../agents/multi_agent_pipeline.md) — agent pipeline detail
