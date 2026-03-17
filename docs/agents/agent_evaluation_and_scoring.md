# Agent Evaluation Logic and Scoring Rationale

**Purpose:** capture in one place **what each agent evaluates**, **how it reasons about scoring**, and **how the final ranking score is composed**.

**Related docs:** [multi_agent_pipeline.md](./multi_agent_pipeline.md), [ADR-004](../adr/ADR-004-agent-orchestration.md), [design/rationale-ontology-eval-cost.md](../design/rationale-ontology-eval-cost.md)

---

## 1. End-to-end flow summary

1. **Four dimension agents** evaluate each candidate and output a 0–1 score plus evidence/rationale.
   → Skill, Experience, Technical, Culture
2. **ScorePack** consolidates the four outputs and aligns explanations to an evidence-token style.
3. **Recruiter / Hiring Manager** each propose weights, and **WeightNegotiation** produces final weights.
4. Compute `agent_weighted_score` as a **weighted sum**, then blend it with the deterministic score using **(rank_deterministic_weight / rank_agent_weight)** to get the final `rank_score`.
5. If agents fail, a **heuristic fallback** fills the same schema with rule-based scores/explanations.

---

## 2. The four dimensions: what is evaluated and how scoring works

All four agents share a **`search_candidate_evidence`** tool (RAG-as-a-Tool). They call it **selectively** only when the given context is insufficient, searching for additional evidence within the candidate’s structured resume fields (`parsed.*`). For usage conditions, target fields, and implementation pointers, see [multi_agent_pipeline.md § Evidence Retrieval (RAG as a Tool)](./multi_agent_pipeline.md#evidence-retrieval-rag-as-a-tool).

### 2.1 Skill (SkillEvalAgent)

| Item | Details |
|------|------|
| **Input** | `required_skills`, `preferred_skills`, `candidate_skills` / `candidate_normalized_skills` / `candidate_core_skills` / `candidate_expanded_skills`, summary, raw_resume_text |
| **Output** | `score` (0–1), `matched_skills`, `missing_skills`, `evidence`, `rationale` |
| **View** | Alignment between JD required/preferred skills and candidate skills. Must consider **transferable / equivalent skills** (e.g., AWS SageMaker ↔ Vertex AI, React ↔ Vue/Angular). Do not over-penalize purely due to missing exact keywords. |
| **Rubric** | 0.8–1.0 Excellent (core skills or strong equivalents), 0.6–0.79 Good (transferable), 0.4–0.59 Fair, &lt;0.4 Poor. |
| **Heuristic** | `compute_skill_score(required_skills, candidate_normalized_skills)` = intersection ratio between required and candidate (denominator = required). Evidence is extracted from resume sentences containing required/matched tokens. |

*Implementation:* `contracts/skill_agent.py`, `runtime/heuristics.py`, `runtime/prompts.py` (skill_eval)

### 2.2 Experience (ExperienceEvalAgent)

| Item | Details |
|------|------|
| **Input** | `required_experience_years`, `preferred_seniority`, `candidate_experience_years`, `candidate_seniority_level`, experience_items, summary, raw_resume_text |
| **Output** | `score`, `experience_fit`, `seniority_fit`, `career_trajectory`, `evidence`, `rationale` |
| **View** | Prioritize **impact/scope/complexity of roles** over raw years. Value “high-impact seniority signals in a relevant domain” more than exact year/title matches. |
| **Rubric** | 0.8+ demonstrates high impact/seniority; 0.6+ solid competence. |
| **Heuristic** | `experience_fit`: candidate-years / required-years (slight penalty when significantly over). `seniority_fit`: 1.0 if matches preferred, else 0.4. `score = (experience_fit + seniority_fit) / 2`. |

*Implementation:* `contracts/experience_agent.py`, `runtime/heuristics.py`, `runtime/helpers.py` (compute_experience_fit, compute_seniority_fit), `runtime/prompts.py` (experience_eval)

### 2.3 Technical (TechnicalEvalAgent)

| Item | Details |
|------|------|
| **Input** | `required_stack`, `preferred_stack`, `candidate_skills`, `candidate_projects`, summary, raw_resume_text |
| **Output** | `score`, `stack_coverage`, `depth_signal`, `evidence`, `rationale` |
| **View** | Stack coverage + **architecture/engineering depth**. Accept **equivalent stacks** (AWS vs GCP vs Azure, PostgreSQL vs MySQL, etc.). Award 0.8+ if depth/maturity is demonstrated even if tool names differ slightly. |
| **Heuristic** | `stack_coverage` = overlap ratio between required_stack and candidate_skills. `depth_signal` = stack_coverage·0.8 + vector_score·0.2. `score = (stack_coverage + depth_signal) / 2`. Evidence cites sentences that include required_stack plus keywords like "architecture", "designed", "implemented". |

*Implementation:* `contracts/technical_agent.py`, `runtime/heuristics.py`, `runtime/prompts.py` (technical_eval)

### 2.4 Culture (CultureEvalAgent)

| Item | Details |
|------|------|
| **Input** | `target_signals`, `candidate_signals`, summary, raw_resume_text |
| **Output** | `score`, `alignment`, `risk_flags`, `evidence`, (optional) `potential_*`, `rationale` |
| **View** | **Culture/capability signals** such as collaboration, communication, and ownership. Default baseline is 0.7–0.8; go below 0.6 only when **explicit negative signals** exist (e.g., implausibly frequent job hopping, lack of any specialization track). |
| **Heuristic** | 0.75 if category_filter matches hit category, else 0.6. risk_flags is `["indirect-domain-signal"]` on mismatch. |

*Implementation:* `contracts/culture_agent.py`, `runtime/heuristics.py`, `runtime/prompts.py` (culture_eval)

### 2.5 Evidence role separation (EVIDENCE RULE, prompt v5+)

Each agent’s **evidence** has a distinct role to avoid duplication. Prompts enforce this so UI cards (Skill/Technical/etc.) do not repeat the same sentences.

| Agent | What to include in evidence | What to avoid |
|----------|----------------------|----------------------|
| **Skill** | **Alignment only**: which required/preferred skills match (or are equivalent) and what is missing/weaker. E.g., "JD required X; candidate has X (or equivalent Y)", "Missing: A, B" | Pure tech/tool listing (Technical’s role) |
| **Technical** | **Stack coverage/depth only**: what tools/platforms are used; evidence of breadth or depth (architecture/scale/ownership). Cite tech in context | Skill alignment/match/missing phrasing (Skill’s role) |
| **Experience** | **Experience/seniority only**: years, impact, scope, level. E.g., "N years in X roles; senior/lead scope" | Skill/tech listing (Skill/Technical roles) |
| **Culture** | **Soft signals only**: collaboration, communication, ownership, teamwork | Skills/tech/years (other agents’ scope) |

- **ScorePack**: keep the same separation when consolidating outputs; do not blur Skill=alignment vs Technical=coverage/depth vs Experience vs Culture.
- **ranking_explanation**: when technical fit is a key driver, cite Technical’s stack coverage/depth evidence as well.

*Implementation:* `runtime/prompts.py` (per-agent EVIDENCE RULE, score_pack, negotiation, live_orchestrator_system)

---

## 3. Weight negotiation (Recruiter vs Hiring Manager)

| Role | View (prompt summary) |
|------|------------------------|
| **Recruiter** | Pipeline/time-to-hire, value of transferable skills, reducing unnecessary false negatives. Do not ignore must-have gaps, but view fit more broadly than rigid keyword matching. |
| **Hiring Manager** | Execution quality, technical fit, risk reduction, must-have coverage, depth and seniority fit. Review/challenge/accept recruiter proposals using evidence. Explicitly **do not allow culture weighting to compensate for weak technical fit**. |
| **WeightNegotiation** | Adjust proposals using JD priorities and score evidence—**not** a simple average. Constrain culture weights so they cannot “wash out” weak technical fit. Guardrails: must_have_match_rate &lt; 0.5 → technical+experience ≥ 0.6; technical_score &lt; 0.6 → culture ≤ 0.2. |

**Output:** `recruiter`, `hiring_manager`, `final` (each is skill/experience/technical/culture and sums to 1.0), `rationale`, `ranking_explanation`.

**Fallback weights (heuristic):**

- Recruiter/Hiring Manager defaults are managed via **settings/env** (e.g., `FALLBACK_RECRUITER_WEIGHTS`, `FALLBACK_HIRING_MANAGER_WEIGHTS`).
- Small adjustment ranges (e.g., recruiter experience boost when required years ≥ threshold) are also managed via **settings**.
- **Final** = midpoint of the two normalized proposals.

*Implementation:* `contracts/weight_negotiation_agent.py`, `runtime/helpers.py` (build_fallback_weight_negotiation), `runtime/prompts.py` (recruiter_view, hiring_manager_view, negotiation)

---

## 4. Agent weighted score → final ranking score

### 4.1 Agent weighted score (`agent_weighted_score`)

After agents run, compute in one step using the four dimension scores and the **negotiated final weights**:

```text
agent_weighted_score = skill_score * w_skill + experience_score * w_exp + technical_score * w_tech + culture_score * w_culture
```

- `w_*` comes from `weight_negotiation.final` (sum = 1.0).
- `skill_score` etc. come from each agent output’s `score` (LLM or heuristic).

*Implementation:* `runtime/helpers.py` (`compute_weighted_score`), `runtime/service.py` (build RankingAgentInput then call `compute_weighted_score` → `RankingAgentOutput.final_score`).

### 4.2 Final ranking score (`rank_score`)

```text
rank_score_before_penalty = rank_deterministic_weight * deterministic_score + rank_agent_weight * agent_weighted_score
rank_score = rank_score_before_penalty * (1 - must_have_penalty)
```

- **deterministic_score**: a 0–1 score computed from semantic_similarity, skill_overlap, experience_fit, seniority_fit, category_fit, etc. Internal weights are managed by a **versioned deterministic scoring policy** (`src/backend/services/scoring_policies.py`). skill_overlap caps the denominator to top 10 JD skills; when agents run, skill_overlap is blended 50:50 with the agent skill score.
- If **agent_weighted_score** is missing (agents not applied), use `rank_score = deterministic_score`.
- **must_have_penalty**: up to 0.12 penalty applied when must-have requirements are not met.

In short, **when agents are present**, ranking is determined by the `RANK_DETERMINISTIC_WEIGHT` / `RANK_AGENT_WEIGHT` blend, then multiplied by a penalty when must-haves are not met.

*Implementation:* `services/scoring_service.py` (`compute_final_ranking_score`, `compute_deterministic_match_score`), `services/scoring_policies.py` (deterministic policy), `services/match_result_builder.py` (rank_score computation + `rank_policy` string).

---

## 5. Explanation generation rationale

- **Goal:** explain “why this score/rank” using an **evidence-token** style. Prefer **literal skill/evidence tokens** present in the JD/candidate over generic phrasing ("strong experience").
- **Template (prompt v5 / live_orchestrator):**
  - `Matched required skills: <literal tokens>.`
  - `Candidate evidence tokens: <literal tokens>; missing or weaker skills: <literal tokens or none>.`
  - `Scores/weights: skill=..., experience=..., technical=..., culture=...; final weights skill=..., ...`
  - When technical fit is a decision driver, cite Technical’s stack coverage/depth evidence.
- **Heuristic explanation:** `build_grounded_ranking_explanation` builds the same structure using job_profile required_skills, candidate skill_input/technical_input, per-agent matched/missing, and final_weights.

This aligns with eval groundedness heuristics (overlap between explanation sentences and skill/evidence tokens) and makes it easy for reviewers to trace “which tokens drove match vs gap”.

*Implementation:* `runtime/helpers.py` (`build_grounded_ranking_explanation`), `runtime/prompts.py` (negotiation, live_orchestrator_system), `match_result_builder.py` (deterministic path `_build_deterministic_explanation`).

---

## 6. Summary table

| Category | Details |
|------|------|
| **Dimensions** | Skill (required/preferred + transferable), Experience (impact/seniority), Technical (stack/depth), Culture (collaboration/risk). |
| **Scoring view** | Each dimension outputs 0–1; accept equivalents/transferables; avoid harsh exact-match penalties; lower Culture only on negative signals. |
| **Weights** | Recruiter (pipeline/transferable) vs Hiring Manager (technical/must-have) → negotiated final. Prevent culture weights from compensating for weak technical fit. |
| **Final score** | agent_weighted = weighted sum of 4 dimensions; rank_score = deterministic·`rank_deterministic_weight` + agent_weighted·`rank_agent_weight`, then apply must_have_penalty. |
| **Explanation** | Evidence-token template (Matched / Candidate evidence / Missing; Scores/weights). Cite Technical stack/depth when it drives ranking. |
| **Evidence roles** | Skill=alignment, Technical=coverage/depth, Experience=tenure/impact, Culture=collaboration/communication (v5 EVIDENCE RULE). |

**Code location summary**

- Contracts/schemas: `src/backend/agents/contracts/` (skill_agent, experience_agent, technical_agent, culture_agent, weight_negotiation_agent, ranking_agent).
- Prompts: `src/backend/agents/runtime/prompts.py`.
- Heuristics / weighted score / explanations: `src/backend/agents/runtime/helpers.py`, `heuristics.py`.
- Orchestration / ranking_output: `src/backend/agents/runtime/service.py`.
- deterministic policy: `src/backend/services/scoring_policies.py`
- Final rank_score: `src/backend/services/scoring_service.py`, `match_result_builder.py`.
