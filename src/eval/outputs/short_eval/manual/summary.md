# Eval Mode Summary

- generated_at_utc: `2026-03-16T19:39:26Z`
- run_dir: `src/eval/outputs/short_eval/manual`

| mode | run_id | recall@10 | recall@20 | mrr | ndcg@5 | mrr_delta | top1_imp_rate | groundedness | consistency | e2e_p95_ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hybrid | eval-20260316T192741Z-667c3cd6 | 0.525 | 0.7125 | 0.6096 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 559.6739 |
| rerank | eval-20260316T192803Z-df09774d | 0.525 | 0.7125 | 0.6096 | 0.3229 | -0.0949 | 0.1875 | 0.0 | 0.0 | 9864.4375 |
| agent | - | - | - | - | - | - | - | - | - | - |

## Notes
- `hybrid`: retrieval/query-understanding 중심
- `rerank`: rerank delta 및 top1 개선률 확인
- `agent`: 설명/근거성/일관성 지표 확인
