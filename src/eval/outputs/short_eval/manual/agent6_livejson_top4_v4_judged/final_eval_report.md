# Final Evaluation Report

## Run Metadata

- Run ID: `eval-20260316T210104Z-d1928143`
- Started at (UTC): `2026-03-16T21:01:04Z`
- Finished at (UTC): `2026-03-16T21:04:00Z`
- Golden set: `src/eval/subsets/golden.agent.jsonl`
- Total queries: `6`
- Successful queries: `6`

## Aggregate Metrics

| Metric | Value |
|---|---|
| Query role extraction accuracy | 0.5000 |
| Query skill extraction accuracy | 0.1333 |
| Retrieval Recall@10 | 0.8000 |
| Retrieval Recall@20 | 0.8667 |
| Retrieval MRR | 0.9167 |
| Rerank NDCG@5 | 0.0000 |
| Rerank MRR delta | 0.0000 |
| Human agreement | - |
| LLM-as-Judge agreement | 0.4000 |
| LLM explanation quality | 0.7200 |
| LLM explanation groundedness | 0.7200 |
| Agent explanation presence | 1.0000 |
| Agent groundedness | 0.2177 |
| End-to-end latency p95 (ms) | 45258.3658 |
| Cost/request (USD) | 0.0022 |
| Fallback trigger rate | 0.0000 |
| Error rate | 0.0000 |

## Per-Query Summary

| query_id | Recall@10 | MRR | NDCG@5 | E2E latency(ms) | status |
|---|---|---|---|---|---|
| gs-q-016 | 1.0000 | 1.0000 | 0.0000 | 25225.3183 | ok |
| gs-q-018 | 0.8000 | 1.0000 | 0.0000 | 25105.5765 | ok |
| gs-q-009 | 0.8000 | 1.0000 | 0.0000 | 24614.7594 | ok |
| gs-q-010 | 0.8000 | 1.0000 | 0.0000 | 51751.9187 | ok |
| gs-q-013 | 0.8000 | 1.0000 | 0.0000 | 23422.5100 | ok |
| gs-q-005 | 0.6000 | 0.5000 | 0.0000 | 25777.7070 | ok |

## Rerank Delta Summary

- NDCG@5 (reranked): `0.0000`
- MRR delta: `0.0000`
- Top-1 improvement rate: `0.0000`
- Added latency (ms): `0.0000`
- Gate enabled this run: `False`
- Gate reason: `disabled_by_config`

## Agent Quality Summary

- LLM-as-Judge agreement: `0.4000`
- LLM explanation quality: `0.7200`
- LLM explanation groundedness: `0.7200`
- Explanation presence rate: `1.0000`
- Explanation groundedness (heuristic): `0.2177`
- Dimension consistency (heuristic): `0.8857`

## Latency/Cost Summary

- End-to-end latency p50/p95/p99 (ms): `25165.4474` / `45258.3658` / `50453.2082`
- Stage latency (retrieval p95 ms): `913.7271`
- Total tokens/request: `790.5833`
- Estimated cost/request (USD): `0.0022`
- Candidates/sec: `36.0361`

## Known Limitations

- Human/LLM agreement requires JSONL reference files with query_id + top1_is_relevant.
- Token/cost fields are currently heuristic estimates until exact provider usage telemetry is exposed per stage.
- Fallback/error counts are query-level rates; candidate-level runtime fallback/error counts are reported in reliability.counts.

## Next Actions

1. Wire explicit query-understanding extractor hook to production endpoint for exact parser parity.
1. Attach token usage instrumentation from retrieval/rerank/agent calls into adapter token_usage payload.
1. Run eval_runner on a schedule and enforce calibrated thresholds for Recall@20, NDCG@5, and degraded-mode success rate.
