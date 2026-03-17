# Runbook Evidence: Clean Rebuild (EXAMPLE)

> 이 파일은 **예시**입니다. 실제 실행 후 메타와 출력을 채워 `clean_rebuild_YYYY-MM-DD.md`로 저장하세요.

## Meta

| Field | Value |
|-------|--------|
| **runbook** | Clean Rebuild — [Resume Ingestion Flow § Clean Rebuild Runbook](../../data-flow/resume_ingestion_flow.md#clean-rebuild-runbook-restored) |
| **executed_at** | 2026-03-17T10:00:00Z |
| **executor** | team / CI |
| **environment** | local |
| **git_ref** | main@abc1234 |

## Steps

### Step 1: Mongo `candidates` 콜렉션 정리

- **Command / action**: (운영 정책에 따라 수동 수행, 예: `db.candidates.deleteMany({})` 또는 drop)
- **Exit code**: N/A
- **Output (excerpt)**: (정리된 문서 수 또는 콜렉션 상태)

### Step 2: Mongo 적재

- **Command / action**: `python3 scripts/ingest_resumes.py --source all --target mongo --parser-mode hybrid`
- **Exit code**: 0
- **Output (excerpt)**:
  ```
  ...
  upserted: 5484
  normalization_version: 2024.1
  taxonomy_version: v1
  ```

### Step 3: 검증

- **Command / action**: normalization_version/taxonomy_version 일관성, core_skills empty 비율 확인
- **Exit code**: 0
- **Output (excerpt)**:
  ```
  docs with same normalization_version: 5484 (100%)
  docs with same taxonomy_version: 5484 (100%)
  core_skills empty: 42 (0.77%)
  ```

### Step 4: Milvus 적재

- **Command / action**: `python3 scripts/ingest_resumes.py --source all --target milvus --milvus-from-mongo --force-reembed`
- **Exit code**: 0
- **Output (excerpt)**:
  ```
  embedded=5484, embed_skipped=0
  ```

### Step 5: API smoke

- **Command / action**: `POST /api/jobs/match` + fallback/fairness metadata 확인
- **Exit code**: 200
- **Output (excerpt)**:
  ```json
  { "candidates": [...], "fallback_used": false, "fairness_metadata": {...} }
  ```

## Validation

| Check | Result | Notes |
|-------|--------|-------|
| normalization_version 일관성 | OK | 5484/5484 (100%) |
| taxonomy_version 일관성 | OK | 5484/5484 (100%) |
| core_skills empty 비율 | OK | 0.77% |
| API smoke | OK | 200, fallback/fairness 필드 존재 |

## Artefacts (optional)

- (로그 경로 또는 스크린샷)
