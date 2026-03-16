# LLM-as-Judge Design

## Current Status

`LLM-as-Judge` was previously in a placeholder state.

- previous file: `src/eval/llm_judge_annotations.jsonl`
- previous content: a single example row
- consequence: short-eval runs showed `llm_as_judge_agreement = null`

As of the current evaluation cleanup, the judge flow is now defined as a stage-aware annotation loop over the active golden subset.

Current generated run:

- run id: `judge-20260316T205123Z-ff8954f7`
- golden subset: `src/eval/subsets/golden.agent.jsonl`
- records: `6`
- live LLM successes: `6`
- bootstrap fallbacks: `0`

## Design Goal

Use one compact annotation format that can support both:

1. current offline agreement checks
2. future explanation-quality judging

The unit of annotation is:

- `query_id`
- `candidate_id`
- `stage`

For now, the active stage is `agent_top1`.

## Annotation Schema (v2)

Each JSONL row should contain:

```json
{
  "query_id": "gs-q-016",
  "candidate_id": "suri-308",
  "stage": "agent_top1",
  "top1_is_relevant": true,
  "golden_top1_is_relevant": true,
  "judge_source": "live_llm",
  "judge_model": "gpt-4o",
  "judge_model_version": "judge-v1",
  "judge_prompt_version": "llm-judge-v2",
  "agent_prompt_version": "agent-prompts-v4",
  "generated_at_utc": "2026-03-17T00:00:00Z",
  "generator_run_id": "judge-...",
  "job_family": "cloud_devops",
  "expected_role": "cloud/devops engineer",
  "expected_skills": ["aws", "kubernetes", "terraform", "ci/cd", "linux"],
  "expected_optional_skills": ["argocd", "helm", "observability"],
  "relevance_rationale": "short judge rationale",
  "explanation_quality": {
    "overall_score": 0.78,
    "groundedness_score": 0.82,
    "coverage_score": 0.70,
    "specificity_score": 0.74,
    "pass": true,
    "rationale": "short explanation-quality rationale"
  },
  "top1_snapshot": {
    "candidate_id": "suri-308",
    "score": 0.81,
    "summary": "...",
    "experience_years": 8.0,
    "seniority_level": "senior",
    "skills": ["aws", "terraform", "kubernetes"],
    "agent_scores": {
      "skill": 0.85,
      "experience": 0.90
    },
    "agent_explanation": "Matched required skills: ..."
  }
}
```

## Generation Loop

The generator is:

- [generate_llm_judge_annotations.py](/Users/lee/Desktop/resume-matching-pj/src/eval/generate_llm_judge_annotations.py)

Loop:

1. load `golden.agent.jsonl`
2. run current agent path for each query
3. capture top-1 candidate snapshot
4. ask live judge model for:
   - `top1_is_relevant`
   - explanation quality block
5. if live judge is unavailable, fall back to bootstrap heuristic
6. write stage-aware JSONL rows to `src/eval/llm_judge_annotations.jsonl`

## Bootstrap Fallback

Fallback mode is intentionally explicit:

- `judge_source = bootstrap_heuristic`
- explanation quality is computed from:
  - literal token overlap
  - explanation groundedness heuristic
  - dimension consistency heuristic

This keeps the file usable even when live judge execution is unavailable, while making it easy to distinguish from true LLM-judged rows.

## Integration Notes

Current eval integration supports:

1. candidate-aware `llm_as_judge_agreement` when `query_id + candidate_id` rows are available
2. optional aggregation of:
   - `llm_explanation_quality_score`
   - `llm_explanation_groundedness_score`

## Decision

Treat `src/eval/llm_judge_annotations.jsonl` as a versioned evaluation artifact, not as disposable output.
