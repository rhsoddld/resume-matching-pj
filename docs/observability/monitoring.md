# Monitoring

## Observability Baseline

| Area | Implementation |
|---|---|
| Structured logging | `src/ops/logging.py` |
| Request correlation | `src/ops/middleware.py` (`X-Request-Id`) |
| Service-level events | matching/retrieval/rerank/fairness stage logs |
| Evaluation artifacts | `src/eval/outputs/*`, `docs/evaluation/evaluation_results.md` |
| Tracing | LangSmith (env enabled) |

## Core Operational Signals

1. API latency p50/p95/p99
2. retrieval success rate and fallback rate
3. rerank invocation/timeouts/added latency
4. agent runtime mode distribution (`sdk_handoff/live_json/heuristic`)
5. fairness warning trigger frequency
6. token budget/cache hit ratio
7. candidates/sec, call/sec

## Stage-wise Reliability Signals

| Stage | Key metrics | Expected behavior on failure |
|---|---|---|
| Query understanding | confidence, unknown_ratio, fallback_rate | generate fallback query profile |
| Retrieval | vector success rate, Mongo fallback rate | keep results via lexical fallback |
| Rerank | rerank rate, timeout rate | skip rerank and keep baseline |
| Agent orchestration | mode distribution, agent error rate | degrade `sdk -> live -> heuristic` |
| Final response | score coverage, warning counts | guarantee minimum explanation fields |

## Legacy Benchmark References (Restored)

- Retrieval benchmark archive (2026-03-15 UTC)
  - success rate `1.0`
  - candidates/sec `60.2076`
  - latency p95 `1069.8 ms`
  - latency p99 `2834.231 ms`
- LLM rerank archive (2026-03-15 UTC)
  - avg added latency `3344.815 ms`
  - quality delta avg overlap@k `-0.0461`

## Recommended Dashboard Panels

1. `API` latency + error rate
2. `Retrieval` success/fallback + top_k quality proxy
3. `Rerank` ROI (quality delta vs latency/cost)
4. `Agent Runtime` mode distribution + fallback reason
5. `Fairness/Guardrail` warning counts by query family
6. `Cost` tokens/request + cache effectiveness

## Alerting Guidelines

- Alert immediately on sharp drops in retrieval success rate
- Alert on p99 latency spikes and attribute to the bottleneck stage
- Alert if `heuristic` mode usage spikes (agent runtime degradation/outage)
- Investigate data/policy drift if fairness warnings spike
