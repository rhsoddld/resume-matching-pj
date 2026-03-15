# Eval Results Archive

- Generated at (UTC): `2026-03-15 06:16:30`
- Commit: `726bfe031fb3`
- Golden set: `src/eval/golden_set.jsonl`
- Rubric: `docs/eval/llm_judge_softskill_potential_rubric.md`

## Custom Eval (Skill/Experience/Culture/Potential)

```json
{
  "counts": {
    "good": 12,
    "neutral": 1,
    "bad": 2
  },
  "by_label_avg": {
    "good": {
      "skill": 0.9554,
      "experience": 0.7932,
      "culture": 1.0,
      "potential": 1.0,
      "quality": 0.9201
    },
    "neutral": {
      "skill": 0.4,
      "experience": 0.875,
      "culture": 0.6667,
      "potential": 0.0,
      "quality": 0.5558
    },
    "bad": {
      "skill": 0.0,
      "experience": 0.0,
      "culture": 0.0,
      "potential": 0.0,
      "quality": 0.0
    }
  }
}
```

## Diversity Report

```json
{
  "total_entries": 15,
  "label_distribution": {
    "bad": 2,
    "good": 12,
    "neutral": 1
  },
  "family_distribution": {
    "backend": 2,
    "data": 3,
    "devops_cloud": 2,
    "frontend": 1,
    "mobile_blockchain": 2,
    "non_tech": 2,
    "product_business": 2,
    "security": 1
  },
  "family_count": 8,
  "family_entropy": 2.9232,
  "family_entropy_normalized": 0.9744,
  "skill_vocabulary_size": 81
}
```

## LLM-as-Judge (Rubric-Based)

```json
{
  "status": "skipped",
  "reason": "OPENAI_API_KEY not set"
}
```
