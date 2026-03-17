# Current Eval Conclusion

This file keeps only the conclusions we should carry forward right now.

## Final Position

1. Keep hybrid retrieval enabled.
2. Keep reranking disabled in the default path.
3. Do not re-enable `sdk_handoff` for eval runs.
4. Keep `agent_eval_top_n=4` as the current tuning baseline.
5. Keep explanations in the evidence-token style.
6. Treat `LLM-as-Judge` as an auxiliary metric only.

## Why

- Hybrid still helps on hard subsets.
- Reranking did not justify its latency overhead.
- The agent runtime evaluated stably only on the `live_json -> heuristic` path.
- Explanation quality improved, but latency is still high.

## Current Best Reference Run

- judged agent run:
  - [final_eval_report.md](outputs/short_eval/manual/agent6_livejson_top4_v4_judged/final_eval_report.md)

Key metrics:

- `llm_as_judge_agreement = 0.4000`
- `llm_explanation_quality_score = 0.7200`
- `llm_explanation_groundedness_score = 0.7200`
- `explanation_presence_rate = 1.0000`
- `groundedness_score = 0.2177`
- `dimension_consistency_score = 0.8857`
- `e2e p95 = 45258.3658 ms`

## Interpretation

- Explanation presence is no longer a problem.
- Groundedness and consistency improved compared to earlier runs.
- However, latency is high, so this is not ready to be adopted as the final production path.

## Practical Decision

- For now, it is better to lock in the current conclusion rather than widen eval coverage.
- Next priority is reducing operational latency rather than running more new evaluations.

## Do Not Spend More Time On

- Expanding rerank re-experiments
- Re-enabling `sdk_handoff` in eval
- Treating judge outputs as if they were golden truth

## If We Resume Later

1. Re-compare `top_n=4` vs `5` using the same prompt version
2. Shorten deterministic explanations to reduce latency/cost
3. Analyze a small set of queries where judge and golden disagree
