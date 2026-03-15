# Retrieval Benchmark

## Run Metadata

- Generated at (UTC): `2026-03-15 11:07:09`
- Input dataset: `/Users/lee/Desktop/resume-matching-pj/src/eval/golden_set.jsonl`
- Query count: `50`
- Iterations: `3`
- Workers: `4`
- Warmup rounds: `1` (calls: `50`)
- top_k: `30`
- Category override: `None`
- Min experience filter: `None`

## KPI Summary

| Metric | Value |
|---|---|
| Success rate | `1.0` |
| Candidates/sec | `60.2076` |
| Calls/sec | `7.8769` |
| Successful calls | `150` |
| Failed calls | `0` |
| Total returned candidates | `4500` |
| Latency mean (ms) | `498.276` |
| Latency p50 (ms) | `402.316` |
| Latency p95 (ms) | `1069.8` |
| Latency p99 (ms) | `2834.231` |
| Latency max (ms) | `3121.926` |

## Interpretation Guide

- `success_rate`: 1.0에 가까울수록 안정적입니다. 0.99 미만이면 인프라/의존성 오류를 먼저 점검하세요.
- `candidates_per_sec`: 같은 환경/같은 입력셋으로 이전 실행값과 비교해 추세를 보세요.
- `p95/p99 latency`: tail 지연 구간입니다. 평균보다 이 값이 먼저 악화되면 부하 병목 신호입니다.
- `calls_per_sec`: 동시성(`workers`)과 인프라 상태 영향을 크게 받으므로 단독 지표로 해석하지 마세요.

## Error Summary (Top)

- 없음

## Next Actions Checklist

- [ ] 이번 실행의 기준선(baseline)을 팀 문서에 기록했다.
- [ ] 이전 실행 대비 증감(%)을 기록했다.
- [ ] 실패 케이스 원인(Mongo/Milvus/OpenAI/timeout)을 분류했다.
- [ ] 재현 커맨드와 환경 정보를 함께 남겼다.

## Raw Summary JSON

```json
{
  "queries": 50,
  "total_calls": 150,
  "successful_calls": 150,
  "failed_calls": 0,
  "success_rate": 1.0,
  "total_returned_candidates": 4500,
  "benchmark_elapsed_sec": 19.042912,
  "successful_call_elapsed_sec_sum": 74.741456,
  "candidates_per_sec": 60.2076,
  "calls_per_sec": 7.8769,
  "latency_ms": {
    "mean": 498.276,
    "p50": 402.316,
    "p95": 1069.8,
    "p99": 2834.231,
    "max": 3121.926
  }
}
```
