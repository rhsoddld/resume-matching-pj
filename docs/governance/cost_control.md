# Cost Control

## Cost Control Strategy

1. Control token spend via the per-request cap on evaluated candidates (`agent_eval_top_n`).
2. Reduce repeated-query cost via a JD request cache (LRU + TTL).
3. Run reranking only for gated cases.
4. Keep deterministic scoring as the default path and run expensive paths conditionally.
5. Keep A2A (Recruiter/HiringManager weight negotiation) handoff inputs slim and limit `max_turns` to what is necessary.

## A2A cost drivers and mitigations

**Why A2A costs are high**

- Per-candidate agent path: 4 evaluation agents + ScorePack + **A2A handoff** (Recruiter → HiringManager → WeightNegotiation) run sequentially via handoffs.
- In the A2A segment, the **same large payload** can be sent every turn. Previously the full `job_description` and full candidate inputs (including `raw_resume_text`) were passed via handoff input and run_context, ballooning token usage due to repeated transmission.
- Default `max_turns` was 6, which allowed unnecessary turns for a flow that typically finishes in three stages (Recruiter → HM → Negotiation).

**Mitigations applied**

- **Slim payload for handoff** (`_build_slim_payload_for_handoff`): A2A inputs include only `job_profile`, `retrieval_context`, candidate `candidate_id`, and a short `candidate_summary` (max 2000 chars). Excluding `job_description`, `raw_resume_text`, and full candidate dumps dramatically reduces per-handoff / per-turn tokens.
- **Default `max_turns` = 3** (`HandoffConstraints.max_turns`): lowered from 6 to 3 to match the three-stage flow (Recruiter → HiringManager → WeightNegotiation). Still configurable from 1–12 if needed.

## Tunable Controls

- `TOKEN_BUDGET_ENABLED`
- `TOKEN_BUDGET_PER_REQUEST`
- `TOKEN_ESTIMATED_PER_AGENT_CALL`
- `TOKEN_CACHE_ENABLED`
- `TOKEN_CACHE_TTL_SEC`
- `TOKEN_CACHE_MAX_SIZE`
- `RERANK_ENABLED`
- `RERANK_TOP_N`
- `RERANK_GATE_MAX_TOP_N`
- `RERANK_TIMEOUT_SEC`

## Current Cache Implementation (As-Is)

### Scope

- Cached endpoints: `match_jobs`, `stream_match_jobs`
- Shared cache object: `ResponseLRUCache` (backend process memory)
- Defaults: `TOKEN_CACHE_ENABLED=true`, `TOKEN_CACHE_TTL_SEC=300`, `TOKEN_CACHE_MAX_SIZE=128`

### Key / Value

- Key fields: `job_description`, `top_k`, `category`, `min_experience_years`, `education`, `region`, `industry`
- Cache key: SHA-256 hash of the serialized key (first 16 hex chars)
- Value type: `JobMatchResponse`

### Hit/Miss Behavior

- `match_jobs`
- hit: return `JobMatchResponse` immediately (skips retrieval/agent/rerank)
- miss: run the pipeline and store the response
- `stream_match_jobs`
- hit: stream `profile -> session -> candidate* -> fairness -> done` immediately
- miss: run the streaming pipeline and store the final `JobMatchResponse`
- early-exit cases with 0 candidates also store fairness outputs in the cache

### Operational Notes

- In-memory cache resets on process restart
- In multi-instance deployments, caches are not shared across instances
- TTL eviction is lazy (performed on access)
- Log metrics: `token_cache_hit`, `token_cache_miss` (streaming adds `source=stream` tag)

## Legacy Benchmark Snapshot (Restored)

### Retrieval benchmark archive (2026-03-15 UTC)
- candidates/sec: `60.2076`
- latency p95: `1069.8 ms`
- latency p99: `2834.231 ms`
- success rate: `1.0`

### LLM rerank comparison archive (2026-03-15 UTC)
- delta avg overlap@k: `-0.0461`
- avg rerank latency: `3344.815 ms`
- interpretation: an optional/gated path is preferable to always-on rerank in the default flow

## Reporting

Required monitoring items:
1. cache hit ratio
2. rerank invocation rate
3. token per request (estimated/actual)
4. fallback rate by runtime mode
5. latency p95/p99 by stage
