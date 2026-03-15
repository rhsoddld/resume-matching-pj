# LLM Rerank Comparison

이 문서는 `HCR.3` 강화를 위한 `LLM rerank on/off` 비교 실험 결과를 정리한다.

## Experiment Goal

- baseline shortlist와 `LLM rerank` shortlist를 같은 입력에 대해 비교한다.
- 품질 지표는 `expected_skills` 대비 후보 skill overlap의 proxy score를 사용한다.
- 이 점수는 최종 relevance의 완전한 대체는 아니며, shortlist refinement 경향을 보기 위한 lightweight proxy다.

## Run Metadata

- Generated at (UTC): `2026-03-15 08:33:33`
- Input dataset: `/Users/lee/Desktop/resume-matching-pj/src/eval/golden_set.jsonl`
- Query count: `5`
- top_k: `5`
- rerank_top_n: `20`
- rerank model: `gpt-4o`

- rerank model version: `hq-v1`

## Aggregate Summary

| Metric | Value |
|---|---|
| Baseline avg overlap@k | `0.3774` |
| LLM rerank avg overlap@k | `0.3312` |
| Delta avg overlap@k | `-0.0461` |
| Baseline avg top1 overlap | `0.4479` |
| LLM rerank avg top1 overlap | `0.4062` |
| Delta avg top1 overlap | `-0.0417` |
| Reordered cases | `5` / `5` |
| Avg LLM rerank latency (ms) | `3344.815` |

## Case Summary

| Query | Family | Baseline avg@k | LLM avg@k | Delta | LLM latency ms |
|---|---|---:|---:|---:|---:|
| `gs-001` | `data` | `0.125` | `0.2` | `0.075` | `3156.776` |
| `gs-002` | `frontend` | `0.4` | `0.28` | `-0.12` | `3323.078` |
| `gs-003` | `devops_cloud` | `0.6286` | `0.5429` | `-0.0857` | `3245.041` |
| `gs-004` | `backend` | `0.3333` | `0.2333` | `-0.1` | `3915.438` |
| `gs-005` | `product_business` | `0.4` | `0.4` | `0.0` | `3083.74` |

## Interpretation

- `Delta avg overlap@k`가 양수면 expected skill proxy 기준으로 shortlist 품질이 개선된 것이다.
- `Reordered cases`가 0보다 크면 LLM rerank가 실제로 shortlist 순서를 바꿨음을 뜻한다.
- latency는 rerank 단계 추가 비용이므로, timeout/fallback 정책과 함께 해석해야 한다.

## Raw Aggregate JSON

```json
{
  "case_count": 5,
  "baseline_avg_overlap_at_k": 0.3774,
  "llm_avg_overlap_at_k": 0.3312,
  "delta_avg_overlap_at_k": -0.0461,
  "baseline_avg_top1_overlap": 0.4479,
  "llm_avg_top1_overlap": 0.4062,
  "delta_avg_top1_overlap": -0.0417,
  "reordered_cases": 5,
  "avg_llm_rerank_latency_ms": 3344.815
}
```
