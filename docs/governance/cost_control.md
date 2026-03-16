# Cost Control

## Cost Control Strategy

1. 후보 평가 수 상한(`agent_eval_top_n`)으로 토큰 지출을 제어한다.
2. JD 요청 캐시(LRU+TTL)로 반복 질의 비용을 절감한다.
3. rerank는 gate 통과 케이스에서만 수행한다.
4. deterministic scoring을 기본 경로로 두고 고비용 경로는 조건부로 실행한다.

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

## Legacy Benchmark Snapshot (Restored)

### Retrieval benchmark archive (2026-03-15 UTC)
- candidates/sec: `60.2076`
- latency p95: `1069.8 ms`
- latency p99: `2834.231 ms`
- success rate: `1.0`

### LLM rerank comparison archive (2026-03-15 UTC)
- delta avg overlap@k: `-0.0461`
- avg rerank latency: `3344.815 ms`
- interpretation: 기본 경로 상시 적용보다는 optional/gated 경로가 적절

## Reporting

필수 모니터링 항목:
1. cache hit ratio
2. rerank invocation rate
3. token per request (estimated/actual)
4. fallback rate by runtime mode
5. latency p95/p99 by stage
