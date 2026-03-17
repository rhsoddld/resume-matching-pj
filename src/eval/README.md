# Eval README

This directory intentionally contains only the minimal files needed for golden-set management, short evaluation loops, judge annotations, and report generation.

## Start Here

- Entry point: [eval_runner.py](eval_runner.py)
- Current conclusion summary: [RESULTS.md](RESULTS.md)
- Create subsets: [create_mode_subsets.py](create_mode_subsets.py)
- Generate LLM judge annotations: [generate_llm_judge_annotations.py](generate_llm_judge_annotations.py)

## Core Files

- [config.py](config.py)
  - Per-eval-mode configuration
- [metrics.py](metrics.py)
  - Retrieval/rerank/agent evaluation functions
- [reporting.py](reporting.py)
  - Markdown/JSON report generation
- [golden_set.jsonl](golden_set.jsonl)
  - Original golden set
- [golden_set.normalized.jsonl](golden_set.normalized.jsonl)
  - Normalized version
- [llm_judge_annotations.jsonl](llm_judge_annotations.jsonl)
  - Current judge annotation outputs

## Subsets

- Subset details: [subsets/README.md](subsets/README.md)
- active agent subset: [golden.agent.jsonl](subsets/golden.agent.jsonl)
- active hybrid subset: [golden.hybrid.jsonl](subsets/golden.hybrid.jsonl)
- active rerank subset: [golden.rerank.jsonl](subsets/golden.rerank.jsonl)

## Outputs

- kept reviewer summary root: `src/eval/outputs/short_eval/manual/`
- current judged agent run:
  - [final_eval_report.md](outputs/short_eval/manual/agent6_livejson_top4_v4_judged/final_eval_report.md)
  - [agent_eval.json](outputs/short_eval/manual/agent6_livejson_top4_v4_judged/agent_eval.json)

## Current Rule Of Thumb

- retrieval: keep hybrid enabled
- rerank: disabled by default
- agent eval: do not use `sdk_handoff` in eval runs
- current tuning point: `agent_eval_top_n=4`
- judge: an auxiliary signal, not a replacement for golden truth
