# Eval Results Archive

> **Note**: This file is an **archive snapshot (2026-03-15)**.  
> For the current evaluation status and recommendations, see `../short_eval_status_2026-03-17.md`.

## Current Status

- **Latest short-eval**: [short_eval_status_2026-03-17.md](../short_eval_status_2026-03-17.md)
- **LLM-as-Judge design/schema**: [llm_judge_design.md](../llm_judge_design.md)
- This document is for historical snapshot archiving.

**Archive metadata**

| Item | Value |
|------|-----|
| Generated (UTC) | 2026-03-15 11:37:28 |
| Commit | `8b7567c7c48e` |
| Golden set | `src/eval/golden_set.jsonl` |
| Rubric | internal judge (soft skill + potential) |

---

## Merged Legacy Snapshots (2026-03-15)

Below is a merged summary from legacy `docs/eval/*` snapshots.

### Retrieval Quality

| Metric | Value | Target | Status |
|--------|------:|------:|--------|
| avg precision@10 | 0.0073 | — | — |
| avg recall@10 | 0.4725 | ≥ 0.50 | MISS |
| F1@10 | 0.0144 | — | — |

### Retrieval Benchmark

| Metric | Value |
|--------|------:|
| success rate | 1.0 |
| candidates/sec | 60.21 |
| calls/sec | 7.88 |
| latency mean | 498.3 ms |
| latency p95 | 1070 ms |
| latency p99 | 2834 ms |
| latency max | 3122 ms |

### LLM Rerank Comparison

| Metric | Value |
|--------|------:|
| baseline avg overlap@k | 0.3774 |
| LLM rerank avg overlap@k | 0.3312 |
| delta avg overlap@k | -0.0461 |
| baseline avg top1 overlap | 0.4479 |
| LLM rerank avg top1 overlap | 0.4062 |
| delta avg top1 overlap | -0.0417 |
| reordered cases | 5 / 5 |
| avg rerank latency | 3345 ms |

**Interpretation**: in this snapshot, LLM rerank increased latency more than it improved the quality proxy. Keeping rerank as a gated optional path (not always-on) is justified.

### Judge Rubric Hard Rules (Restored)

1. if soft-skill/potential evidence is missing, score ≤ 0.40  
2. if it clearly contradicts collaboration/ownership requirements, score ≤ 0.50  
3. generic evidence is capped at 0.74
4. if evidence is specific/consistent/growth-oriented and sufficient, ≥ 0.75  

---

## Custom Eval (Skill / Experience / Culture / Potential)

**Counts by label**: good 28, neutral 8, bad 14

| Label | skill | experience | culture | potential | quality |
|-------|------:|-----------:|--------:|----------:|--------:|
| good | 0.905 | 0.847 | 1.0 | 0.75 | 0.891 |
| neutral | 0.377 | 0.713 | 0.917 | 1.0 | 0.648 |
| bad | 0.0 | 0.0 | 0.667 | 0.0 | 0.133 |

---

## Diversity Report

| Item | Value |
|------|-----|
| total_entries | 50 |
| good / neutral / bad | 28 / 8 / 14 |
| family_count | 8 |
| family_entropy (norm) | 2.733 (0.911) |
| skill_vocabulary_size | 282 |

**Family distribution**: backend 10, data 8, devops_cloud 4, frontend 2, mobile_blockchain 3, non_tech 14, product_business 6, security 3

---

## LLM-as-Judge (Rubric-Based)

- **50 detailed samples**: [evaluation_results_llm_judge_samples.json](evaluation_results_llm_judge_samples.json)

| Item | Value |
|------|-----|
| status | ok |
| model | gpt-4o (judge-v1) |
| sample_size | 50 |
| average_score | 0.5667 |
| score_dispersion | 0.6433 (excellent) |

**Average score by label**

| Label | avg score |
|-------|-----------:|
| bad | 0.1695 |
| good | 0.8128 |
| neutral | 0.4001 |

Good/bad separation is strong, with neutral positioned in the middle band.
