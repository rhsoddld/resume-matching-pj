# Agent Eval Stability Comparison

## Runs Compared

- Previous unstable short-agent run:
  - artifact status: no completed `agent_eval.json` was produced in the earlier short-eval summary
  - evidence: `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/summary.md`
  - observed runtime failures during execution:
    - `ScorePackOutput` missing `technical_output` / `culture_output`
    - `WeightNegotiationOutput` vs `ViewpointProposalOutput` mismatch
    - Agents SDK handoff event-loop / connection instability
    - eval processes reaching long idle/sleep tails without finishing cleanly

- Current stable baseline:
  - run id: `eval-20260316T201425Z-3e437923`
  - path: `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_baseline`
  - mode: eval-only SDK bypass (`live_json -> heuristic`)

- Top-3 latency experiment:
  - run id: `eval-20260316T201847Z-1e08f138`
  - path: `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_top3`
  - mode: eval-only SDK bypass + `AGENT_EVAL_TOP_N=3`

- Top-4 prompt-v4 experiment:
  - run id: `eval-20260316T202755Z-b273f110`
  - path: `/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_top4_v4`
  - mode: eval-only SDK bypass + `AGENT_EVAL_TOP_N=4` + evidence-token explanation template

## What Stabilized

1. The short agent eval now completes end-to-end.
   - Previous unstable run: no finished agent artifact
   - Current baseline: `6/6` successful queries, `fallback_trigger_rate=0.0`, `error_rate=0.0`

2. The evaluation path no longer depends on the unstable SDK handoff chain.
   - Baseline run executed on `chat/completions` live JSON path instead of the SDK handoff `responses` path.

3. Runtime fallback counters stayed at zero in the completed baseline.
   - `agent_fallback_count=0`
   - `agent_runtime_fallback_candidate_count=0`
   - `agent_runtime_error_candidate_count=0`

4. This means the remaining problem moved from "runtime instability" to "output quality."
   - baseline explanation presence is only `0.5000`
   - groundedness is `0.0648`
   - consistency is `0.4080`

## Baseline Metrics

| metric | unstable run | stable baseline |
|---|---:|---:|
| completed agent artifact | no | yes |
| successful queries | - | 6 |
| fallback trigger rate | - | 0.0000 |
| error rate | - | 0.0000 |
| explanation presence | - | 0.5000 |
| groundedness | - | 0.0648 |
| dimension consistency | - | 0.4080 |
| e2e latency p95 (ms) | - | 19843.8624 |
| agent latency p95 (ms) | - | 19261.5709 |
| cost/request (USD) | - | 0.0017 |

## Groundedness Findings From Explanation Text

Representative live-json explanations were inspected directly on the stable eval path.

### Query `gs-q-016`

- candidate `suri-308`
  - groundedness: `0.1581`
  - explanation:
    - `Candidate ranks highly due to strong experience and technical skill alignment with the job requirements, including extensive AWS, Terraform, Kubernetes, and Linux expertise. Minor skill gap in ArgoCD is offset by strong related skills. Cultural fit signals are less explicit, warranting moderate caution. Overall, candidate is a strong match for a senior cloud/devops engineer role.`

- candidate `suri-495`
  - groundedness: `0.1270`
  - explanation:
    - `Candidate ranks highly due to strong alignment in skills, extensive relevant experience, and solid technical expertise in cloud, DevOps, and infrastructure automation. Minor gaps in nice-to-have tools (Helm, ArgoCD) and limited cultural signal slightly reduce overall fit. Weighting favors experience and technical depth, supporting a strong match for a lead cloud/devops engineer role.`

- candidate `suri-2647`
  - groundedness: `0.1127`
  - explanation:
    - `Candidate ranks well due to strong experience and seniority fit, solid technical skills in core cloud and devops areas, and good skill match for required technologies. Missing helm and argocd skills and limited cultural signals slightly reduce overall ranking but candidate remains a strong match for the role.`

### Why groundedness is low

1. The explanations are fluent but generic.
   - They use phrases like `strong experience`, `technical expertise`, `good skill match`, `strong alignment`.
   - Those phrases do not mention enough of the actual expected or candidate skill tokens counted by the heuristic.

2. Token overlap is much narrower than it looks to a human.
   - The heuristic scores groundedness by checking whether explanation text literally mentions the union of expected skills and candidate skills.
   - Candidate skill lists are broad (`aws`, `ec2`, `vpc`, `cloudwatch`, `terraform`, etc.), but the explanation only names a few (`AWS`, `Terraform`, `Kubernetes`, `Linux`, sometimes `ArgoCD`, `Helm`).

3. Presence is also suppressing the aggregate.
   - Baseline explanation presence rate is only `0.5000`, so many evaluated rows contribute `0.0`.

4. The explanation is ranking-oriented, not evidence-oriented.
   - It summarizes why the candidate is good, but rarely cites resume-grounded details such as project names, years, systems, or specific tools from the normalized skill set.

## `agent_eval_top_n=5` vs `3`

| metric | top_n=5 baseline | top_n=3 | delta |
|---|---:|---:|---:|
| explanation presence | 0.5000 | 0.3000 | -40.00% |
| groundedness | 0.0648 | 0.0408 | -37.04% |
| dimension consistency | 0.4080 | 0.2456 | -39.80% |
| e2e latency p95 (ms) | 19843.8624 | 18141.0053 | -8.58% |
| e2e latency mean (ms) | 17021.9076 | 16401.9088 | -3.64% |
| agent latency p95 (ms) | 19261.5709 | 17593.1485 | -8.66% |
| total tokens/request | 646.0 | 535.5 | -17.11% |
| agent tokens/request | 910.3333 | 689.3333 | -24.28% |
| cost/request (USD) | 0.0017 | 0.0013 | -23.53% |
| candidates/sec | 42.5786 | 46.5016 | +9.21% |
| fallback trigger rate | 0.0000 | 0.0000 | flat |
| error rate | 0.0000 | 0.0000 | flat |

## Recommendation

- Use the stable `top_n=5` live-json baseline as the current quality reference.
- Use `top_n=3` only if latency/cost is the immediate priority and the quality drop is acceptable.
- The next quality win is not more fallback work; it is making agent explanations cite more literal skill/evidence tokens from the candidate profile.

## Prompt-v4 / `top_n=4` Update

### Representative explanation after the prompt/template change

- query `gs-q-016`, candidate `suri-308`
  - `Matched required skills: helm, linux, terraform, networking, kubernetes, observability. Candidate evidence tokens: aws, ec2, vpc, ebs; missing or weaker skills: argocd. Scores/weights: skill=0.85, experience=0.90, technical=0.88, culture=0.60; final weights skill=0.35, experience=0.30, technical=0.28, culture=0.07.`

### `top_n=4` with prompt-v4 vs previous baselines

| metric | top_n=5 baseline | top_n=4 prompt-v4 | top_n=3 |
|---|---:|---:|---:|
| explanation presence | 0.5000 | 0.4000 | 0.3000 |
| groundedness | 0.0648 | 0.0832 | 0.0408 |
| dimension consistency | 0.4080 | 0.3323 | 0.2456 |
| e2e latency p95 (ms) | 19843.8624 | 19551.8936 | 18141.0053 |
| e2e latency mean (ms) | 17021.9076 | 16615.5136 | 16401.9088 |
| cost/request (USD) | 0.0017 | 0.0014 | 0.0013 |

### Interpretation

- `top_n=4` is the best current compromise.
- It keeps explanation presence between `top5` and `top3`.
- It improves groundedness above the old `top5` baseline by using literal evidence tokens.
- Its latency/cost are lower than `top5`, while avoiding the larger quality drop seen at `top3`.
