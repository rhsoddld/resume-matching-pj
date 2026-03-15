# Retrieval Quality Report

- Run at (UTC): `2026-03-15T11:41:29Z`
- Top-k: `10`
- Label filter: `good`
- Evaluated entries: `28`

## KPI Summary

| Metric | Value | Target | Status |
|---|---|---|---|
| avg precision@10 | 0.0073 | — | — |
| avg recall@10 | 0.4725 | ≥ 0.50 | ❌ MISS |
| F1@10 | 0.0144 | — | — |

## Per-Entry Results

| ID | Label | precision@10 | recall@10 |
|---|---|---|---|
| gs-001 | good | 0.0095 | 0.7500 |
| gs-002 | good | 0.0114 | 1.0000 |
| gs-003 | good | 0.0099 | 0.8571 |
| gs-004 | good | 0.0099 | 0.6667 |
| gs-005 | good | 0.0081 | 0.6667 |
| gs-006 | good | 0.0056 | 0.3333 |
| gs-008 | good | 0.0120 | 0.6250 |
| gs-009 | good | 0.0042 | 0.3333 |
| gs-010 | good | 0.0062 | 0.5714 |
| gs-011 | good | 0.0064 | 0.5000 |
| gs-013 | good | 0.0085 | 0.5000 |
| gs-014 | good | 0.0050 | 0.3333 |
| gs-016 | good | 0.0083 | 0.7500 |
| gs-017 | good | 0.0087 | 0.5000 |
| gs-018 | good | 0.0156 | 0.7143 |
| gs-019 | good | 0.0071 | 0.3750 |
| gs-020 | good | 0.0078 | 0.5000 |
| gs-021 | good | 0.0116 | 0.4286 |
| gs-022 | good | 0.0000 | 0.0000 |
| gs-023 | good | 0.0035 | 0.1250 |
| gs-024 | good | 0.0081 | 0.5000 |
| gs-025 | good | 0.0103 | 0.5714 |
| gs-026 | good | 0.0057 | 0.4286 |
| gs-027 | good | 0.0043 | 0.2857 |
| gs-028 | good | 0.0081 | 0.2857 |
| gs-029 | good | 0.0040 | 0.2000 |
| gs-030 | good | 0.0000 | 0.0000 |
| gs-031 | good | 0.0045 | 0.4286 |

## Interpretation

- **recall@k**: fraction of expected skills found in top-k retrieved candidates' skill pools
- **precision@k**: fraction of retrieved skills that overlap with expected skills
- Target: recall@k ≥ 0.50 (improvement path: tune fusion weights via `RETRIEVAL_VECTOR_WEIGHT`, `RETRIEVAL_KEYWORD_WEIGHT`, `RETRIEVAL_METADATA_WEIGHT`)