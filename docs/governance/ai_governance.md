# AI Governance

## Governance Mission (Legacy AGENT/PLAN Merged)

시스템 거버넌스 목표:
1. ingestion/query understanding의 deterministic-first 원칙 유지
2. retrieval -> evaluation -> negotiation -> ranking의 책임 경계 명확화
3. explainable output과 fairness guardrail을 기본 계약으로 유지
4. 요구사항-코드-평가 산출물의 추적성 확보

## Canonical Documents and Roles

| 문서 | 역할 |
|---|---|
| `requirements/problem_definition.md` | 문제 정의 / 목표 |
| `requirements/functional_requirements.md` | 요구사항 ID 체계 (R1/R2/HCR/MSA/AHI/D/DS) |
| `requirements/traceability_matrix.md` | 구현/검증/문서 증거 연결 |
| `docs/architecture/system_architecture.md` | 목표 아키텍처와 레이어 책임 |
| `docs/data-flow/*.md` | ingestion/retrieval 런타임 흐름 |
| `docs/evaluation/*.md` | 평가 기준/결과 |
| `docs/adr/*.md` | 설계 결정과 배경 |

## Status Labels

- `Implemented`: 코드/문서/검증 증거 모두 존재
- `Partial`: 코드는 있으나 운영 검증 또는 품질 증거가 부족
- `Planned`: 설계/백로그 상태

## Governance Control Rules

1. 신규 기능은 코드와 문서를 같은 변경 단위로 업데이트한다.
2. 점수/프롬프트/모델 라우팅 변경 시 최소 1개 이상 평가 증거를 남긴다.
3. fallback 정책(`sdk_handoff -> live_json -> heuristic`)은 문서와 구현을 동기화한다.
4. 민감 속성은 점수 근거에서 제외하고, 관련 경고를 응답/로그에 남긴다.
5. 버전 필드(`normalization_version`, `taxonomy_version`, `embedding_text_version`, `PROMPT_VERSION`)를 변경하면 변경 이유를 문서화한다.

## Review Cadence

| 주기 | 검토 항목 |
|---|---|
| 매 PR | 요구사항 영향, 테스트 영향, 문서 영향 |
| 주간 | retrieval/agent/fairness 지표 추세 |
| 릴리스 전 | traceability matrix 최신화, evaluation 결과 검토, ADR 갱신 |

## Current Governance Priorities

1. retrieval quality 회귀 감지 자동화
2. rerank 효과 대비 latency/cost 검증 고도화
3. fairness 경고 지표의 운영 대시보드 정착
4. feedback loop 및 hiring intelligence 근거 데이터 강화
