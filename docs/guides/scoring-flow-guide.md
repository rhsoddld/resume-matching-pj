# End-to-end scoring flow guide

**Purpose:** Explain **step by step** "how many candidates are filtered and how scores are computed" from start to finish.  
Scoring is the most complex part of this system, so **head counts** and **formulas** are spelled out clearly.

---

## 1. Pipeline at a glance

Assume the user asks for **"top 10 (top_k=10) recommendations"**.

```
[Full DB] → Retrieval(N) → Enrichment(meta filters) → Shortlist(up to top_k) → Score computation → Final ordering
                ↑                    ↑                        ↑
           e.g. 10–50             drop if conditions         top 10 of those
                                 not met              → top 5 get agent eval
                                                      → remaining 5 rule-based score only
```

| Stage | Module | Head count (e.g. top_k=10) | What it does |
|------|-----------|------------------------|---------|
| 1. Retrieval | `HybridRetriever` | **N** (default 10; more if rerank on) | Retrieve candidates via vector + keyword + metadata |
| 2. Enrichment | `candidate_enricher` | **N → M** (M ≤ N) | Join Mongo docs + apply experience/education/region/industry filters → drop if conditions not met |
| 3. Shortlist | `_shortlist_candidates` | **Up to top_k (10)** | If rerank gate passes: Cross-Encoder rerank then top 10; else top 10 by fusion order |
| 4. Score computation | `_score_candidates` + `build_match_candidate` | **All 10** | Compute **deterministic score** for all 10 → only **top 5 (agent_eval_top_n)** get agent eval → produce **final rank_score** |
| 5. Order & response | `MatchingService` | **10** | Agent-evaluated first, then by `score` descending → return `JobMatchResponse` |

---

## 2. Step-by-step details: how many remain, what we compute

### 2.1 Retrieval — “how many do we fetch?”

- **Target count:** `retrieval_top_n`
  - rerank disabled: `retrieval_top_n = top_k` (e.g. 10)
  - rerank enabled: `retrieval_top_n = max(top_k, rerank_pool_n)`  
    - `rerank_pool_n = max(top_k, min(rerank_top_n, rerank_gate_max_top_n))`  
    - defaults: `rerank_top_n=50`, `rerank_gate_max_top_n=8` → for top_k=10, fetch **10**
- **What happens:**
  1. **Mongo keyword search** (always): search with lexical query extracted from the JD → `keyword_hits`
  2. **Milvus vector search** (when available): embed the JD and search by similarity → `vector_hits`
  3. **Merge:** de-duplicate by candidate and compute a single **fusion** score
- **Fusion formula (retrieval stage):**
  ```
  fusion_score = (vector_weight × vector_score) + (keyword_weight × keyword_score) + (metadata_weight × metadata_score)
  ```
  - default weights: **vector 0.48, keyword 0.37, metadata 0.15**
  - `vector_score`: normalize Milvus similarity \([-1, 1]\) into \([0, 1]\)
  - `keyword_score`: overlap ratio between JD required skills/terms and candidate skills
  - `metadata_score`: match signals for category/industry/experience years/seniority
- **Output:** **N hits** sorted by `fusion_score` (each hit keeps raw `score` plus `fusion_score`)

---

### 2.2 Enrichment — “who gets filtered out by metadata?”

- **Input:** **N** hits from retrieval
- **What happens:**
  - fetch full candidate documents from Mongo for each hit
  - **drop** the candidate if any metadata condition fails (not included in the enriched list)
    - `min_experience_years`: drop if candidate experience years is below the minimum
    - `education`: drop if education requirement does not match
    - `region`: drop if region/remote requirement does not match
    - `industry`: drop if industry requirement does not match
- **Output:** **M** pairs of **(hit, candidate_doc)** (M ≤ N). Downstream uses only these M.

---

### 2.3 Shortlist — “how many become scoring candidates?”

- **Goal:** keep **up to top_k** (e.g. 10) as scoring/agent-eval candidates.
- **What happens:**
  1. **Rerank gate** (`should_apply_rerank`):
     - rerank disabled or gate fails → sort `enriched_hits` by **fusion_score** and take first **top_k**
     - gate passes → rerank only the pool `resolve_rerank_pool_n(top_k)` (e.g. 10) via Cross-Encoder rerank, then blend **0.75×rerank + 0.25×fusion**, and take top **top_k**
  2. **Result:** always **up to top_k**. These are `shortlisted_hits` passed to scoring.

---

### 2.4 Score computation — “score all 10 + agents for top 5”

This is the **most complex** part. Two scores are produced in order.

#### Step A: all 10 — deterministic score (rule-based)

First, compute the deterministic match score for **all shortlisted candidates (10)**.

- **Inputs (hit + candidate_doc):**
  - `hit["score"]`: **raw vector similarity** from retrieval (semantic input to deterministic scoring)
  - `hit` fields such as `experience_years`, `seniority_level`, `category`, etc.
  - `candidate_doc["parsed"]`: skills, experience, etc.
  - `job_profile`: required_skills, expanded_skills, required_experience_years, preferred_seniority, etc.

- **1) Skill overlap (`skill_overlap`)** — `scoring_service.compute_skill_overlap`
  - Compare candidate core/expanded/normalized skills against JD required/expanded skills via **soft overlap**
  - **Denominator cap:** use at most **top 10** JD skills to avoid runaway penalties for very long skill lists
  - when core exists: `0.45×core_overlap + 0.35×expanded_overlap + 0.2×normalized_overlap`
  - when core is missing: `0.5×normalized_overlap + 0.5×expanded_overlap`
  - **When agents run:** blend 50:50 with the agent skill score to reflect richer, match-time evidence

- **2) Deterministic match score** — `scoring_service.compute_deterministic_match_score`
  ```
  semantic_similarity = (raw_similarity + 1) / 2   # normalize vector score to [0,1]
  experience_fit      = experience-years fit vs requirement (slight penalty if overqualified)
  seniority_fit       = 0..1 based on seniority level distance
  category_fit        = category bonus if matched, else 0

  final_score = w_sem×semantic_similarity + w_skill×skill_overlap + w_exp×experience_fit + w_seniority×seniority_fit + category_fit
  ```
  - \(w_\*\) and `category_bonus` are managed as a **versioned deterministic scoring policy** in `src/backend/services/scoring_policies.py` (default v1).
  - Clip the result into \([0, 1]\) to get **deterministic_score**.

Sort the 10 candidates by **deterministic_score**, and send only the **top agent_eval_top_n (default 5)** to the next stage (agents).

#### Step B: top 5 — agent evaluation + agent-weighted score

- **Scope:** only the **top 5 by score** from Step A (`select_agent_eval_indices`).
- **Per candidate:**
  1. Run **four agents**: Skill / Experience / Technical / Culture → each outputs a 0..1 score + evidence
  2. Recruiter vs Hiring Manager propose weights → finalize via **WeightNegotiation** (skill+experience+technical+culture sum to 1.0)
  3. Compute **agent-weighted score** via `compute_weighted_score`:
     ```
     agent_weighted_score = skill×w_skill + experience×w_exp + technical×w_tech + culture×w_culture
     ```

#### Step C: all 10 — final rank_score (display score)

Compute the final display score for **all 10** inside `build_match_candidate`.

- **Candidates with agent eval (5):**
  ```
  rank_score = rank_deterministic_weight × deterministic_score + rank_agent_weight × agent_weighted_score
  rank_score = rank_score × (1 - must_have_penalty)   # clip to 0..1
  ```
  - `must_have_penalty`: up to 0.12 penalty when must-have JD skills are missing (can be partially offset via adjacent skills).

- **Candidates without agent eval (5):**
  ```
  rank_score = deterministic_score
  rank_score = rank_score × (1 - must_have_penalty)
  ```

So, even with the same deterministic base, the top-5 with agent eval get a finer score via **30% deterministic + 70% agent**, while the remaining 5 keep **deterministic-only** scoring.

---

### 2.5 Ordering and response

- **Ordering key:**  
  1) candidates with agent eval first, 2) then by descending `score` (rank_score).
- Apply **fairness guardrails**, then return `JobMatchResponse` (the `matches` list is the “10 recommended candidates” with score + explanation).

---

## 3. Formulas (summary)

| Stage | Formula summary |
|------|-----------|
| **Skill overlap (display / deterministic input)** | Use only top-10 JD skills as denominator. With core: `0.45×core + 0.35×expanded + 0.2×normalized` / without core: `0.5×normalized + 0.5×expanded`. If agents run, blend 50:50 with agent skill score. |
| **Retrieval fusion** | `fusion = 0.48×vector + 0.37×keyword + 0.15×metadata` |
| **Deterministic score** | `w_sem×semantic + w_skill×skill_overlap + w_exp×experience_fit + w_seniority×seniority_fit + category_bonus(if matched)` (policy v1: `scoring_policies.py`) |
| **Agent weighted score** | `skill×w_s + experience×w_e + technical×w_t + culture×w_c` (weights sum to 1, negotiated) |
| **Final rank_score (agents on)** | `(rank_deterministic_weight×deterministic + rank_agent_weight×agent) × (1 - must_have_penalty)` |
| **Final rank_score (agents off)** | `deterministic × (1 - must_have_penalty)` |

---

## 4. Tunable numbers (summary)

| Setting | Default | Meaning |
|------|--------|------|
| `top_k` | (request param, e.g. 10) | final return count + shortlist size |
| `retrieval_top_n` | top_k (or larger with rerank) | max candidates fetched in stage 1 |
| `agent_eval_top_n` | 5 | top candidates evaluated by agents (others deterministic-only) |
| `rerank_top_n` / `rerank_gate_max_top_n` | 50 / 8 | rerank pool size cap |
| `token_budget_enabled` | False | when True, agent_eval_top_n may be reduced to fit token budget |
| `rank_deterministic_weight` / `rank_agent_weight` | 0.30 / 0.70 | blending ratio for deterministic vs agent_weighted in final rank_score (env/Settings) |
| `fallback_recruiter_weights` / `fallback_hiring_manager_weights` | (doc defaults) | fallback negotiation weights and adjustment range when LLM negotiation fails (env/Settings) |
| `deterministic scoring policy` | v1 | deterministic internal weights/bonuses are a **repo-managed policy version** (`scoring_policies.py`), not an env knob |

---

## 5. Related code locations

| Topic | File |
|------|------|
| Pipeline orchestration (retrieval → enrich → shortlist → score) | `src/backend/services/matching_service.py` |
| Retrieval fusion and counts | `src/backend/services/hybrid_retriever.py`, `src/backend/services/matching/rerank_policy.py` |
| Enrichment / metadata filters | `src/backend/services/candidate_enricher.py` |
| Shortlist / rerank gate | `src/backend/services/matching_service.py` (`_shortlist_candidates`), `src/backend/services/matching/rerank_policy.py` |
| Deterministic scoring, skill overlap, final blend | `src/backend/services/scoring_service.py`, `src/backend/services/scoring_policies.py`, `src/backend/services/match_result_builder.py` |
| Four agents + weight negotiation + agent_weighted_score | `src/backend/agents/runtime/service.py`, `src/backend/agents/runtime/helpers.py` |
| Selecting agent-eval indices | `src/backend/services/matching/evaluation.py` (`select_agent_eval_indices`) |

Following this document lets you trace **“how many candidates are filtered, what computations produce scores, and how the final top-10 is returned”** end to end.
