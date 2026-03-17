# Golden Set Alignment Plan (2026-03-16)

## Why
- Goal: keep `golden_set` aligned with current ingestion normalization/ontology so retrieval quality can be tracked without label/schema mismatch noise.
- Scope: expected skill vocabulary alignment + role-family specific query extraction hardening (`junior_software`, `senior_architect`).

## Ontology Gap Patch List
Added to [`config/skill_taxonomy.yml`](../../config/skill_taxonomy.yml):

- `api testing`
- `ci/cd`
- `cloud architecture`
- `dashboarding`
- `data structures`
- `distributed systems`
- `fastapi`
- `feature engineering`
- `model deployment`
- `process mapping`
- `pytest`
- `pytorch`
- `requirements gathering`
- `rest api`
- `security by design`
- `selenium`
- `spring boot`
- `stakeholder management`
- `stakeholder reporting`
- `system architecture`
- `technical leadership`
- `test automation`
- `unit testing`
- `enterprise integration` (optional skill alignment)
- `cost optimization` (optional skill alignment)
- `solution governance` (optional skill alignment)

Added alias mappings to [`config/skill_aliases.yml`](../../config/skill_aliases.yml) for common variants:

- `rest api integration -> rest api`
- `cicd/ci cd/continuous integration -> ci/cd`
- `springboot -> spring boot`
- `fast api -> fastapi`
- `qa automation -> test automation`
- `unit test(s) -> unit testing`
- `py test -> pytest`
- `selenium webdriver -> selenium`
- `solution architecture/enterprise architecture -> system architecture`
- `secure by design -> security by design`
- `technical lead -> technical leadership`

## Query Extraction Hardening
Updated [`src/backend/services/job_profile_extractor.py`](../../src/backend/services/job_profile_extractor.py):

- Strengthened role patterns:
  - `junior software engineer`
  - `graduate software engineer`
  - `associate engineer`
- Added phrase skill hints:
  - junior tracks: python/java/git/data structures/unit testing
  - senior architect tracks: system architecture/distributed systems/cloud architecture/technical leadership/security by design
- Added capability hints:
  - `software engineering fundamentals`
  - `architecture leadership`
- Improved role inference:
  - junior/senior architect string signals reflected directly into role candidates

## Continuous Update Loop
Run these after ontology changes or golden set edits:

1. Audit + aligned golden set refresh
```bash
./scripts/update_golden_set.sh
```

2. Retrieval-only eval with normalized golden
```bash
GOLDEN_SET=src/eval/golden_set.normalized.jsonl ./scripts/run_retrieval_eval.sh
```

3. Rerank eval with normalized golden
```bash
GOLDEN_SET=src/eval/golden_set.normalized.jsonl ./scripts/run_rerank_eval.sh
```

4. Check outputs
- `src/eval/outputs/retrieval_eval.json`
- `src/eval/outputs/rerank_eval.json`
- `src/eval/outputs/golden_skill_gap_report.md`

## Gating Rule (Fast)
- Compare retrieval KPIs only when `unmapped unique skills == 0` in `golden_skill_gap_report.md`.
- If unmapped > 0, strengthen ontology/alias first, then re-run eval.
