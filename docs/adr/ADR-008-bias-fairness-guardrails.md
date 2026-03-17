# ADR-008 Bias & Fairness Guardrails (v1)

## Decision
Implement backend v1 bias and fairness guardrails: sensitive-term scan on JD/description text, culture weight cap, must-have vs culture gate, and top-K seniority distribution check. Expose warnings via `fairness.warnings` and frontend banner.

## Why
- Governance and audit: document what is being limited and how, for recruiter and compliance review
- Reduce risk of over-relying on culture score or must-have gaps masked by high culture fit
- Sensitive-attribute keyword detection surfaces potential bias in job or candidate text for human review

## Consequences
- Guardrails are heuristic (keyword list, thresholds); tuning and fairness metrics dashboard are follow-up work
- Frontend must handle and display warnings without blocking workflow; backend returns structured warnings only

---

## How it works

**When it runs:** right after shortlist scoring completes in the matching pipeline, `MatchingService._run_fairness_guardrails()` is invoked once. (Both sync and streaming APIs include `fairness` in the final output.)

**Configuration:** if `settings.fairness_guardrails_enabled=False`, the system skips checks and returns only a FairnessAudit with `enabled=False`. Each check can also be toggled (e.g., `fairness_sensitive_term_enabled`).

### 1. Sensitive term scan

| Target | Behavior |
|------|------|
| **JD (`job_description`)** | Regex match via `extract_sensitive_terms(job_description)`. On hit, emit one global warning: `sensitive_term_in_query` (severity: critical). |
| **Candidate** | Apply the same regex to `summary + agent_explanation` text per candidate. On hit, emit candidate warning: `sensitive_term_in_candidate_explanation` (severity: warning) and append a message to `bias_warnings`. |

Sensitive terms include `young`, `old`, `male`, `female`, `man`, `woman`, `pregnant`, `maternity`, `married`, `single`, religion/race terms, `disability`, etc. (see `_SENSITIVE_TERMS` in `fairness.py`). Uses word boundaries (`\b`) and is case-insensitive.

### 2. Culture weight cap

- Read `agent_scores.weights.culture`.
- If `culture_weight > fairness_max_culture_weight` (default 0.2), emit `culture_weight_over_cap`.
- This flags cases where culture weight violates the policy that skill/technical evidence should dominate.

### 3. Must-have vs culture gate

Emit `must_have_underfit_high_culture` only when **all** of the following are true:

- `score_detail.must_have_match_rate < fairness_min_must_have_match_rate` (default 0.5)
- `agent_scores.confidence.culture > fairness_high_culture_confidence` (default 0.7)
- `candidate.score >= fairness_rank_score_floor` (default 0.7)
- This flags candidates where must-have coverage is low, culture confidence is high, and overall score is still high—i.e., “review cases where culture fit may be lifting a candidate above core requirements.”

### 4. Top-K seniority distribution check

- **Conditions:** (1) Top-K has at least 2 entries (and meets `fairness_topk_distribution_min`), and (2) the JD has **no** `preferred_seniority`.
- **Check:** normalize `seniority_level` of Top-K via `normalize_seniority()` (principal/lead/senior/mid/junior/unknown). If one level exceeds `fairness_seniority_concentration_threshold` (default 0.85), emit `seniority_concentration_topk`.
- This warns about unintended seniority skew when seniority was not specified in the JD.

### Output and frontend

- **Backend:** `JobMatchResponse.fairness` includes `FairnessAudit` (enabled, policy_version, checks_run, warnings). Each `FairnessWarning` contains code, severity, message, candidate_ids, metrics.
- **Per-candidate:** candidate-level warning messages are stored in `JobMatchCandidate.bias_warnings` as a list of strings.
- **Frontend:** `CandidateDetailModal` collects `bias_warnings` (and possibly gaps, etc.) and passes them to `BiasGuardrailBanner`, which renders a “Guardrail Alert” list.
- **Logging:** each warning is logged via `logger.warning("fairness_guardrail_triggered", code=..., severity=..., ...)` for monitoring/audit trails.

*Implementation:* `src/backend/services/matching/fairness.py`, `src/backend/core/jd_guardrails.py`  
*Frontend:* `BiasGuardrailBanner.tsx`, `CandidateDetailModal.tsx`
