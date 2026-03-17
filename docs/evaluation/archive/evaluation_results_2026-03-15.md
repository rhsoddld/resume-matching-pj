# Eval Results Archive

> **Note**: This file is an **archive snapshot (2026-03-15)**.  
> For the current evaluation status and recommendations, see `../short_eval_status_2026-03-17.md`.

## Current Status

- **Latest short-eval**: [short_eval_status_2026-03-17.md](../short_eval_status_2026-03-17.md)
- **LLM-as-Judge 설계·스키마**: [llm_judge_design.md](../llm_judge_design.md)
- 이 문서는 과거 스냅샷 아카이브용이다.

**아카이브 메타**

| 항목 | 값 |
|------|-----|
| Generated (UTC) | 2026-03-15 11:37:28 |
| Commit | `8b7567c7c48e` |
| Golden set | `src/eval/golden_set.jsonl` |
| Rubric | internal judge (soft skill + potential) |

---

## Merged Legacy Snapshots (2026-03-15)

아래는 기존 `docs/eval/*`에서 병합한 요약이다.

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

**해석**: 해당 스냅샷 기준 LLM rerank는 품질 proxy 개선보다 지연 증가가 더 컸다. rerank는 기본 상시 경로가 아니라 gate 기반 optional 경로가 타당하다.

### Judge Rubric Hard Rules (Restored)

1. soft-skill/potential 증거가 모두 부족하면 score ≤ 0.40  
2. 협업/소유권 요구와 명백히 모순되면 score ≤ 0.50  
3. generic evidence는 0.74 상한  
4. 구체적/일관/성장 증거가 충분하면 ≥ 0.75  

---

## Custom Eval (Skill / Experience / Culture / Potential)

**라벨별 개수**: good 28, neutral 8, bad 14

| Label | skill | experience | culture | potential | quality |
|-------|------:|-----------:|--------:|----------:|--------:|
| good | 0.905 | 0.847 | 1.0 | 0.75 | 0.891 |
| neutral | 0.377 | 0.713 | 0.917 | 1.0 | 0.648 |
| bad | 0.0 | 0.0 | 0.667 | 0.0 | 0.133 |

---

## Diversity Report

| 항목 | 값 |
|------|-----|
| total_entries | 50 |
| good / neutral / bad | 28 / 8 / 14 |
| family_count | 8 |
| family_entropy (norm) | 2.733 (0.911) |
| skill_vocabulary_size | 282 |

**Family 분포**: backend 10, data 8, devops_cloud 4, frontend 2, mobile_blockchain 3, non_tech 14, product_business 6, security 3

---

## LLM-as-Judge (Rubric-Based)

- **상세 샘플 50건**: [evaluation_results_llm_judge_samples.json](evaluation_results_llm_judge_samples.json)

| 항목 | 값 |
|------|-----|
| status | ok |
| model | gpt-4o (judge-v1) |
| sample_size | 50 |
| average_score | 0.5667 |
| score_dispersion | 0.6433 (excellent) |

**라벨별 평균 점수**

| Label | 평균 score |
|-------|-----------:|
| bad | 0.1695 |
| good | 0.8128 |
| neutral | 0.4001 |

good/bad 구분이 잘 되고, neutral은 중간 구간에 위치함.
