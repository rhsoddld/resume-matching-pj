# Traceability — Reviewer Guide

This document maps Problem Definition, Functional Requirements, implementation/verification evidence, and the Reviewer Checklist so **reviewers** can verify requirement satisfaction in one place.

**Related documents**
- Requirements: [`requirements/problem_definition.md`](../../requirements/problem_definition.md), [`requirements/functional_requirements.md`](../../requirements/functional_requirements.md)
- Implementation matrix: [`requirements/traceability_matrix.md`](../../requirements/traceability_matrix.md)
- Checklist: [`requirements/Reviewer_Checklist.md`](../../requirements/Reviewer_Checklist.md)
- Case study source: `requirements/case-study.pdf`

---

## 1. Requirement satisfaction summary

| Area | Content | Status |
|-----|------|------|
| **Problem Definition** | PO.1–PO.6, OBJ.1–OBJ.5 | ✅ Mapped to implementation/docs |
| **Functional Requirements** | R1.*, R2.*, HCR.*, MSA.*, AHI.*, D.*, DS.* | ✅ All Implemented (per-ID mapping §3) |
| **Reviewer Checklist** | 5 areas (files/architecture/implementation/testing/verdict) | ✅ Evidence links documented |
| **Dependencies** | `requirements.txt` (FastAPI, Milvus, OpenAI, DeepEval, etc.) | ✅ Aligned with project |

---

## 2. Problem Definition → Functional Requirements mapping

### 2.1 Problem statements (PO.*) → corresponding requirements

| PO ID | Problem statement | Corresponding requirements |
|-------|-----------|----------------|
| PO.1 | Difficulty evaluating technical fit, proficiency, career context | R1.2, R1.5, MSA.2, MSA.3, HCR.1 |
| PO.2 | Quality degradation when location/education/industry metadata not interpreted | R1.4, R1.8, HCR.2, DS.4, DS.5 |
| PO.3 | Transferable/adjacent skill missed with exact match only | R1.2, HCR.1, R2.3 |
| PO.4 | Parsing quality variance across CSV/PDF/unstructured formats | R1.7, DS.3, DS.4 |
| PO.5 | Score alone insufficient for trust; need explainable evidence | AHI.1, R2.4, MSA.6 |
| PO.6 | Inefficiency and inconsistency of manual review at scale | R1.1, HCR.*, MSA.*, R2.6 |

### 2.2 Objectives (OBJ.*) → corresponding requirements

| OBJ ID | Objective | Corresponding requirements |
|--------|------|----------------|
| OBJ.1 | JD → structured query profile; stable retrieval signals | R1.6, R1.9 (query understanding path) |
| OBJ.2 | Prioritize relevant recall at retrieval stage | R1.1, HCR.1, HCR.2, HCR.3 |
| OBJ.3 | skill/experience/technical/culture evaluation + weight policy | MSA.1–MSA.6, AHI.5 |
| OBJ.4 | Explainability with score breakdown, evidence, gaps | AHI.1, R2.4 |
| OBJ.5 | Reproducible metrics for quality/performance/reliability/fairness | R2.1, R2.2, R2.4, R2.6, R2.7, D.2 |

---

## 3. Functional Requirements → implementation/verification evidence (detail)

Code paths, docs, and status are synced with [`requirements/traceability_matrix.md`](../../requirements/traceability_matrix.md). Below is a group-level summary.

### 3.1 R1.* (Basic)

| ID | Requirement | Implementation evidence | Verification evidence | Status |
|----|----------|-----------|-----------|------|
| R1.1 | Basic RAG candidate retrieval | `retrieval_service.py`, `hybrid_retriever.py` | `test_api.py`, `test_retrieval.py` | Implemented |
| R1.2 | Skills-based semantic matching | `matching_service.py`, `scoring_service.py` | same | Implemented |
| R1.3 | Skill overlap baseline ranking | `scoring_service.py`, `matching_service.py` | same | Implemented |
| R1.4 | Job category filtering | `filter_options.py`, job API | `test_api.py` | Implemented |
| R1.5 | Job-resume alignment scoring | `scoring_service.py`, `match_result_builder.py` | same | Implemented |
| R1.6 | JD guardrails | `jd_guardrails.py` | `test_api.py` | Implemented |
| R1.7 | Resume parsing/normalization validation | `ingest_resumes.py`, `candidate_enricher.py` | `test_api.py` | Implemented |
| R1.8 | Metadata filtering | `filter_options.py`, API schema | `test_api.py` | Implemented |
| R1.9 | API endpoint provision | `main.py`, `api/*.py` | `test_api.py` | Implemented |

### 3.2 R2.* (Advanced)

| ID | Requirement | Implementation evidence | Verification evidence | Status |
|----|----------|-----------|-----------|------|
| R2.1 | DeepEval quality/diversity | `eval_runner.py`, `metrics.py`, `golden_set.jsonl` | `test_match_quality.py`, `test_skill_coverage.py` | Implemented |
| R2.2 | Custom eval (skill/experience/culture/potential) | `eval_runner.py`, eval design docs | same | Implemented |
| R2.3 | Rerank enhancement | `cross_encoder_rerank_service.py`, `matching_service.py`, `run_rerank_eval.sh`, `golden.rerank.jsonl` | `test_retrieval.py`, `test_sdk_runner_and_rerank_policy.py` | Implemented |
| R2.4 | LLM-as-Judge | `llm_judge_annotations.jsonl`, `eval_runner.py` | `test_match_quality.py` | Implemented |
| R2.5 | Token optimization | `settings.py`, `cache.py`, `matching_service.py`, LangSmith(ADR-009) | `test_api.py`, `cost_control.md` | Implemented |
| R2.6 | Throughput/latency benchmark | `run_eval.sh`, `reporting.py`, deployment scalability design | `evaluation_results.md`, `monitoring.md` | Implemented |
| R2.7 | Bias/fairness guardrail | `fairness.py`, `jd_guardrails.py` | `test_api.py` | Implemented |
| R2.8 | Reviewer demo frontend | `frontend/src/App.tsx`, `components/*` | README, manual demo | Implemented |

### 3.3 HCR.* (Hybrid Retrieval)

| ID | Requirement | Implementation evidence | Verification evidence | Status |
|----|----------|-----------|-----------|------|
| HCR.1 | Vector + keyword hybrid | `hybrid_retriever.py` (services + repositories) | `test_retrieval.py` | Implemented |
| HCR.2 | Dynamic filtering | `filter_options.py`, API | `test_retrieval.py` | Implemented |
| HCR.3 | Shortlist reranking | `matching_service.py`, rerank path | `test_retrieval.py` | Implemented |

### 3.4 MSA.* (Multi-Stage Agent)

| ID | Requirement | Implementation evidence | Verification evidence | Status |
|----|----------|-----------|-----------|------|
| MSA.1 | Multi-agent orchestration | `agents/contracts/*`, `agents/runtime/*` | `test_api.py` | Implemented |
| MSA.2–MSA.5 | Skill / Experience / Technical / Culture Agent | same | same | Implemented |
| MSA.6 | Agent score pack → final ranking | `match_result_builder.py`, ranking engine | `test_api.py` | Implemented |

### 3.5 AHI.* (Additional Hiring Intelligence)

| ID | Requirement | Implementation evidence | Verification evidence | Status |
|----|----------|-----------|-----------|------|
| AHI.1 | Explainable ranking, score breakdown | `match_result_builder.py` | `test_api.py` | Implemented |
| AHI.2 | Recruiter feedback loop | `api/feedback.py` | `test_api.py` | Implemented |
| AHI.3 | Hiring analytics observability | logs, metrics, LangSmith traces | - | Implemented |
| AHI.4 | Interview scheduling/email draft handoff | `email_draft_service.py` | `test_api.py` | Implemented |
| AHI.5 | Recruiter/HiringManager A2A negotiation | `weight_negotiation_agent.py` | `test_api.py` | Implemented |

### 3.6 D.* / DS.* (Deliverables & Dataset)

| ID | Requirement | Implementation/doc evidence | Status |
|----|----------|----------------|------|
| D.1 | System architecture diagram | `docs/architecture/system_architecture.md`, `deployment_architecture.md` | Implemented |
| D.2 | Design decisions / tradeoffs | `docs/adr/*`, `docs/tradeoffs/design_tradeoffs.md`, `docs/design/key-design-decisions.md` | Implemented |
| D.3 | Runnable code / README / examples | `README.md`, `scripts/*`, `docker-compose` | Implemented |
| D.4 | Demo / presentation summary | README, evaluation result docs | Implemented |
| DS.1 | Primary dataset (snehaanbhawal) path | `scripts/ingest_resumes.py`, ingestion service | Implemented |
| DS.2 | Alternate dataset (suriyaganesh) extension path | same script/config | Implemented |
| DS.3 | CSV/JSON/PDF input handling | `ingest_resumes.py`, pdfplumber, etc. | Implemented |
| DS.4 | skill/experience/education/category extraction | ingestion + enricher | Implemented |
| DS.5 | Extracted fields → retrieval/filtering/scoring use | `hybrid_retriever`, `scoring_service`, `filter_options` | Implemented |

---

## 4. Reviewer Checklist ↔ requirements · evidence mapping

Each Reviewer_Checklist item is linked to requirements, docs, and code. Use the paths below when checking.

### 4.1 Filesystem & Documentation

| Check item | Corresponding requirements | Evidence location |
|-----------|----------------|-----------|
| Clear folder structure | D.1, D.2 | `/requirements`, `/docs/architecture`, `/docs/data-flow`, `/src`, `/tests` |
| README setup/eval guide | D.3 | `README.md` |
| Stakeholder PPT / briefing deck | D.4 | `docs/evaluation/*`, `docs/design/key-design-decisions.md` (presentation materials are separate deliverables) |

### 4.2 Architecture & Design Integrity

| Check item | Corresponding requirements | Evidence location |
|-----------|----------------|-----------|
| Architecture vs Data Flow distinction | D.1 | `docs/architecture/system_architecture.md` top "Architecture vs Data Flow" paragraph; components = this doc, data flow = `docs/data-flow/resume_ingestion_flow.md`, `candidate_retrieval_flow.md` |
| Production scale (API GW, LB, K8s) | - | `docs/architecture/deployment_architecture.md` § "Production-scale considerations (API Gateway, Load Balancer, K8s)" |
| MVP vs Production scope | - | `docs/architecture/deployment_architecture.md` § "MVP vs production scope"; `problem_definition.md` Non-Goals |
| Observability & MLOps | R2.6, AHI.3 | `docs/observability/monitoring.md`; `docs/architecture/system_architecture.md` layer table "Observability & MLOps" row |
| ADR / design decisions | D.2, OBJ.5 | `docs/architecture/deployment_architecture.md` § "Design decisions (ADRs) and decoupling" → `docs/adr/*`, `docs/tradeoffs/design_tradeoffs.md`, `docs/design/key-design-decisions.md` |
| Decoupling (e.g. Vector DB swap) | - | `docs/architecture/deployment_architecture.md` § "Design decisions (ADRs) and decoupling"; `docs/adr/ADR-001-vector-db.md`, repository abstraction |

### 4.3 Implementation & Code Quality

Item-level evidence (code paths and verification) is listed under the summary table.

| Check item | Corresponding requirements | Evidence location |
|-----------|----------------|-----------|
| Zero print, structured logging | R1.9 | §4.3.1 below |
| Security & clean code (secrets, modularity) | R1.6 | §4.3.2 below |
| Connection pooling | R1.9 | §4.3.3 below |
| I/O validation (Pydantic) | R1.6, R1.8 | §4.3.4 below |
| Containerization | D.3 | §4.3.5 below |
| Resource management (generator/streaming) | R1.1, HCR.* | §4.3.6 below |
| Cold start optimization | R2.6 | §4.3.7 below |

**§4.3.1 Zero print / structured logging**  
`src/ops/logging.py`: structlog, `ProcessorFormatter` + `JSONRenderer`, request_id. `main.py`: `configure_logging(log_level=...)`. Backend and eval use logging; **one print exception**: `src/ops/mongo_handler.py` `emit()` exception path only — `print(..., file=sys.stderr)` to avoid logger recursion on handler failure.

**§4.3.2 Security & clean code**  
`src/backend/core/settings.py`: Pydantic Settings + `.env`/env injection (no API keys/URIs in code). Services and agents are split into modules: `matching_service.py`, `retrieval_service.py`, `agents/contracts/*`, `agents/runtime/*`, etc.

**§4.3.3 Connection pooling**  
Mongo: `core/database.py` — `maxPoolSize`, `minPoolSize`, `retryWrites` (`settings.py`). Milvus: `core/vector_store.py` — `_initialize_connection_pool()`, `milvus_pool_size`, gRPC keepalive. Pools created at app startup in `startup.py`/lifespan.

**§4.3.4 I/O validation (Pydantic)**  
`src/backend/schemas/job.py`, `candidate.py`, `feedback.py`, `ingestion.py`. FastAPI `Body`/`response_model`. Config: `core/settings.py` BaseSettings.

**§4.3.5 Containerization**  
`src/backend/Dockerfile`, root/`src/` `docker-compose.yml` (frontend, backend, mongodb, milvus). Matches README run procedure.

**§4.3.6 Resource management (generator/streaming)**  
`ingest_resumes.py`: CSV `chunksize`, `iter_sneha`/`iter_suri`/`_chunked` etc. with `yield`/`yield from`. `matching_service.py`: SSE `yield event: profile/candidate/fairness`. `api/jobs.py`: `StreamingResponse`.

**§4.3.7 Cold start optimization**  
`core/startup.py`: `warmup_infrastructure()` — `get_mongo_client()`, `ensure_indexes()`, `preload_collection()`. Called from `main.py` lifespan. Status exposed via `/api/health`, `/api/ready`.

### 4.4 Testing & Validation

| Check item | Corresponding requirements | Evidence location |
|-----------|----------------|-----------|
| Automated tests (loading, retrieval) | R1.*, HCR.*, DS.* | `tests/test_api.py`, `tests/test_retrieval.py` |
| Performance (latency p99, throughput) | R2.6 | `docs/evaluation/evaluation_results.md`, `scripts/run_eval.sh` |
| Accuracy (LLM-as-Judge, IR) | R2.1, R2.2, R2.4 | `src/eval/*`, `docs/evaluation/*` |
| Ground truth documentation | R2.1, DS.1, DS.2 | `golden_set.jsonl`, `evaluation_plan.md` |
| Resilience (fallback) | - | Fallback logic in design/code (documentation recommended) |

### 4.5 Reviewer's Verdict (SME Yes criteria)

| Verdict item | Reference when checking |
|-----------|----------------|
| Correctness | R1.6, R1.7, R2.1, R2.4, edge-case tests |
| Architecture | D.1, `system_architecture.md`, layer separation |
| Design decisions | D.2, ADR, `design_tradeoffs.md` |
| Performance | R2.6, HCR.*, R2.5, `evaluation_results.md` |
| Scalability | deployment docs, stateless API, pooling |
| Reliability | R2.7, retry/fallback policy |
| Maintainability | D.3, code structure, Docker |
| Observability | logging/monitoring docs, health checks |

---

## 5. Dependency alignment (requirements.txt)

Core project requirements and package mapping:

| Requirement area | Representative packages |
|-----------|-------------|
| API server | fastapi, uvicorn |
| DB & vector search | pymongo, motor, pymilvus |
| Schema & config | pydantic, pydantic-settings, python-dotenv |
| LLM & agents | openai, openai-agents, langsmith |
| Parsing & NLP | spacy, pdfplumber, pdfminer.six, dateparser |
| Logging | structlog |
| Evaluation | deepeval |

Dependencies used for R1.* (parsing, retrieval, API), R2.* (eval, benchmark), HCR.* (hybrid retrieval), and MSA.* (agents) are listed in `requirements.txt`.

---

## 6. Gaps and next steps (summary)

- **Requirements satisfied**: R2.3 (rerank tests/path), R2.5 (LangSmith, config-based token), R2.6 (benchmark, scalability design), AHI.2–AHI.4 (API/services) are satisfied by implementation. See [REQUIREMENTS_CHECKLIST_VERIFICATION.md](./REQUIREMENTS_CHECKLIST_VERIFICATION.md) for detail.
- **Recommended enhancements**: role-family calibration automation, retrieval quality regression report, filter explainability, ingestion auth/rate-limit documentation, fairness drift dashboard, handoff trace standardization (optional).

For detailed gaps/next steps, see the per-group "Gap / Next" column in [`requirements/traceability_matrix.md`](../../requirements/traceability_matrix.md).

---

## 7. Defense rationale — checklist/requirement issues

Justification for checklist or case-study items where **satisfaction is ambiguous or a different choice was made intentionally**.

| Item | Checklist/requirement | Current state | Defense rationale |
|------|-----------------|-----------|-----------|
| **Production scale (K8s, API GW, LB)** | Does architecture consider API Gateway, Load Balancer, K8s? | Current implementation is docker-compose; **considerations are documented** | Section in `docs/architecture/deployment_architecture.md` on production-scale considerations: role of API GW/LB/K8s, mapping to current implementation, how to apply when scaling (stateless, health, pooling). |
| **Resilience (local model fallback)** | Is there fallback to a local model (e.g. Flan-T5) on external API failure? | Only **heuristic / live_json** rule-based/single-call fallback implemented; no local SLM | On external API failure we switch **without extra LLM calls** along `sdk_handoff → live_json → heuristic` to preserve service continuity. Local SLM (e.g. Flan-T5) is an **intentional Non-Goal** due to ops/cost/model-version burden; retry, timeout, and fallback metadata satisfy reliability needs. |
| **live_json term** | What is "live_json" in the fallback chain? | — | **live_json** = agent path (`live_runner.py`) that gets a **JSON-schema** response via a **single LLM call** without the SDK. "live" = real-time single call, "json" = structured JSON. Used when SDK path fails; if this path also fails, switch to heuristic. |
| **Zero print()** | 100% structured logging, no print() | **Addressed.** Backend and eval use logging; one print in `src/ops/mongo_handler.py` emit exception path only (stderr to avoid logger recursion on handler failure). | See §4.3.1; `src/eval/*.py` print → logging completed. |
| **Stakeholder PPT** | Briefing deck with EDA, design, evaluation results | No separate .pptx; `docs/design/key-design-decisions.md`, `docs/evaluation/*`, `evaluation_results.md` exist | Presentation materials are **separate deliverables**. For a 10‑min demo: use the above docs for ~8 min design/results summary; optionally use `docs/presentation_summary.md` as a single reference. Actual .pptx can be a separate deliverable. |
| **Circuit breaker** | Retry logic, circuit breaker implementation | MongoDB retryWrites, ingestion rate limit; no dedicated circuit breaker | DB layer retries via `retryWrites`. External LLM calls limit failure propagation via **timeout + fallback chain** (immediate switch to heuristic). Circuit breaker recommended as Phase 2 under high load/multiple dependencies. |
| **R2.3 / R2.5 / R2.6** | Rerank enhancement, token optimization, throughput benchmark | Rerank tests/eval exist; token observability via LangSmith; scalability design for load | Rerank: `run_rerank_eval.sh`, eval_runner rerank mode, golden.rerank.jsonl. Token: LangSmith tracing + config-based budget/cache. Benchmark: performance_eval and scalability design (K8s/LB/stateless). See [REQUIREMENTS_CHECKLIST_VERIFICATION.md](./REQUIREMENTS_CHECKLIST_VERIFICATION.md). |
| **AHI.2–AHI.4** | Feedback loop, analytics, interview/email handoff | Requirements satisfied by API/service implementation | Feedback API, email draft, handoff data provided. Auto-retrain pipeline, dedicated dashboard, handoff standard can be added later if needed. |

Use this table when explaining in review why an item is Yes or Partial.
