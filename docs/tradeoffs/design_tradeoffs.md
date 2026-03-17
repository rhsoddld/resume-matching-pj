# Design Tradeoffs

This document consolidates the key decisions from legacy `DESIGN_DECISION_MATRIX.md`, `KNOWN_TRADEOFFS.md`, and `scoring_design.md`.

## Decision Matrix (Restored)

| Decision | Chosen | Alternatives | Why Chosen | Tradeoff | Mitigation |
|---|---|---|---|---|---|
| Ingestion parsing | Rule-based deterministic | Generative parsing | cost / reproducibility / operational stability | field omissions possible for unstructured resumes | keep raw text + fallback at matching time |
| Data store | MongoDB + Milvus dual store | Single store | flexible document model + strong vector search | higher sync complexity | hash-based incremental upsert |
| Retrieval strategy | Hybrid (vector + lexical + metadata) | semantic-only, keyword-only | recall/precision balance | requires parameter tuning | automate fusion-weight experiments |
| Ranking baseline | Deterministic-first + optional agent blend | agent-only scoring | strong regressability + explainability | may lose semantic nuance | selectively blend agent score |
| Rerank policy | Gated optional rerank | always-on rerank | uncertain ROI vs cost/latency | added complexity | gate + timeout + fallback |
| Embedding model | `text-embedding-3-small` | larger embedding | cost-efficient + fast (re)indexing | may lose edge-case semantics | upgrade via env configuration |
| Agent runtime | `sdk_handoff -> live_json -> heuristic` | single-path runtime | resilience and service continuity | must understand mode-specific behavior | expose mode/fallback metadata |
| Agent latency/UX | parallel candidate eval + SSE streaming + agent_eval_top_n | synchronous single response only | mitigates long runtimes from multi-agent communication; improves perceived wait/progress | streaming sequencing/error handling complexity | sequential thought_process/candidate events + ThreadPoolExecutor parallelism |

## Agent tradeoffs: latency vs quality/UX

### Problem: long runtimes from OpenAI SDK multi-agent handoffs

| Item | Description |
|------|------|
| **Cause** | In the OpenAI Agents SDK path, multiple agents run sequentially via handoffs per candidate: Skill → Experience → Technical → Culture (LLM calls) → ScorePack → Recruiter → HiringManager → WeightNegotiation. This leads to many inter-agent communications and high end-to-end latency. |
| **Impact** | Users wait longer for results; with only a synchronous API, UX can degrade to an extended blank/loading screen. |

### Mitigations

| Mitigation | Description | Implementation |
|------|------|-----------|
| **Per-candidate parallelism** | Evaluate Top-K shortlist candidates concurrently. Within each candidate, agents are sequential, but candidates run in parallel via ThreadPoolExecutor to reduce total wall-clock time. | `matching_service.stream_match_jobs` → `ThreadPoolExecutor(...)`, `matching/evaluation.py` |
| **Streaming (SSE)** | Instead of waiting for a single response, stream results via Server-Sent Events in order: query profile → session_id → thought_process → candidate (as each completes) → fairness → done. This improves perceived progress and UX. | `POST /api/jobs/match/stream`, `stream_match_jobs`, `on_event` → `thought_process` / `candidate`, frontend `streamMatchCandidates`, `App.tsx` |
| **`agent_eval_top_n` cap** | Cap the number of candidates that receive full agent evaluation. Only top N run the full agent path; the rest use deterministic scoring to control latency/cost. | `agent_eval_top_n` setting, `select_agent_eval_indices` |
| **live_json / heuristic fallback** | If SDK path fails or is disabled, switch to `live_json` (single structured call) or `heuristic` (rule-based). This reduces/eliminates multi-agent communication and improves latency/resilience. | `AgentOrchestrationService._execute`, `live_runner`, `heuristics` |

### Summary

- **Tradeoff**: SDK-based multi-agent design → many inter-agent communications → **long runtimes**.
- **Mitigation**: **parallelism** (across candidates) + **streaming** (profile / thought_process / candidate) improves perceived wait time and UX; **agent_eval_top_n** and **live_json/heuristic** fallback control latency/cost/failures.

*Implementation details: [multi_agent_pipeline.md](../agents/multi_agent_pipeline.md), [candidate_retrieval_flow.md](../data-flow/candidate_retrieval_flow.md), [system_architecture.md](../architecture/system_architecture.md) § Multi-Agent Evaluation.*

## Scoring Tradeoffs (Legacy Scoring Design)

### Retrieval fusion
```text
fusion_score =
  0.48 * vector_score
+ 0.37 * keyword_score
+ 0.15 * metadata_score
```

### Skill overlap (skill_overlap)
 - Cap the denominator to the **top 10** JD-side skills.
- when core exists: `0.45×core_overlap + 0.35×expanded_overlap + 0.2×normalized_overlap`
- when core is missing: `0.5×normalized_overlap + 0.5×expanded_overlap`
- When agents run: blend the above value 50:50 with the agent skill score and use it as skill_overlap.

### Deterministic score
```text
deterministic_score =
  0.42 * semantic_similarity
+ 0.33 * skill_overlap
+ 0.18 * experience_fit
+ 0.07 * seniority_fit
+ category_fit_bonus
```

### Final hybrid score
```text
rank_score_before_penalty =
  0.30 * deterministic_score
+ 0.70 * agent_weighted_score

final_score = rank_score_before_penalty * (1 - must_have_penalty)
```

Notes:
- Use `compute_final_ranking_score` defaults as the source-of-truth weights.
- The response `rank_policy` string may be a legacy label; operational decisions should follow the actual computation.

## Known Risk Notes

1. In some experiments, rerank delivered limited quality gains relative to added latency.
2. Fair ranking can over-weight culture scores; keep guardrail caps.
3. Taxonomy expansion improves explainability but increases maintenance cost.
4. Multi-mode fallback improves resilience but increases operational observability surface area.

## Backlog

1. Auto-tune fusion weights per job family
2. Must-have penalty sensitivity experiments
3. Operationalize rerank ROI (A/B + rollback) documentation
4. Automate fairness drift detection
