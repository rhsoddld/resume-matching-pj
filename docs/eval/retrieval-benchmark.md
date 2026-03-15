# Retrieval Benchmark

## Run Metadata

- Generated at (UTC): `2026-03-15 08:08:05`
- Input dataset: `/Users/lee/Desktop/resume-matching-pj/src/eval/golden_set.jsonl`
- Query count: `10`
- Iterations: `3`
- Workers: `4`
- Warmup rounds: `1` (calls: `10`)
- top_k: `30`
- Category override: `None`
- Min experience filter: `None`

## KPI Summary

| Metric | Value |
|---|---|
| Success rate | `0.0` |
| Candidates/sec | `0.0` |
| Calls/sec | `0.0` |
| Successful calls | `0` |
| Failed calls | `30` |
| Total returned candidates | `0` |
| Latency mean (ms) | `0.0` |
| Latency p50 (ms) | `0.0` |
| Latency p95 (ms) | `0.0` |
| Latency p99 (ms) | `0.0` |
| Latency max (ms) | `0.0` |

## Interpretation Guide

- `success_rate`: 1.0에 가까울수록 안정적입니다. 0.99 미만이면 인프라/의존성 오류를 먼저 점검하세요.
- `candidates_per_sec`: 같은 환경/같은 입력셋으로 이전 실행값과 비교해 추세를 보세요.
- `p95/p99 latency`: tail 지연 구간입니다. 평균보다 이 값이 먼저 악화되면 부하 병목 신호입니다.
- `calls_per_sec`: 동시성(`workers`)과 인프라 상태 영향을 크게 받으므로 단독 지표로 해석하지 마세요.

## Error Summary (Top)

- `ExternalDependencyError: Both vector retrieval and Mongo fallback failed.`: 20

## Next Actions Checklist

- [ ] 이번 실행의 기준선(baseline)을 팀 문서에 기록했다.
- [ ] 이전 실행 대비 증감(%)을 기록했다.
- [ ] 실패 케이스 원인(Mongo/Milvus/OpenAI/timeout)을 분류했다.
- [ ] 재현 커맨드와 환경 정보를 함께 남겼다.

## Raw Summary JSON

```json
{
  "queries": 10,
  "total_calls": 30,
  "successful_calls": 0,
  "failed_calls": 30,
  "success_rate": 0.0,
  "total_returned_candidates": 0,
  "benchmark_elapsed_sec": 272.33453,
  "successful_call_elapsed_sec_sum": 0.0,
  "candidates_per_sec": 0.0,
  "calls_per_sec": 0.0,
  "latency_ms": {
    "mean": 0.0,
    "p50": 0.0,
    "p95": 0.0,
    "p99": 0.0,
    "max": 0.0
  }
}
```
