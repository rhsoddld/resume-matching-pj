# Mongo Scoring Assessment

Date: 2026-03-13
Database: `resume_matching`
Collections reviewed: `candidates`, `jobs`

## Scope

This note evaluates which resume fields in MongoDB are reliable enough to use for candidate scoring right now.
The assessment is based on direct inspection of the live local MongoDB instance, not just the schema definition.

## Executive Summary

Your proposed scoring direction is mostly correct.
The best scoring core, based on the actual Mongo data, is:

1. `semantic_similarity`
2. `skill_overlap`
3. `experience_fit`
4. `seniority_fit` with reduced trust
5. `category_fit` as a source-conditional bonus, not a universal core feature

Optional features:

1. `education_fit`
2. `recency_fit` in a light form only

The biggest finding is that field availability is high overall, but quality differs sharply by source dataset:

1. `snehaanbhawal` has `category` and richer experience descriptions, but weaker location and education structure.
2. `suriyaganesh` has location and cleaner structured education/company fields, but `category` is completely missing and experience descriptions are empty.

That means some features should be source-aware or guarded by fallback logic.

## Collection Reality

`jobs` is empty right now.
So candidate-side scoring signals exist, but production-quality scoring still depends on how consistently the JD side is parsed.

`candidates` count: 5484

## Coverage Snapshot

Across all candidate documents:

| Field | Count | Coverage | Assessment |
| --- | ---: | ---: | --- |
| `embedding_text` | 5484 | 100.0% | Strong |
| `parsed.summary` | 5468 | 99.7% | Strong |
| `parsed.skills` | 5453 | 99.4% | Strong |
| `parsed.normalized_skills` | 5453 | 99.4% | Strong |
| `parsed.experience_years` | 5392 | 98.3% | Strong |
| `parsed.seniority_level` | 5392 | 98.3% | Available, but quality skewed |
| `parsed.experience_items` | 5422 | 98.9% | Good availability |
| `parsed.education` | 4793 | 87.4% | Useful as optional |
| `metadata.location` | 2920 | 53.2% | Source-dependent |
| `category` | 2484 | 45.3% | Too incomplete for universal core scoring |
| `metadata.phone` | 558 | 10.2% | Not useful for scoring |
| `metadata.linkedin` | 349 | 6.4% | Not useful for scoring |
| `metadata.email` | 101 | 1.8% | Not useful for scoring |
| `raw` | 5484 | 100.0% | Storage only, not scoring |

## Source-Level Differences

### `snehaanbhawal` (2484 docs)

| Field | Coverage |
| --- | ---: |
| `category` | 100.0% |
| `parsed.summary` | 100.0% |
| `parsed.skills` | 99.0% |
| `parsed.normalized_skills` | 99.0% |
| `parsed.experience_years` | 97.5% |
| `parsed.seniority_level` | 97.5% |
| `parsed.education` | 83.4% |
| `parsed.experience_items` | 97.5% |
| `metadata.location` | 0.0% |
| `ingestion.has_structured_enrichment` | 0.0% |

Quality notes:

1. `category` is fully populated.
2. `experience_items.description` exists for 97.5% of docs, which is very helpful for a light recency/relevance feature.
3. `education.degree` exists when education exists, but `education.institution` is effectively absent.
4. Skills are noisier. Some entries are clean (`excel`, `marketing`), but some are long phrases or extraction artifacts.

### `suriyaganesh` (3000 docs)

| Field | Coverage |
| --- | ---: |
| `category` | 0.0% |
| `parsed.summary` | 99.5% |
| `parsed.skills` | 99.8% |
| `parsed.normalized_skills` | 99.8% |
| `parsed.experience_years` | 99.0% |
| `parsed.seniority_level` | 99.0% |
| `parsed.education` | 90.7% |
| `parsed.experience_items` | 100.0% |
| `metadata.location` | 97.3% |
| `ingestion.has_structured_enrichment` | 100.0% |

Quality notes:

1. `category` is completely absent, so category scoring cannot be universal.
2. `experience_items` are structurally clean and usually include company and dates.
3. `experience_items.description` is empty for 100% of docs, so recency-by-skill-description is not available here.
4. Education is more structured than in `snehaanbhawal`, especially institution and location.

## Feature-by-Feature Assessment

### 1. `semantic_similarity`

Use now: yes

Why:

1. `embedding_text` exists for all 5484 candidates.
2. Current system already relies on Milvus similarity.
3. This is the most stable cross-source signal.

Verdict: keep as a top-weight core feature.

### 2. `skill_overlap`

Use now: yes

Primary field:

1. `parsed.normalized_skills`
2. fallback: `parsed.skills`

Why:

1. Coverage is 99.4%.
2. It is much more actionable than raw semantic similarity.
3. Missing-skill and matched-skill explanations can be generated directly.

Caution:

1. Some skill values are noisy phrases, especially in `snehaanbhawal`.
2. You should normalize JD-required skills to the same vocabulary style before computing overlap.
3. A small stoplist or post-cleaning layer would improve precision.

Verdict: definitely core.

### 3. `experience_fit`

Use now: yes

Field:

1. `parsed.experience_years`

Why:

1. Coverage is 98.3%.
2. It is numeric and easy to score deterministically.
3. It is present in both Mongo and Milvus retrieval output.

Verdict: definitely core.

### 4. `seniority_fit`

Use now: yes, but with lower trust than you originally implied

Field:

1. `parsed.seniority_level`

Why:

1. Coverage is 98.3%.
2. It helps when JD language is clearly junior/mid/senior/lead.

Main concern:

The distribution is very skewed:

1. `lead`: 4023
2. `junior`: 742
3. `mid`: 401
4. `senior`: 226

This does not look like a natural labor-market distribution.
It looks more like a heuristic label that may over-predict `lead`.

Verdict: useful as a weak support signal, not a heavy-ranking signal.

### 5. `category_fit`

Use now: conditionally

Field:

1. `category`

Why it is weaker than it first appears:

1. Global coverage is only 45.3%.
2. Coverage is 100% in `snehaanbhawal` and 0% in `suriyaganesh`.
3. That means a global `category_fit` would unfairly advantage one source and silently disappear for the other.

Verdict:

1. Do not make this a universal core feature.
2. Use it as a bonus only when both JD category and candidate category are present.
3. Consider source-aware weighting or missing-value neutral scoring.

### 6. `education_fit`

Use now: optional bonus

Field:

1. `parsed.education`

Why:

1. Coverage is 87.4%, which is high enough for an optional feature.
2. `suriyaganesh` has more structured institutions.
3. `snehaanbhawal` often compresses degree text into a single messy string.

Verdict:

1. Good for degree-level checks such as bachelor/master/phd presence.
2. Avoid aggressive school-name or major-matching logic at first.
3. Treat as bonus, not penalty-heavy scoring.

### 7. `recency_fit`

Use now: only light and guarded

Field:

1. `parsed.experience_items[].start_date`
2. `parsed.experience_items[].end_date`
3. optionally `parsed.experience_items[].description`

Reality:

1. Dates are present for almost all docs in both sources.
2. Description-based relevance is available in `snehaanbhawal`.
3. Description-based relevance is unavailable in `suriyaganesh`.

Verdict:

1. A pure date recency signal is feasible now.
2. A "recently used required skill" signal is only partially feasible.
3. Keep this lightweight and do not make it a core score until parsing is more uniform.

## Current Application State

Current matching logic is still much simpler than the available Mongo fields suggest.

Observed behavior in the codebase:

1. Milvus vector score is the primary ranker.
2. `min_experience_years` is applied as a filter.
3. Mongo is used mainly to enrich the response with summary and skills.

Implication:

The database is already rich enough to support hybrid scoring, but the service layer has not implemented it yet.

## Recommended Production Scoring

### Core version

Use this first:

```text
score =
0.38 * semantic_similarity
+ 0.30 * skill_overlap
+ 0.17 * experience_fit
+ 0.08 * seniority_fit
+ 0.07 * category_fit_conditional
```

Why this differs slightly from the original proposal:

1. `semantic_similarity`, `skill_overlap`, and `experience_fit` are the strongest real signals.
2. `seniority_fit` should be down-weighted because of the label skew.
3. `category_fit` should be weaker because it is absent for one full source.

### Extended version

If JD parsing is available:

```text
score =
0.34 * semantic_similarity
+ 0.28 * skill_overlap
+ 0.16 * experience_fit
+ 0.08 * seniority_fit
+ 0.05 * category_fit_conditional
+ 0.05 * education_fit_bonus
+ 0.04 * recency_fit_light
```

## Practical Recommendations

### Implement immediately

1. Hybrid score = vector similarity + skill overlap + experience fit.
2. Keep `seniority_fit` but cap its influence.
3. Make `category_fit` conditional on non-null category.
4. Return `matched_skills` and `missing_skills` for explainability.

### Implement carefully

1. Add a skill cleaning layer for noisy normalized skills.
2. Use source-aware fallback logic for category and recency.
3. Add education as a bonus feature only when JD specifies a degree requirement.

### Do not rely on yet

1. `metadata.email`
2. `metadata.phone`
3. `metadata.linkedin`
4. `raw`
5. `ingestion.*` as ranking features

## Bottom Line

Your overall judgment was right, but the live Mongo data suggests two refinements:

1. `category_fit` is not a true core feature yet because it only exists in one source.
2. `seniority_fit` is usable, but it should be treated as a weak heuristic because the label distribution is heavily skewed toward `lead`.

So the real "best current core" is:

1. `semantic_similarity`
2. `skill_overlap`
3. `experience_fit`
4. `seniority_fit` with low weight
5. `category_fit` only when present

And the best optional additions are still:

1. `education_fit`
2. `recency_fit` light version
