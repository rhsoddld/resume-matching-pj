# Team Eval Snapshot (2026-03-17)

## Bottom Line

- hybrid retrieval stays
- rerank stays off by default
- agent eval is stable in eval mode only when `sdk_handoff` is bypassed
- explanation quality is now the main improvement target
- `agent_eval_top_n=4` is the current practical tuning point

## What Changed

1. short-eval outputs were cleaned up
2. empty abandoned run directories were removed
3. prompt v4 pushed explanations toward evidence-token wording
4. eval mode now bypasses unstable SDK handoff
5. `LLM-as-Judge` moved from placeholder-only to a real generation loop design
6. the first generated judge run completed with `6/6` live-LLM rows and `0` bootstrap fallbacks

## Current Recommended Defaults

- retrieval: keep hybrid
- rerank: disabled unless A/B proof turns positive
- agent eval in eval mode: `live_json -> heuristic`
- agent tuning point: `agent_eval_top_n=4`
- explanation style: evidence-token centric template
- use `LLM-as-Judge` as a secondary lens; latest judged rerun reported `llm_as_judge_agreement = 0.4000`

## Risks Still Open

1. stream cache-miss ordering is still nondeterministic
2. production `sdk_handoff` path is not yet trusted for eval
3. `LLM-as-Judge` needs accumulation of more than one subset run
4. explanation presence is still lower than ideal

## Primary References

- [short_eval_status_2026-03-17.md](short_eval_status_2026-03-17.md)
- [llm_judge_design.md](llm_judge_design.md)
- [agent_baseline_comparison.md](../../src/eval/outputs/short_eval/manual/agent_baseline_comparison.md)

## Artifact Commit Policy

- commit:
  - docs under `docs/evaluation/`
  - `src/eval/llm_judge_annotations.jsonl`
  - reviewer-facing markdown summaries
- do not commit:
  - raw short-eval run directories under `src/eval/outputs/short_eval/manual/*/`
  - ad-hoc generated JSON summaries at the manual root
