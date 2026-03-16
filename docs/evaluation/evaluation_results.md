# Eval Results Archive

## Current Status

- Latest short-eval status and recommendation:
  - `/Users/lee/Desktop/resume-matching-pj/docs/evaluation/short_eval_status_2026-03-17.md`
- LLM-as-Judge design and current schema:
  - `/Users/lee/Desktop/resume-matching-pj/docs/evaluation/llm_judge_design.md`
- This file is now treated as an archive of earlier snapshots.

- Generated at (UTC): `2026-03-15 11:37:28`
- Commit: `8b7567c7c48e`
- Golden set: `src/eval/golden_set.jsonl`
- Rubric: internal judge rubric (`soft skill + potential`)

## Merged Legacy Snapshots (2026-03-15)

아래 항목은 기존 `docs/eval/*`에서 현재 문서로 병합한 요약이다.

### Retrieval Quality Snapshot

| Metric | Value | Target | Status |
|---|---:|---:|---|
| avg precision@10 | 0.0073 | - | - |
| avg recall@10 | 0.4725 | >= 0.50 | MISS |
| F1@10 | 0.0144 | - | - |

### Retrieval Benchmark Snapshot

| Metric | Value |
|---|---:|
| success rate | 1.0 |
| candidates/sec | 60.2076 |
| calls/sec | 7.8769 |
| latency mean | 498.276 ms |
| latency p95 | 1069.8 ms |
| latency p99 | 2834.231 ms |
| latency max | 3121.926 ms |

### LLM Rerank Comparison Snapshot

| Metric | Value |
|---|---:|
| baseline avg overlap@k | 0.3774 |
| LLM rerank avg overlap@k | 0.3312 |
| delta avg overlap@k | -0.0461 |
| baseline avg top1 overlap | 0.4479 |
| LLM rerank avg top1 overlap | 0.4062 |
| delta avg top1 overlap | -0.0417 |
| reordered cases | 5 / 5 |
| avg rerank latency | 3344.815 ms |

해석:
- 해당 스냅샷 기준으로 LLM rerank는 품질 proxy 개선보다 지연 증가가 더 컸다.
- 따라서 rerank는 기본 상시 경로가 아니라 gate 기반 optional 경로가 타당하다.

### Judge Rubric Hard Rules (Restored)

1. soft-skill/potential 증거가 모두 부족하면 score는 `<= 0.40`
2. 협업/소유권 요구와 명백히 모순되면 score는 `<= 0.50`
3. generic evidence는 `0.74` 상한
4. 구체적/일관/성장 증거가 충분하면 `>= 0.75`

## Custom Eval (Skill/Experience/Culture/Potential)

```json
{
  "counts": {
    "good": 28,
    "neutral": 8,
    "bad": 14
  },
  "by_label_avg": {
    "good": {
      "skill": 0.9046,
      "experience": 0.8471,
      "culture": 1.0,
      "potential": 0.75,
      "quality": 0.891
    },
    "neutral": {
      "skill": 0.3774,
      "experience": 0.713,
      "culture": 0.9167,
      "potential": 1.0,
      "quality": 0.6482
    },
    "bad": {
      "skill": 0.0,
      "experience": 0.0,
      "culture": 0.6667,
      "potential": 0.0,
      "quality": 0.1333
    }
  }
}
```

## Diversity Report

```json
{
  "total_entries": 50,
  "label_distribution": {
    "bad": 14,
    "good": 28,
    "neutral": 8
  },
  "family_distribution": {
    "backend": 10,
    "data": 8,
    "devops_cloud": 4,
    "frontend": 2,
    "mobile_blockchain": 3,
    "non_tech": 14,
    "product_business": 6,
    "security": 3
  },
  "family_count": 8,
  "family_entropy": 2.733,
  "family_entropy_normalized": 0.911,
  "skill_vocabulary_size": 282
}
```

## LLM-as-Judge (Rubric-Based)

```json
{
  "status": "ok",
  "model": "gpt-4o",
  "model_version": "judge-v1",
  "sample_size": 50,
  "average_score": 0.5667,
  "per_label_avg": {
    "bad": 0.1695,
    "good": 0.8128,
    "neutral": 0.4001
  },
  "score_dispersion": 0.6433,
  "dispersion_interpretation": "excellent",
  "samples": [
    {
      "id": "gs-001",
      "label": "good",
      "score": 0.8363
    },
    {
      "id": "gs-002",
      "label": "good",
      "score": 0.8346
    },
    {
      "id": "gs-003",
      "label": "good",
      "score": 0.8176
    },
    {
      "id": "gs-004",
      "label": "good",
      "score": 0.8755
    },
    {
      "id": "gs-005",
      "label": "good",
      "score": 0.7464
    },
    {
      "id": "gs-006",
      "label": "good",
      "score": 0.874
    },
    {
      "id": "gs-007",
      "label": "bad",
      "score": 0.2316
    },
    {
      "id": "gs-008",
      "label": "good",
      "score": 0.8672
    },
    {
      "id": "gs-009",
      "label": "good",
      "score": 0.7988
    },
    {
      "id": "gs-010",
      "label": "good",
      "score": 0.8225
    },
    {
      "id": "gs-011",
      "label": "good",
      "score": 0.8092
    },
    {
      "id": "gs-012",
      "label": "neutral",
      "score": 0.4188
    },
    {
      "id": "gs-013",
      "label": "good",
      "score": 0.7024
    },
    {
      "id": "gs-014",
      "label": "good",
      "score": 0.6894
    },
    {
      "id": "gs-015",
      "label": "bad",
      "score": 0.2022
    },
    {
      "id": "gs-016",
      "label": "good",
      "score": 0.8874
    },
    {
      "id": "gs-017",
      "label": "good",
      "score": 0.8345
    },
    {
      "id": "gs-018",
      "label": "good",
      "score": 0.7167
    },
    {
      "id": "gs-019",
      "label": "good",
      "score": 0.8796
    },
    {
      "id": "gs-020",
      "label": "good",
      "score": 0.7754
    },
    {
      "id": "gs-021",
      "label": "good",
      "score": 0.8686
    },
    {
      "id": "gs-022",
      "label": "good",
      "score": 0.8121
    },
    {
      "id": "gs-023",
      "label": "good",
      "score": 0.7061
    },
    {
      "id": "gs-024",
      "label": "good",
      "score": 0.7666
    },
    {
      "id": "gs-025",
      "label": "good",
      "score": 0.8516
    },
    {
      "id": "gs-026",
      "label": "good",
      "score": 0.8022
    },
    {
      "id": "gs-027",
      "label": "good",
      "score": 0.797
    },
    {
      "id": "gs-028",
      "label": "good",
      "score": 0.8114
    },
    {
      "id": "gs-029",
      "label": "good",
      "score": 0.8806
    },
    {
      "id": "gs-030",
      "label": "good",
      "score": 0.8844
    },
    {
      "id": "gs-031",
      "label": "good",
      "score": 0.8111
    },
    {
      "id": "gs-032",
      "label": "neutral",
      "score": 0.3955
    },
    {
      "id": "gs-033",
      "label": "neutral",
      "score": 0.4694
    },
    {
      "id": "gs-034",
      "label": "neutral",
      "score": 0.3731
    },
    {
      "id": "gs-035",
      "label": "neutral",
      "score": 0.3679
    },
    {
      "id": "gs-036",
      "label": "neutral",
      "score": 0.3868
    },
    {
      "id": "gs-037",
      "label": "neutral",
      "score": 0.3976
    },
    {
      "id": "gs-038",
      "label": "neutral",
      "score": 0.3917
    },
    {
      "id": "gs-039",
      "label": "bad",
      "score": 0.1993
    },
    {
      "id": "gs-040",
      "label": "bad",
      "score": 0.1854
    },
    {
      "id": "gs-041",
      "label": "bad",
      "score": 0.1329
    },
    {
      "id": "gs-042",
      "label": "bad",
      "score": 0.1711
    },
    {
      "id": "gs-043",
      "label": "bad",
      "score": 0.1432
    },
    {
      "id": "gs-044",
      "label": "bad",
      "score": 0.1722
    },
    {
      "id": "gs-045",
      "label": "bad",
      "score": 0.128
    },
    {
      "id": "gs-046",
      "label": "bad",
      "score": 0.1655
    },
    {
      "id": "gs-047",
      "label": "bad",
      "score": 0.1629
    },
    {
      "id": "gs-048",
      "label": "bad",
      "score": 0.1205
    },
    {
      "id": "gs-049",
      "label": "bad",
      "score": 0.1544
    },
    {
      "id": "gs-050",
      "label": "bad",
      "score": 0.2038
    }
  ]
}
```
