# Key Design Decisions – AI Resume Matching System

**Project:** `resume-matching-pj` | **Version:** MVP / Capstone baseline | **Date:** March 2026  
**Goal:** JD (Job Description) → structured query → hybrid retrieval → multi-agent evaluation → explainable candidate recommendation

**Design rationale (ontology/cost/eval):** [rationale-ontology-eval-cost.md](./rationale-ontology-eval-cost.md) — why a skill ontology (agentic-AI friendliness), long-run cost structure (agent work focus), and evaluation metrics/viewpoints.

## 1. Vector DB & Document Store → Milvus + MongoDB

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **Milvus** (vector retrieval) | Strong vector performance, metadata filtering, Docker-friendly local dev | Qdrant, Pinecone, Weaviate |
| **MongoDB** (document source) | Candidate profiles, resume text, structured fields; single source of truth | PostgreSQL + pgvector, Elasticsearch |
| **Dual-store sync** | Ingestion pipeline upserts to both; retrieval uses Milvus for vector, MongoDB for fallback/lexical path | Single store with vector extension |

*Ref: [ADR-001-vector-db.md](../adr/ADR-001-vector-db.md)*

## 2. Embedding Strategy → OpenAI text-embedding-3-small

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **text-embedding-3-small** | Lower cost, faster indexing/re-indexing; sufficient baseline for capstone scope | text-embedding-3-large, Cohere, open-source sentence-transformers |
| **Model configurable via env** | Easy upgrade path without code change | Hardcoded model |
| **Future: fine-tuned embedding** | R2.3 fine-tuned embedding rerank intentionally deferred until A/B evidence | Fine-tune from day one |

*Ref: [ADR-002-embedding-model.md](../adr/ADR-002-embedding-model.md)*

## 3. Query Understanding → Deterministic (No LLM for JD Parsing)

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **Deterministic JD parsing** | Predictable, fast, no LLM cost; skill taxonomy + alias normalization + role inference | LLM-based JD extraction (slow, costly, non-deterministic) |
| **Skill taxonomy + config YAML** | Normalize and stabilize signal quality via skill_taxonomy.yml, skill_aliases.yml, skill_capability_phrases.yml, job_filters.yml | DB-driven taxonomy, external API |
| **Signal quality & confidence** | Emit `signal_quality` and `confidence` to support retrieval/rerank gating and evaluation traceability | Opaque query object |
| **Query fallback (optional)** | Provide an optional LLM query fallback when confidence is low or unknown_ratio is high | Always LLM or never LLM |

*Ref: [ADR-005-deterministic-query-understanding.md](../adr/ADR-005-deterministic-query-understanding.md)*  
*Implementation:* `src/backend/services/job_profile_extractor.py`, `src/backend/core/filter_options.py`, `config/*.yml`

**Docs vs code:** the filter-options API (`/api/jobs/filters`) calls `repositories.mongo_repo.get_filter_options()`, but the current implementation **does not read MongoDB**. It uses only `core.filter_options.get_filter_options()` (YAML merge of `job_filters.yml` + `skill_taxonomy.yml`). In other words, filter options are 100% config-file driven.

## 4. Hybrid Retrieval (Vector + Keyword + Metadata)

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **Vector + lexical + metadata** | Semantic recall + exact skill coverage + structured filters (category, experience, etc.) | Vector-only or keyword-only |
| **Fusion scoring** | Combine vector similarity, keyword score, and metadata score via `hybrid_scoring.fusion_score` | Single-score ranking |
| **Mongo fallback** | If Milvus is unavailable, build a candidate pool via the Mongo lexical path | Fail fast |

*Ref: [ADR-003-hybrid-retrieval.md](../adr/ADR-003-hybrid-retrieval.md)*  
*Implementation:* `src/backend/services/hybrid_retriever.py`, `src/backend/services/retrieval/hybrid_scoring.py`

## 5. Rerank Layer → Conditional Gate + Embedding/LLM Modes

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **Rerank OFF by default** | Keep baseline shortlist until latency/quality A/B evidence is established | Always rerank |
| **Gate conditions** | Run rerank only for tie-like (small top2 gap) or ambiguous queries (low confidence / high unknown_ratio) | Unconditional rerank |
| **Model routing** | Default path `RERANK_MODEL_DEFAULT`, ambiguity/tie-break path `RERANK_MODEL_HIGH_QUALITY` (e.g. gpt-4o) | Single model |
| **Timeout & fallback** | Apply `RERANK_TIMEOUT_SEC`; on failure return the baseline shortlist | Block until rerank completes |
| **R2.3 fine-tuned embedding rerank** | Intentionally deferred; do not claim beyond baseline | Implement from start |

*Ref: [ADR-006-rerank-policy.md](../adr/ADR-006-rerank-policy.md)*  
*Implementation:* `src/backend/services/matching/rerank_policy.py`, `src/backend/services/cross_encoder_rerank_service.py`, `src/backend/core/model_routing.py`

**Docs vs code:** although the rerank service file is named `cross_encoder_rerank_service.py`, the implementation supports only two modes: **embedding-based** rerank and **LLM** rerank. It does not use a Cross-Encoder model (e.g., ms-marco-MiniLM-L-6-v2). When `rerank_mode=embedding`, it embeds query + candidate text and reorders by similarity.

## 6. Multi-Agent Evaluation & Weight Negotiation

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **4 evaluation agents (parallel)** | Split Skill/Experience/Technical/Culture → independent scores and evidence | Single monolithic LLM call |
| **Recruiter vs Hiring Manager weights** | RecruiterAgent + HiringManagerAgent proposals → final weights via WeightNegotiationAgent | Fixed weights |
| **Runtime fallback chain** | SDK handoff → live_json → heuristic; response includes `runtime_mode` and fallback reason | Single path only |
| **RAG-as-a-Tool** | Agents can search for evidence via `search_candidate_evidence` | No tool use |

**Agent latency tradeoff and mitigations:** in the OpenAI SDK path, multiple agents run sequentially via handoffs per candidate, which increases inter-agent communication and overall runtime latency. Mitigations include **(1) per-candidate parallelism** (evaluate shortlist candidates concurrently via ThreadPoolExecutor), **(2) streaming (SSE)** to deliver profile → thought_process → candidate incrementally for better UX, **(3) an `agent_eval_top_n` cap**, and **(4) live_json/heuristic fallback** to reduce latency/cost and improve resilience. See [design_tradeoffs.md](../tradeoffs/design_tradeoffs.md) § Agent tradeoffs.

*Ref: [ADR-004-agent-orchestration.md](../adr/ADR-004-agent-orchestration.md)*  
*Implementation:* `src/backend/agents/contracts/*.py`, `src/backend/agents/runtime/service.py`, `sdk_runner.py`, `live_runner.py`, `heuristics.py`

## 7. LLM Usage (Default Models)

| Component | Default Model | Purpose |
|-----------|---------------|---------|
| Agent reasoning | gpt-4.1-mini | Skill/Experience/Technical/Culture agents, negotiation |
| Embedding | text-embedding-3-small | Query & candidate embedding |
| Rerank (when enabled) | gpt-4.1-mini (default path), gpt-4o (high-quality path) | LLM rerank mode |
| Query fallback | gpt-4.1-mini | Low-confidence JD parsing fallback |
| Eval judge | gpt-4o | LLM-as-Judge evaluation |

All model names and versions are configurable via `backend.core.settings` (env).

## 8. Bias & Fairness Guardrails (Backend v1)

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **Sensitive term scan** | Detect sensitive-attribute keywords in JD/explanations → `fairness.warnings` | No scan |
| **Culture weight cap** | Warn when exceeding `fairness_max_culture_weight` | No cap |
| **Must-have vs culture gate** | Warn on must-have shortfall + high culture confidence | No gate |
| **Top-K seniority distribution** | Check for Top-K seniority skew when JD seniority is unspecified | No check |

*Ref: [ADR-008-bias-fairness-guardrails.md](../adr/ADR-008-bias-fairness-guardrails.md)*  
*Implementation:* `src/backend/services/matching/fairness.py`, `src/backend/core/jd_guardrails.py`  
*Frontend:* warnings are displayed via `BiasGuardrailBanner.tsx`

## 9. Observability & Operations

| Component | Choice |
|-----------|--------|
| **Logging** | structlog; request_id middleware; optional MongoDB request log |
| **Tracing** | LangSmith (openai-agents); `traceable_op` for retrieval/rerank |
| **Metrics** | Custom retrieval metrics (top_k, elapsed_ms, candidates_per_sec); fairness_guardrail_triggered |
| **Health** | `/api/health` (liveness), `/api/ready` (Mongo + Milvus readiness) |
| **Deployment** | Docker Compose (local); GKE/Helm-ready (see deployment_architecture.md) |

*Ref: [ADR-009-observability-strategy.md](../adr/ADR-009-observability-strategy.md)*  
*Ref: [docs/observability/logging_metrics.md](../observability/logging_metrics.md), [docs/observability/monitoring.md](../observability/monitoring.md)*

## 10. Tech Stack Summary (Final)

```yaml
Embedding:       OpenAI text-embedding-3-small
Vector DB:       Milvus (Docker / K8s-ready)
Document Store:  MongoDB
LLM:             OpenAI GPT-4.1-mini (agents, rerank, query fallback); GPT-4o (eval judge, HQ rerank path)
Backend:         FastAPI + Uvicorn
Frontend:        React (Vite), TypeScript
Query Understanding: Deterministic (skill taxonomy, YAML config)
Retrieval:       Hybrid (vector + keyword + metadata fusion)
Rerank:          Conditional gate; embedding default, LLM optional; fallback to baseline
Agents:          Multi-agent (Skill / Experience / Technical / Culture) + Weight Negotiation
Explainability:  Match result builder + frontend CandidateDetailModal / ExplainabilityPanel
Evaluation:      DeepEval, LLM-as-Judge, golden set; Bias guardrails v1
```

## 11. Implementation gaps and future improvements (current state)

| Gap | Description |
|----|------|
| Query Understanding v3 | Need continuous validation of role/skill/capability strength with job-family-specific golden sets |
| Hybrid fusion weight | Per-job-family calibration is incomplete |
| Rerank A/B | Conditional gates/timeouts/fallback exist; need latency/quality benchmarks proving consistent improvements |
| Fine-tuned embedding rerank | R2.3 intentionally deferred; claim only after training/versioning/rollback/A-B evidence |
| Explainability quality | Improve automated sentence quality + evidence consistency evaluation via DeepEval/LLM-as-Judge |
| Fairness operations | v1 implemented; improve fairness metrics dashboards and policy tuning |

*Details: [docs/architecture/system_architecture.md](../architecture/system_architecture.md) § Implementation gaps*
