# Cost Control

## Cost Control Strategy

1. 후보 평가 수 상한(`agent_eval_top_n`)으로 토큰 지출을 제어한다.
2. JD 요청 캐시(LRU+TTL)로 반복 질의 비용을 절감한다.
3. rerank는 gate 통과 케이스에서만 수행한다.
4. deterministic scoring을 기본 경로로 두고 고비용 경로는 조건부로 실행한다.
5. A2A(Recruiter/HiringManager weight negotiation) handoff 입력을 슬림하게 유지하고, `max_turns`를 필요한 수준으로 제한한다.

## A2A 비용과 완화

**비용이 나가는 이유**

- 후보당 에이전트 경로: 4개 평가 에이전트 + ScorePack + **A2A handoff**(Recruiter → HiringManager → WeightNegotiation)가 순차/핸드오프로 실행된다.
- A2A 구간에서 **동일한 대용량 입력**이 매 턴마다 전달된다. 기존에는 `job_description` 전체와 후보 전체 입력(각종 `raw_resume_text` 포함)을 그대로 handoff 입력과 run_context에 넣어, 턴마다 반복 전송되며 토큰이 크게 늘어났다.
- `max_turns` 기본값이 6이어서, 실제로는 Recruiter→HM→Negotiation 3단계면 끝나는 플로우에 비해 불필요하게 많은 턴이 허용되었다.

**적용한 완화**

- **Handoff용 슬림 payload** (`_build_slim_payload_for_handoff`): A2A 입력에는 `job_profile`, `retrieval_context`, 후보 `candidate_id`와 짧은 `candidate_summary`(최대 2000자)만 포함한다. `job_description`과 `raw_resume_text` 및 전체 candidate input 덤프는 제외하여 handoff당·턴당 토큰을 대폭 줄였다.
- **max_turns 기본값 3** (`HandoffConstraints.max_turns`): Recruiter → HiringManager → WeightNegotiation 3단계에 맞춰 기본값을 6에서 3으로 낮췄다. 필요 시 설정으로 1~12 유지 가능.

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

- 캐시 대상 경로: `match_jobs`, `stream_match_jobs`
- 공통 캐시 객체: `ResponseLRUCache` (backend 프로세스 메모리)
- 기본 설정: `TOKEN_CACHE_ENABLED=true`, `TOKEN_CACHE_TTL_SEC=300`, `TOKEN_CACHE_MAX_SIZE=128`

### Key / Value

- Key 구성: `job_description`, `top_k`, `category`, `min_experience_years`, `education`, `region`, `industry`
- Key 직렬화 후 SHA-256 해시(앞 16자리)를 캐시 키로 사용
- Value 타입: `JobMatchResponse`

### Hit/Miss Behavior

- `match_jobs`
- hit: 즉시 `JobMatchResponse` 반환 (retrieval/agent/rerank 생략)
- miss: 기존 파이프라인 실행 후 응답 저장
- `stream_match_jobs`
- hit: `profile -> session -> candidate* -> fairness -> done` 이벤트를 즉시 스트리밍
- miss: 기존 스트리밍 파이프라인 실행 후 최종 결과를 `JobMatchResponse`로 저장
- 후보가 0명인 조기 종료 분기도 fairness 결과를 캐시에 저장

### Operational Notes

- 인메모리 캐시이므로 프로세스 재시작 시 초기화됨
- 멀티 인스턴스 환경에서는 인스턴스 간 캐시 공유가 되지 않음
- TTL 만료 정리는 접근 시점(lazy expiration)에 수행됨
- 로그 지표: `token_cache_hit`, `token_cache_miss` (stream은 `source=stream` 태그 포함)

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
