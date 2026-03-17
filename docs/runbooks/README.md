# Runbook Evidence

운영 runbook 실행 시 **실제 테스트 결과·산출물**을 남겨 traceability(실행/테스트 증거)와 Reviewer Checklist 검증에 활용합니다.

## 목적

- **Traceability Matrix**: `Implemented` 상태는 "코드 + 문서 + **실행/테스트 증거**"를 요구함. Runbook 실행 기록이 D.*/DS.* 등 검증 증거로 사용됨.
- **재현성**: 동일 runbook을 나중에 다시 실행할 때 참고할 수 있는 기준선(예: 문서 수, 버전, 소요 시간).
- **리뷰/감사**: Reviewer Checklist의 "자동화된 테스트", "복구 탄력성" 등 항목에 대한 evidence로 제출 가능.

## 보관 위치

| 구분 | 경로 | 비고 |
|------|------|------|
| Evidence 파일 | `docs/runbooks/evidence/` | 실행일·runbook별로 1개 파일 |
| Runbook 본문 | `docs/data-flow/resume_ingestion_flow.md` 등 | 절차 정의 |

## Evidence 파일 규칙

### 파일명

- `{runbook_id}_{YYYY-MM-DD}.md` (예: `clean_rebuild_2026-03-17.md`)
- Runbook ID는 소문자·언더스코어만 사용.

### 필수 메타

- **runbook**: runbook 이름 + 본문 링크(예: `Clean Rebuild` → `docs/data-flow/resume_ingestion_flow.md#clean-rebuild-runbook-restored`)
- **executed_at**: 실행 일시 (ISO 8601 권장)
- **executor**: 실행자(팀/이름 또는 CI job id)
- **environment**: `local` / `staging` / `production` 등
- **git_ref**: 실행 시점 커밋 (예: `abc1234` 또는 `main@abc1234`)

### 본문 구조

1. **Steps**  
   Runbook 단계별로:
   - 수행한 명령(또는 작업 요약)
   - exit code / 성공 여부
   - 핵심 출력 일부(줄 수 제한 권장, 예: 마지막 20줄 또는 요약 통계만)
2. **Validation**  
   Runbook에 정의된 검증 항목 결과(예: normalization_version 일관성, core_skills empty 비율, API smoke 결과).
3. **Artefacts (선택)**  
   로그/스크린샷 경로, 외부 링크 등.

템플릿은 `docs/runbooks/evidence/_template.md` 참고.

## Runbook 목록

| Runbook ID | 설명 | 정의 위치 |
|------------|------|------------|
| `clean_rebuild` | Mongo 정리 → Mongo 적재 → 검증 → Milvus 적재 → API smoke | [Resume Ingestion Flow § Clean Rebuild Runbook](../data-flow/resume_ingestion_flow.md#clean-rebuild-runbook-restored) |

## 자동 수집 (선택)

- 검증 단계만 스크립트로 돌리고, 그 출력을 evidence 파일에 붙여넣는 방식으로 반자동화 가능.
- 예: `scripts/runbook_verify_ingestion.py` → `normalization_version`/`core_skills` 통계 출력 → `docs/runbooks/evidence/clean_rebuild_YYYY-MM-DD.md`에 "Validation" 섹션으로 추가.
- CI에서 runbook 전체를 돌리지 않고, **검증만** 주기 실행해 evidence를 생성하는 것도 가능.

## Traceability 연계

- **Requirements**: `requirements/traceability_matrix.md`의 Validation Evidence 열에 "runbook evidence"를 명시할 수 있음.  
  예: `docs/runbooks/evidence/clean_rebuild_*.md` (최신 1건 링크).
- Runbook 본문(예: `resume_ingestion_flow.md`) 마지막에 "최근 실행 evidence" 링크를 두면, 실행 증거를 한 곳에서 찾기 쉬움.
