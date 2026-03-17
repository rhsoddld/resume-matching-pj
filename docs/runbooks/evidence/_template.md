# Runbook Evidence: {RUNBOOK_NAME}

<!-- Fill runbook name, e.g. Clean Rebuild -->

## Meta

| Field | Value |
|-------|--------|
| **runbook** | {runbook name} — 본문 링크: {path} |
| **executed_at** | YYYY-MM-DDTHH:MMZ |
| **executor** | name or CI job id |
| **environment** | local / staging / production |
| **git_ref** | commit hash or branch@hash |

## Steps

### Step 1: (runbook step title)

- **Command / action**: `...`
- **Exit code**: 0
- **Output (excerpt)**:
  ```
  (paste last N lines or summary stats only)
  ```

### Step 2: ...

(Repeat per runbook step.)

## Validation

| Check | Result | Notes |
|-------|--------|-------|
| normalization_version / taxonomy_version | OK / FAIL | e.g. all same version |
| core_skills empty ratio | X% | threshold if any |
| API smoke POST /api/jobs/match | 200, fallback/fairness present | optional: sample response snippet |

## Artefacts (optional)

- Log path or URL: ...
- Screenshot: ...
