# Skill Ontology Refinement

Date: 2026-03-13

## Why Refinement Was Needed

- 1st-pass taxonomy included many role phrases and operational capability phrases.
- Substring-based heuristics could misclassify non-skill phrases (example: `excellent customer service` vs `excel`).
- Versioned product strings were mixed with canonical skills.

## Refinement Rules

- `core_skill`: exact whitelist + existing taxonomy metadata reuse.
- `role_like`: boundary-based role noun detection (no broad substring scoring).
- `versioned_skill`: strict version regex parsing into `canonical` and `version`.
- `capability_phrase`: action/operation phrases separated from core taxonomy.
- Ambiguous items remain in `review_required_refined` (conservative by design).

## Output Summary

- Slim core taxonomy entries: **66**
- Role-like candidates: **15**
- Versioned skills: **32**
- Capability phrases: **80**
- Review-required (refined): **69**
- Canonical merge candidates: **11**

## Representative Moves

- role_like moved examples:
  - `administrator`
  - `analyst`
  - `consultant`
  - `database administrator`
  - `developer`
  - `director`
  - `engineer`
  - `oracle database administrator`
  - `oracle dba`
  - `oracle sql developer`
- versioned_skill moved examples:
  - `microsoft sql server 2012`
  - `ms sql server 2012`
  - `oracle 10.2.0.5`
  - `oracle 10g`
  - `oracle 10g rac`
  - `oracle 10g/11g`
  - `oracle 11g`
  - `oracle 11g rac`
  - `oracle 11g/12c`
  - `oracle 11gr2`
- capability_phrase moved examples:
  - `database administration`
  - `database backup`
  - `database backup and recovery`
  - `database backup and restore`
  - `database backups`
  - `database cloning`
  - `database configuration`
  - `database consolidation`
  - `database creation`
  - `database deployment`

## Notes For Explainable Scoring

- Use only `skill_taxonomy_refined.yml` for direct skill overlap scoring.
- Use role/version/capability files as auxiliary explainability signals, not as core overlap matches.
- Keep alias normalization and taxonomy expansion as separate steps.

## Main Review Points

- SQL-family canonical merge candidates: `mssql`, `ms sql server`, `microsoft sql server` -> `sql server`.
- Security-family boundary cases: `information security`, `system security`, `security management`.
- Role/tool ambiguity: `oracle enterprise manager`, `sql developer`.
