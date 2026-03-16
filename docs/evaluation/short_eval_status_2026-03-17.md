# Short Eval Status (2026-03-17)

## Scope

This document summarizes the recent short-path evaluation work across hybrid retrieval, rerank, and agent evaluation.
It captures:

- what was measured
- what was unstable vs stabilized
- what artifacts are worth keeping
- what tasks remain
- what direction the project should take next

Primary retained artifacts:

- hybrid / rerank summary: `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/summary.md`
- agent stability and tuning comparison: `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent_baseline_comparison.md`
- stable agent baseline: `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_baseline`
- top-3 latency experiment: `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_top3`
- top-4 prompt-v4 experiment: `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_top4_v4`
- LLM judge design: `/Users/lee/Desktop/resume-matching-pj/docs/evaluation/llm_judge_design.md`

Cleanup performed:

- removed empty abandoned run directories:
  - `src/eval/outputs/short_eval/manual/agent`
  - `src/eval/outputs/short_eval/manual/agent2`
  - `src/eval/outputs/short_eval/manual/agent6`

## Executive Summary

1. Hybrid retrieval is useful on hard-query subsets and should stay.
2. Rerank is not justified in the default path right now.
3. Agent evaluation became stable only after bypassing `sdk_handoff` in eval mode.
4. The main bottleneck has moved from runtime instability to explanation quality.
5. `agent_eval_top_n=4` with prompt v4 is the best current cost/quality compromise.
6. `LLM-as-Judge` was placeholder-only before this cleanup and now has a real generation path.

## LLM-as-Judge Status

Before this cleanup:

- `src/eval/llm_judge_annotations.jsonl` was effectively a placeholder
- short eval runs therefore showed `llm_as_judge_agreement = null`

Current state:

- a stage-aware generation loop now exists at:
  - `/Users/lee/Desktop/resume-matching-pj/src/eval/generate_llm_judge_annotations.py`
- schema/design is documented at:
  - `/Users/lee/Desktop/resume-matching-pj/docs/evaluation/llm_judge_design.md`
- first generated run:
  - run id: `judge-20260316T205123Z-ff8954f7`
  - records: `6`
  - live judge success: `6`
  - bootstrap fallback: `0`

Important note:

- current live judge coverage should still be treated as early-stage and subset-scoped, not yet as a full production KPI

## Stage Summary

### Hybrid

Reference run:
- `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/hybrid`

Key metrics:
- `recall@10 = 0.525`
- `recall@20 = 0.7125`
- `mrr = 0.6096`
- `must_have_coverage = 0.725`
- `e2e p95 = 559.6739 ms`

Interpretation:
- lexical retrieval is already strong in many cases
- hybrid still matters on difficult slices and should remain the retrieval default

### Rerank

Reference run:
- `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/rerank`

Key metrics:
- `ndcg@5 = 0.3229`
- `mrr_delta = -0.0949`
- `top1_improvement_rate = 0.1875`
- `added_latency_ms = 7268.1267`
- `e2e p95 = 9864.4375 ms`

Interpretation:
- rerank helps some ties, but aggregate value is negative
- current recommendation remains: keep rerank disabled by default

### Agent: unstable phase

Observed before eval-only SDK bypass:

- short agent eval runs often failed to finish cleanly
- no completed agent artifact was available in the original short summary
- repeated failure classes:
  - `ScorePackOutput` schema mismatch
  - negotiation schema mismatch
  - SDK handoff/event-loop instability
  - long idle tails without useful completion

Interpretation:
- agent quality could not be evaluated cleanly while the runtime itself was unstable

### Agent: stable baseline

Reference run:
- `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_baseline`

Configuration:
- eval-only SDK bypass
- path effectively `live_json -> heuristic`
- `agent_eval_top_n = 5`

Key metrics:
- successful queries: `6/6`
- explanation presence: `0.5000`
- groundedness: `0.0648`
- dimension consistency: `0.4080`
- `e2e p95 = 19843.8624 ms`
- `agent_eval p95 = 19261.5709 ms`
- `cost/request = 0.0017`
- fallback/error rate = `0`

Interpretation:
- stability baseline achieved
- the next problem is quality, not runtime survivability

### Agent: top-3 latency experiment

Reference run:
- `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_top3`

Key metrics:
- explanation presence: `0.3000`
- groundedness: `0.0408`
- dimension consistency: `0.2456`
- `e2e p95 = 18141.0053 ms`
- `cost/request = 0.0013`

Interpretation:
- top-3 improves latency/cost
- quality drops too much

### Agent: top-4 prompt-v4 experiment

Reference run:
- `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_top4_v4`

Configuration:
- eval-only SDK bypass
- `agent_eval_top_n = 4`
- prompt v4 with evidence-token explanation template

Key metrics:
- explanation presence: `0.4000`
- groundedness: `0.0832`
- dimension consistency: `0.3323`
- `e2e p95 = 19551.8936 ms`
- `e2e mean = 16615.5136 ms`
- `cost/request = 0.0014`
- fallback/error rate = `0`

Interpretation:
- top-4 sits between top-5 and top-3 on latency/cost
- groundedness improved above the old top-5 baseline after explanation template changes
- this is the best current compromise

### Agent: top-4 prompt-v4 re-run with LLM judge annotations

Reference run:
- `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_top4_v4_judged`

Key metrics:
- `llm_as_judge_agreement = 0.4000`
- `llm_explanation_quality_score = 0.7200`
- `llm_explanation_groundedness_score = 0.7200`
- `explanation_presence_rate = 1.0000`
- `groundedness_score = 0.2177`
- `dimension_consistency_score = 0.8857`
- `e2e p95 = 45258.3658 ms`

Interpretation:
- the new judge file is now wired into the report correctly
- deterministic explanation backfill raised explanation presence materially
- heuristic groundedness and consistency also improved
- latency remains too high for this to be treated as a final operating point

## Why Groundedness Was Low

Root cause from explanation inspection:

1. Explanations were too generic.
   - phrases like `strong experience`, `technical expertise`, `good skill match` appeared often

2. The groundedness heuristic rewards literal token overlap.
   - it checks whether explanation text mentions expected skill tokens and candidate skill tokens

3. The old explanation style named only a few tools.
   - for example, it might mention `AWS`, `Terraform`, `Kubernetes`, `Linux`
   - but omit many candidate evidence tokens such as `ec2`, `vpc`, `cloudwatch`, `jenkins`

4. Explanation presence itself was only partial.
   - with `top_n=5`, only agent-evaluated rows contribute explanations
   - non-agent rows remain explanation-free and drag the aggregate down

## What Changed In Prompt v4

The current explanation path now forces an evidence-token-centric template:

- `Matched required skills: ...`
- `Candidate evidence tokens: ...; missing or weaker skills: ...`
- `Scores/weights: ...`

Why this matters:
- it directly aligns explanation text with the groundedness heuristic
- it makes explanations less fluent-but-generic and more literal/evidence-bearing

## Current Recommendation

### Keep

- hybrid retrieval as default retrieval path
- rerank disabled by default
- eval-only SDK bypass until Agents SDK handoff is proven stable
- `agent_eval_top_n=4` as the current evaluation tuning point
- prompt v4 evidence-token explanation template

### Do Not Adopt Yet

- restoring `sdk_handoff` in evaluation
- enabling rerank broadly
- dropping to `agent_eval_top_n=3` as the default quality benchmark

## Task Backlog

### Immediate

1. Re-run the stable agent baseline on a slightly larger subset or full golden slice using prompt v4.
2. Compare `top_n=4` vs `top_n=5` under the same prompt version to isolate the pure top-N effect.
3. Persist runtime-mode breakdown (`live_json`, `heuristic`, `deterministic_only`) into eval artifacts.

### Near-Term

1. Improve explanation presence without forcing evaluation on all top-10 candidates.
2. Add backoff/rate-limit resilience for manual explanation probes and batch evals.
3. Replace heuristic token estimates with exact token usage instrumentation.

### Medium-Term

1. Revisit `sdk_handoff` only after the event-loop/runtime issue is fixed in isolation.
2. Decide whether the evidence-token template should become the production explanation format.
3. Add a clean reviewer-facing benchmark table comparing retrieval, rerank, and agent ROI.

### Open Product/Engineering Issue

1. Streaming candidate order is still nondeterministic on cache miss and should be fixed separately from eval work.

## Artifact Policy

Commit:

- docs in `docs/evaluation/`
- `src/eval/llm_judge_annotations.jsonl`
- reviewer-facing markdown summaries

Do not commit:

- raw short-eval run directories in `src/eval/outputs/short_eval/manual/*/`
- ad-hoc JSON artifacts at the manual root unless they become a declared baseline

## Forward Direction

The project direction is now clearer than before:

1. Retrieval remains the foundation. Preserve hybrid retrieval and keep tuning query understanding.
2. Rerank should stay optional until it proves real value on quality-per-latency.
3. Agent work should focus on explanation quality and consistency, not on adding more orchestration complexity.
4. Simpler and observable execution paths are winning.
5. The next strong milestone is:
   - stable live-json agent path
   - prompt v4 or better evidence-token explanations
   - `top_n=4` or `top_n=5` chosen via clean A/B comparison under the same prompt version
   - LLM judge agreement used as a secondary evaluation lens, not a replacement for golden truth
