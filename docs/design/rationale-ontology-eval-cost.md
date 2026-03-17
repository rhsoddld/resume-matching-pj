# Design rationale: ontology, cost, evaluation

**Purpose:** This document explains design decisions and operational direction by consolidating “why a skill ontology”, “long-term cost structure”, and “evaluation metrics and perspective” in one place.

**Related docs:** [Key Design Decisions](./key-design-decisions.md), [evaluation_plan.md](../evaluation/evaluation_plan.md), [cost_control.md](../governance/cost_control.md), [ADR-004](../adr/ADR-004-agent-orchestration.md). **Agent evaluation & scoring detail:** [agents/agent_evaluation_and_scoring.md](../agents/agent_evaluation_and_scoring.md).

---

## 1. Why an ontology? — Agentic AI fit

### 1.1 Definition

The **skill ontology** in this system consists of:

- **Core taxonomy** (`config/skill_taxonomy.yml`): skill → `domain`, `family`, `parents` hierarchy
- **Aliases** (`config/skill_aliases.yml`): synonym/variant → canonical skill mapping
- **Role candidates** (`config/skill_role_candidates.yml`): role candidate sets
- **Capability phrases** (`config/skill_capability_phrases.yml`): capability phrase mappings
- **Versioned skills** (`config/versioned_skills.yml`): versioned skill normalization
- **Review required** (`config/skill_review_required.yml`): skills flagged for review

At runtime, `RuntimeSkillOntology` loads this config and is used for **JD parsing, retrieval, scoring, and agent evaluation** so all stages share the same vocabulary and hierarchy.

### 1.2 Fit with Agentic AI

Reasons to use an ontology together with agent-based evaluation (Agentic AI):

| Aspect | Description |
|------|------|
| **Input/output consistency** | What agents evaluate is fixed by the ontology. JD-derived `required_skills`, `related_skills`, and `role` are canonical/alias-normalized, so agent prompts and tool inputs use the **same terminology**. |
| **Explicit scope of work** | Skill candidate extraction (`_extract_ontology_candidates`), role inference (`_infer_roles`), capability signals (`_extract_capability_signals`), and adjacent skills (`find_adjacent_skills`) are ontology-vocabulary driven. Agents only need to score and cite evidence for “already structured requirements”, making their work explicit. |
| **Transferable/adjacent skill** | For PO.3 (missing transferable/adjacent skill candidates), we do expanded matching **within the same ontology** via `find_adjacent_skills` (shared domain/family/parents) and `adjacent_match_score`. Agents can explain in consistent terms (e.g. “these skills share the same domain/family”). |
| **Tool alignment** | Tools like `search_candidate_evidence` use the same schema as retrieval results and JD profile. Because the profile is ontology-normalized, agent “evidence” and “required skills” align. |
| **Maintenance and extension** | Adding/merging skills happens via YAML, extending vocabulary and hierarchy without changing agent code. Agent behavior extends automatically to the “given ontology”. |

In short, **the ontology is agent-friendly because it unifies what agents understand, say, and evaluate** into one system.

### 1.3 Use in the pipeline

- **Query understanding** (`job_profile_extractor.py`): JD → ontology-based `required_skills`, `related_skills`, `role`, `core_skills`, `adjacent_skills` (including evidence)
- **Filter options** (`filter_options.py`): merge `skill_taxonomy.yml` domain/family with industries/job_families for API options
- **Match result** (`match_result_builder.py`): compute adjacent match score and match list between JD-related skills and candidate skills via `adjacent_match_score`
- **Ingestion** (`ingestion/transformers.py`): enrich resume skills with ontology hierarchy (e.g. parents)

---

## 2. Why long-term cost is favorable — cost effectiveness of agent workload

### 2.1 Design principle: deterministic-first, agents optional

 - The deterministic path is the default: JD parsing (ontology + rules), hybrid retrieval, and deterministic scoring run without LLM calls.
 - High-cost steps (agents, rerank) run only under **conditions and caps**.

This ensures “expensive work” runs only for the candidates/queries that truly need it, reducing long-run cost.

### 2.2 Cost maximization via agent workload

| Mechanism | Description |
|----------|------|
| **`agent_eval_top_n` cap** | Cap the number of candidates that receive agent evaluation. Remaining candidates use only deterministic scoring, limiting token spend to “top N”. |
| **Cache (LRU + TTL)** | Repeated requests for the same/similar JD are served from cache without retrieval/agents/rerank, greatly reducing repeat-query cost. |
| **Rerank off by default** | Rerank is disabled by default because its quality gains are not yet justified vs latency/cost; target baseline quality primarily via agents. |
| **Fallback chain** | SDK handoff → live_json → heuristic fallback produces results without extra token spend when upstream paths fail. |
| **Ontology provides “high-quality inputs”** | JD and candidates are ontology-normalized, so agents can focus tokens on requirement evaluation rather than re-deriving what to look at from long context. |

In short, we maximize cost-effectiveness by **capping agent workload and handling the rest via deterministic logic and caching**.

### 2.3 Summary

- **Why long-term cost is favorable:** we use high-cost LLM work (agents) only when needed and only for top N candidates; the rest is handled via ontology-driven deterministic logic and caching.
- Agent workload is not “LLM over every candidate”, but **“curated inputs + a limited number of candidates”**, which improves cost effectiveness.

See [cost_control.md](../governance/cost_control.md) for detailed control knobs.

---

## 3. Evaluation (Eval): why metrics are low, and from what perspective

### 3.1 Two meanings of "eval metrics are low"

- **(A) The measured metric values are low**  
  e.g. recall@10 below target, groundedness/agreement still low, etc.
- **(B) The number of data points/experiments is small**  
  e.g. short-eval uses small subsets (like 6 queries); full golden 50 exists but is not run continuously.

Below we separate these two meanings.

### 3.2 How we view eval (evaluation philosophy)

Eval is designed not as a single score, but as **stage-wise**, **reproducible**, and **reviewer-facing**.

| Principle | Description |
|------|------|
| **Retrieval-first truth** | Downstream rerank/agents cannot recover a candidate that was missed in retrieval. Therefore **retrieval quality (recall@10/20, MRR)** is the top quality gate. |
| **Stage attribution** | Measure quality/latency/cost by attributing to stages: **query understanding / retrieval / rerank / agents**. |
| **Measurable over anecdotal** | Claims must map to explicit KPIs (recall, MRR, NDCG@5, groundedness, agreement, etc.). |
| **Traceability** | Evaluation results must be reproducible via versioned inputs (golden set, ontology, code) and the exact run commands. |
| **Operational axes** | Evaluate not only quality but also fairness, reliability, cost, and latency as separate axes. |

Therefore, “eval” is not a single score; it splits **retrieval → rerank → agents** to see stage contribution and cost/benefit.

### 3.3 Why (some) eval metrics are low

- **Retrieval**  
  - In short-eval: recall@10 ≈ 0.525, recall@20 ≈ 0.71.
  - Close to targets (e.g. recall@10 ≥ 0.50) but still has room to improve.
  - If golden set and ontology are misaligned, comparisons are paused due to unmapped skills (see `golden_set_alignment.md`).

- **Rerank**  
  - Deltas like NDCG@5 and MRR show **unclear quality gains vs added latency**, so rerank is excluded from the default path and kept as optional/gated.
  - So rerank numbers exist, but do not justify always-on adoption.

- **Agent (explanation quality)**
  - **Why groundedness was low** (from short_eval_status):
    - explanations were too generic (“strong experience”, “technical expertise”)
    - groundedness heuristics require **skill/evidence token overlap**, but older explanations mentioned only a few tools and omitted concrete evidence tokens (e.g. ec2, vpc, cloudwatch)
    - explanation presence was partial (only agent-evaluated rows had explanations), reducing aggregate scores
  - **Mitigation:** prompt v4 uses evidence-token-centric templates (matched required skills, candidate evidence tokens, missing/weaker skills) and exposes ontology-aligned evidence.
  - **LLM-as-Judge** is newly integrated and still subset/early-stage, so it is not yet a production KPI.

- **Short-eval sample size**
  - For quick validation we run small subsets (e.g. **6 queries**), so “low” can also mean “few data points/experiments”.
  - Continuous full runs on golden 50 and per-job-family slice analysis are tracked as backlog.

### 3.4 Eval perspective summary

| Question | Answer |
|------|------|
| **What perspective do we use for eval?** | Stage-wise (retrieval → rerank → agents), reproducible golden-based, producing reviewer-trustworthy evidence across quality/performance/cost/reliability/fairness. |
| **Why do some numbers look low?** | (1) Agent explanation groundedness was low due to generic explanations and lack of evidence; improving via prompt v4 and evidence-token alignment. (2) Rerank is off by default because metrics do not justify always-on use. (3) Short-eval uses small samples for fast validation. |
| **What do we prioritize?** | Retrieval recall first, then incremental gains vs cost for rerank/agents. |

For detailed metrics, artifacts, and checklists, see [evaluation_plan.md](../evaluation/evaluation_plan.md), [short_eval_status_2026-03-17.md](../evaluation/short_eval_status_2026-03-17.md), and [llm_judge_design.md](../evaluation/llm_judge_design.md).

---

## 4. Why we chose this eval stack (DeepEval, Confident AI, sdk_handoff bypass)

**Purpose:** This section is not defensive; it documents the **reasoning** behind choices such as “Do we use DeepEval?”, “Why not Confident AI?”, and “Why disable sdk_handoff in eval?”.

### 4.1 DeepEval

| Fact | Description |
|------|------|
| **Docs/requirements** | `deepeval` is listed in `requirements.txt`, and docs (Key Design Decisions, system architecture) describe “DeepEval-based evaluation”. |
| **Implementation** | **The code does not import or call the deepeval library.** Metrics like recall@k, MRR, NDCG, groundedness heuristics, and LLM-as-Judge integration are implemented in `src/eval/metrics.py` and `eval_runner.py`. |
| **Summary** | The evaluation **approach** (golden set, stage-wise metrics, LLM-as-Judge) aligns with DeepEval, but there is **no runtime dependency** today. Adopting DeepEval APIs later is optional. |

### 4.2 Confident AI

| Fact | Description |
|------|------|
| **Environment variables** | `.env.example` includes `CONFIDENT_API_KEY` and `CONFIDENT_REGION`. |
| **Implementation** | **There is no backend code calling the Confident AI API.** Guardrails run via in-repo implementation (`fairness.py`, `jd_guardrails.py`, etc.). |
| **Why not used** | Confident AI is currently **not integrated**. It may have been unavailable (service outage/access restrictions) or deprioritized in favor of in-repo guardrails. We do not claim “unusable”; we document it as “not integrated/not used”. |

### 4.3 Why eval does not use sdk_handoff (not defensive)

| Fact | Description |
|------|------|
| **Issue** | The **Agents SDK handoff path was unstable**. Observed in short_eval: schema mismatches in `ScorePackOutput` / negotiation, handoff event-loop/connection instability, long idle tails causing eval runs not to complete. |
| **Result** | To evaluate agent **quality**, eval runs must finish reliably. With SDK handoff enabled, runs failed or timed out and metrics could not be collected. |
| **Mitigation** | In eval mode we **do not use sdk_handoff**, and instead use only the `live_json → heuristic` paths. This is not “agentic AI is unstable”; it is that a **specific runtime path (SDK handoff)** was unstable, so eval bypasses it until proven stable. |
| **Docs** | [short_eval_status_2026-03-17.md](../evaluation/short_eval_status_2026-03-17.md), [RESULTS.md](../eval/RESULTS.md): “eval-only SDK bypass until Agents SDK handoff is proven stable”, “do not re-enable sdk_handoff in eval.” |

Summary: we document **Confident AI as not integrated/not used** (without claiming it is unusable), and document **sdk_handoff bypass** as a choice made for eval stability due to SDK handoff instability (schema/event loop).

---

## 5. Summary table

| Topic | One-line summary |
|------|------------|
| **Why ontology?** | It makes agents use a single consistent system for “what to evaluate” and “what terms to use”, improving agentic-AI fit and enabling transferable skills, tools, and maintainability. |
| **Long-term cost** | Deterministic-first + `agent_eval_top_n` + caching keeps high-cost LLM work focused only where needed, maximizing cost-effectiveness of agent workload. |
| **Eval metrics and perspective** | Eval is stage-wise, reproducible, and reviewer-facing; lower numbers can come from explanation quality (groundedness), unclear rerank ROI, and small short-eval samples; prioritize retrieval-first. |
| **DeepEval** | Listed in docs/requirements but not called in code; metrics are implemented in-repo. |
| **Confident AI** | Env vars exist but not integrated; guardrails are implemented in-repo. |
| **sdk_handoff bypass** | SDK handoff path instability (schema/event loop) prevented eval completion, so eval uses live_json → heuristic only. |
