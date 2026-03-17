# Eval batching, LLM-as-Judge, and continuous eval

## 1. Eval batching (batch evaluation)

### Entry points

| Purpose | Command / script | Notes |
|------|-----------------|------|
| Full pipeline eval | `scripts/run_eval.sh` or `python3 -m eval.eval_runner --golden-set ...` | local/manual batch |
| Generate LLM judge annotations | `python3 -m eval.generate_llm_judge_annotations ...` | prepare judge inputs first |

### Environment variables (`run_eval.sh`)

- `GOLDEN_SET`: golden set path (default `src/eval/golden_set.jsonl`)
- `EVAL_MODE`: `full` | `hybrid` | `rerank` | `agent`
- `RUN_LABEL`: run label (default `manual`)
- `OUTPUTS_DIR`: outputs directory (default `src/eval/outputs`)

### Eval modes (`config.py`)

- **full**: query understanding + retrieval + rerank + agents + performance, plus human/LLM judge agreement
- **hybrid**: retrieval + query understanding only (rerank/agents off)
- **rerank**: retrieval + rerank metrics (agents off)
- **agent**: agent evaluation + performance focused

### Batch flow (`eval_runner`)

1. Load golden set JSONL
2. Load human/LLM judge references (optional)
3. Decide whether rerank runs (gate)
4. **Sequential per query**: for each row
   - query understanding → retrieval → (rerank) → agents → collect metrics
5. Aggregate metrics and write JSON/MD reports

- During agent eval, candidates run concurrently via `run_candidate_tasks_with_isolation` (ThreadPool, `max_workers=10`) (`matching/evaluation.py`, `matching_service.py`).

### Output artifacts

- `retrieval_eval.json`, `rerank_eval.json`, `agent_eval.json`, `performance_eval.json`
- `final_eval_report.md`, `rerank_gate_state.json`

---

## 2. LLM-as-Judge

### What it measures

- **Top-1 relevance**: `top1_is_relevant` (boolean)
- **Explanation quality**: `explanation_quality` (overall_score, groundedness_score, coverage_score, specificity_score, pass, rationale)

Use as **auxiliary signals**, not a replacement for golden truth (per `RESULTS.md` policy).

### Design doc

- [docs/evaluation/llm_judge_design.md](llm_judge_design.md)

### Generation loop (`generate_llm_judge_annotations.py`)

1. Load `golden.agent.jsonl` (or a specified subset)
2. For each query, run the current agent path → collect Top-1 candidate snapshot
3. **Live judge**: send job/candidate/explanation to the judge model and collect JSON output
4. If live fails, fall back to **bootstrap heuristics** (token overlap, groundedness/consistency heuristics)
5. Write one JSONL line per `query_id` + `candidate_id` + `stage` (agent_top1)

### Judge modes

- `--judge-mode llm`: live LLM calls (default)
- In bootstrap mode, set `judge_source = bootstrap_heuristic`; explanation quality is computed heuristically

### Eval integration

- Load JSONL via `llm_judge_path`, then:
  - `llm_as_judge_agreement`: agreement rate between predicted top1 vs judge `top1_is_relevant`
  - `llm_explanation_quality_score` / `llm_explanation_groundedness_score`: per-candidate score aggregates

---

## 3. Continuous eval

### Current implementation

| Type | Trigger | Workflow | Notes |
|------|--------|----------|------|
| **Retrieval benchmark** | weekly Monday 01:00 UTC, or main push (path-filtered) | `.github/workflows/retrieval-benchmark-archive.yml` | runs `scripts/generate_retrieval_benchmark_archive.py`, commits results to `docs/eval/` |
| **Eval archive** | main push (when eval paths change) or manual | `.github/workflows/eval-archive.yml` | runs `scripts/generate_eval_results.py` → updates `docs/eval/eval-results.md` |

- There is no scheduled workflow that runs the full `eval_runner` periodically (only recommendations exist).

### Recommendation (`final_eval_report.md` / `eval_runner`)

- “Run eval_runner on a schedule and enforce calibrated thresholds for **Recall@20**, **NDCG@5**, and **degraded-mode success rate**.”
- In other words: use scheduled batches + calibrated thresholds to prevent regressions.

### Notes for extending continuous eval

1. **Schedule**: run `scripts/run_eval.sh` (or `eval.eval_runner`) on a schedule via GitHub Actions cron or an external scheduler
2. **Thresholds**: read metrics such as Recall@20, NDCG@5, degraded-mode success rate from JSON and fail builds/alert
3. **Judge**: due to cost/latency, regenerate judge annotations periodically (`generate_llm_judge_annotations`) and have eval_runner reference them, rather than running judge every schedule
4. **Artifacts**: store run-time snapshots (commit/version/config) for reproducibility (current `run_id` and output path structure can be reused)

---

## 4. Quick reference

| Item | Location |
|------|------|
| Run eval | `scripts/run_eval.sh`, `src/eval/eval_runner.py` |
| Eval config/modes | `src/eval/config.py` |
| Metrics definitions | `src/eval/metrics.py` |
| Generate LLM judge | `src/eval/generate_llm_judge_annotations.py` |
| Judge design | `docs/evaluation/llm_judge_design.md` |
| Evaluation plan | `docs/evaluation/evaluation_plan.md` |
| Current conclusions/rules | `src/eval/RESULTS.md`, `src/eval/README.md` |
| CI schedules/archives | `.github/workflows/retrieval-benchmark-archive.yml`, `.github/workflows/eval-archive.yml` |
