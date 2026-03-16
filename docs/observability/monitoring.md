# Monitoring

## Observability Baseline

| 영역 | 구현 |
|---|---|
| Structured logging | `src/ops/logging.py` |
| Request correlation | `src/ops/middleware.py` (`X-Request-Id`) |
| Service-level events | matching/retrieval/rerank/fairness stage logs |
| Evaluation artifacts | `src/eval/outputs/*`, `docs/evaluation/evaluation_results.md` |
| Tracing | LangSmith (env enabled) |

## Core Operational Signals

1. API latency p50/p95/p99
2. retrieval success rate 및 fallback rate
3. rerank invocation/timeouts/added latency
4. agent runtime mode 분포(`sdk_handoff/live_json/heuristic`)
5. fairness warning trigger frequency
6. token budget/cache hit ratio
7. candidates/sec, call/sec

## Stage-wise Reliability Signals

| Stage | 핵심 지표 | 장애 시 기대 동작 |
|---|---|---|
| Query understanding | confidence, unknown_ratio, fallback_rate | fallback query profile 생성 |
| Retrieval | vector success rate, Mongo fallback rate | lexical fallback 후 결과 유지 |
| Rerank | rerank 실행률, timeout rate | rerank 생략 후 baseline 유지 |
| Agent orchestration | mode distribution, agent error rate | `sdk -> live -> heuristic` 강등 |
| Final response | score coverage, warning counts | 최소 설명 필드 보장 |

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

- Retrieval success rate 급락 시 즉시 경보
- p99 latency 급증 시 stage별 병목 분리 알림
- `heuristic` 모드 비율 급증 시 agent runtime 장애 알림
- fairness warning 급증 시 데이터/정책 드리프트 점검
