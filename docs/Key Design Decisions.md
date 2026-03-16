# Key Design Decisions – AI Resume Matching System

**Project:** `resume-matching-pj` | **Version:** MVP / Capstone baseline | **Date:** March 2026  
**Goal:** JD(Job Description) → 구조화된 쿼리 → Hybrid Retrieval → Multi-Agent 평가 → Explainable Candidate Recommendation

## 1. Vector DB & Document Store → Milvus + MongoDB

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **Milvus** (vector retrieval) | Strong vector performance, metadata filtering, Docker-friendly local dev | Qdrant, Pinecone, Weaviate |
| **MongoDB** (document source) | Candidate profiles, resume text, structured fields; single source of truth | PostgreSQL + pgvector, Elasticsearch |
| **Dual-store sync** | Ingestion pipeline upserts to both; retrieval uses Milvus for vector, MongoDB for fallback/lexical path | Single store with vector extension |

*Ref: [ADR-001-vector-db.md](./adr/ADR-001-vector-db.md)*

## 2. Embedding Strategy → OpenAI text-embedding-3-small

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **text-embedding-3-small** | Lower cost, faster indexing/re-indexing; sufficient baseline for capstone scope | text-embedding-3-large, Cohere, open-source sentence-transformers |
| **Model configurable via env** | Easy upgrade path without code change | Hardcoded model |
| **Future: fine-tuned embedding** | R2.3 fine-tuned embedding rerank intentionally deferred until A/B evidence | Fine-tune from day one |

*Ref: [ADR-002-embedding-model.md](./adr/ADR-002-embedding-model.md)*

## 3. Query Understanding → Deterministic (No LLM for JD Parsing)

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **Deterministic JD parsing** | Predictable, fast, no LLM cost; skill taxonomy + alias normalization + role inference | LLM-based JD extraction (slow, costly, non-deterministic) |
| **Skill taxonomy + config YAML** | skill_taxonomy.yml, skill_aliases.yml, skill_capability_phrases.yml, job_filters.yml로 정규화 및 시그널 품질 보장 | DB-driven taxonomy, external API |
| **Signal quality & confidence** | `signal_quality`, `confidence` 출력으로 retrieval/rerank 게이트 및 평가 추적 가능 | Opaque query object |
| **Query fallback (optional)** | Low confidence / high unknown_ratio 시 LLM query fallback 옵션 제공 | Always LLM or never LLM |

*Implementation:* `src/backend/services/job_profile_extractor.py`, `src/backend/core/filter_options.py`, `config/*.yml`

**설명 vs 코드:** 필터 옵션 API(`/api/jobs/filters`)는 `repositories.mongo_repo.get_filter_options()`를 호출하지만, 현재 구현에서는 **MongoDB를 읽지 않고** `core.filter_options.get_filter_options()`(YAML: `job_filters.yml` + `skill_taxonomy.yml` 병합)만 사용한다. 즉 필터 옵션 소스는 100% 설정 파일이다.

## 4. Hybrid Retrieval (Vector + Keyword + Metadata)

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **Vector + lexical + metadata** | Semantic recall + exact skill coverage + structured filters (category, experience, etc.) | Vector-only or keyword-only |
| **Fusion scoring** | `hybrid_scoring.fusion_score`로 vector similarity, keyword score, metadata score 결합 | Single-score ranking |
| **Mongo fallback** | Milvus 불가 시 Mongo 기반 lexical path로 후보 풀 생성 | Fail fast |

*Ref: [ADR-003-hybrid-retrieval.md](./adr/ADR-003-hybrid-retrieval.md)*  
*Implementation:* `src/backend/services/hybrid_retriever.py`, `src/backend/services/retrieval/hybrid_scoring.py`

## 5. Rerank Layer → Conditional Gate + Embedding/LLM Modes

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **Rerank OFF by default** | Latency/quality A/B 증거 확보 전까지 baseline shortlist 유지 | Always rerank |
| **Gate conditions** | tie-like (top2 gap 작음), ambiguous query (low confidence / high unknown_ratio)일 때만 rerank 실행 | Unconditional rerank |
| **Model routing** | Default path `RERANK_MODEL_DEFAULT`, ambiguity/tie-break path `RERANK_MODEL_HIGH_QUALITY` (e.g. gpt-4o) | Single model |
| **Timeout & fallback** | `RERANK_TIMEOUT_SEC` 적용, 실패 시 baseline shortlist 반환 | Block until rerank completes |
| **R2.3 fine-tuned embedding rerank** | Intentionally deferred; baseline 이상 주장하지 않음 | Implement from start |

*Implementation:* `src/backend/services/matching/rerank_policy.py`, `src/backend/services/cross_encoder_rerank_service.py`, `src/backend/core/model_routing.py`

**설명 vs 코드:** Rerank 서비스 파일명은 `cross_encoder_rerank_service.py`이지만, 실제 구현은 **embedding 기반** rerank와 **LLM** rerank 두 모드만 지원한다. Cross-Encoder 모델(예: ms-marco-MiniLM-L-6-v2)은 사용하지 않으며, `rerank_mode`가 `embedding`일 때는 쿼리+후보 텍스트를 embedding한 뒤 유사도로 재정렬한다.

## 6. Multi-Agent Evaluation & Weight Negotiation

| Decision | Reason | Alternative Considered |
|----------|--------|-------------------------|
| **4 evaluation agents (parallel)** | Skill / Experience / Technical / Culture 분리 → 각각 독립 점수 및 근거 | Single monolithic LLM call |
| **Recruiter vs Hiring Manager weights** | RecruiterAgent + HiringManagerAgent 제안 → WeightNegotiationAgent로 최종 가중치 | Fixed weights |
| **Runtime fallback chain** | SDK handoff → live_json → heuristic; 응답에 `runtime_mode` 및 fallback reason 포함 | Single path only |
| **RAG-as-a-Tool** | 에이전트가 `search_candidate_evidence`로 증거 탐색 가능 | No tool use |

*Ref: [ADR-004-agent-orchestration.md](./adr/ADR-004-agent-orchestration.md)*  
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
| **Sensitive term scan** | JD/설명 텍스트에서 민감속성 키워드 탐지 → `fairness.warnings` | No scan |
| **Culture weight cap** | `fairness_max_culture_weight` 초과 시 경고 | No cap |
| **Must-have vs culture gate** | must-have 미달 + culture 고신뢰 조합 시 경고 | No gate |
| **Top-K seniority distribution** | JD seniority 미지정 시 상위 K명 seniority 쏠림 검사 | No check |

*Implementation:* `src/backend/services/matching/fairness.py`, `src/backend/core/jd_guardrails.py`  
*Frontend:* `BiasGuardrailBanner.tsx`로 경고 노출

## 9. Observability & Operations

| Component | Choice |
|-----------|--------|
| **Logging** | structlog; request_id middleware; optional MongoDB request log |
| **Tracing** | LangSmith (openai-agents); `traceable_op` for retrieval/rerank |
| **Metrics** | Custom retrieval metrics (top_k, elapsed_ms, candidates_per_sec); fairness_guardrail_triggered |
| **Health** | `/api/health` (liveness), `/api/ready` (Mongo + Milvus readiness) |
| **Deployment** | Docker Compose (local); GKE/Helm-ready (see deployment_architecture.md) |

*Ref: [docs/observability/logging_metrics.md](./observability/logging_metrics.md), [docs/observability/monitoring.md](./observability/monitoring.md)*

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

## 11. 구현 갭 및 향후 고도화 (현재 상태 기준)

| 갭 | 설명 |
|----|------|
| Query Understanding v3 | 직군별 golden set으로 role/skill/capability strength 상시 검증 필요 |
| Hybrid fusion weight | 직군별 calibration 미완 |
| Rerank A/B | 조건부 게이트/타임아웃/fallback 구현됨; latency/quality benchmark로 품질 개선 입증 필요 |
| Fine-tuned embedding rerank | R2.3 의도적 defer; 학습/버전/rollback/A-B 확보 후 주장 |
| Explainability 품질 | DeepEval/LLM-as-Judge로 문장 품질·근거 일관성 자동 평가 고도화 |
| Fairness 운영 | v1 구현됨; fairness metrics 대시보드 및 정책 튜닝 고도화 |

*상세: [docs/architecture/system_architecture.md](./architecture/system_architecture.md) § 구현 갭*
