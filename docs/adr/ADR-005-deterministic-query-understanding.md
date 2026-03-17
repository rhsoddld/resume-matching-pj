# ADR-005 Deterministic Query Understanding (JD Parsing)

## Decision
Use deterministic JD (Job Description) parsing with skill taxonomy and YAML config—no LLM for the default query-understanding path.

## Why
- Predictable, fast, and no per-request LLM cost
- Skill taxonomy + alias normalization + role inference give sufficient signal quality for capstone scope
- `signal_quality` and `confidence` enable retrieval/rerank gating and evaluation tracking

## Consequences
- Nuanced or highly non-standard JDs may benefit from optional LLM query fallback (low confidence / high unknown_ratio)
- Taxonomy and config (e.g. `skill_taxonomy.yml`, `job_filters.yml`) must be maintained; quality depends on coverage

*Implementation:* `src/backend/services/job_profile_extractor.py`, `src/backend/core/filter_options.py`, `config/*.yml`
