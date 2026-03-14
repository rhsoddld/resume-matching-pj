# REPOSITORY STRUCTURE RULES

이 문서는 현재 저장소 구조를 기준으로 코드/문서 배치 원칙을 정의한다.

## 1. Top-Level Layout

```text
resume-matching-pj/
├── config/
├── data/
├── docs/
│   ├── adr/
│   ├── architecture/
│   ├── data-flow/
│   ├── eval/
│   ├── governance/
│   └── ontology/
├── requirements/
├── scripts/
├── src/
│   ├── backend/
│   ├── domain_agents/
│   ├── eval/
│   ├── frontend/
│   └── ops/
└── tests/
```

## 2. Source Ownership

| Path | Ownership | Rule |
|---|---|---|
| `src/backend/api/` | HTTP interface | 라우터는 요청/응답 처리만 담당, 비즈니스 로직 금지 |
| `src/backend/services/` | business orchestration | 도메인 로직/유스케이스 조합 담당 |
| `src/backend/repositories/` | DB access | 쿼리/저장소 접근만 담당 |
| `src/backend/schemas/` | contracts | Pydantic 요청/응답/내부 계약 정의 |
| `src/backend/core/` | infra core | 설정/클라이언트/예외/스타트업 공통 처리 |
| `src/domain_agents/` | agent logic | skill/experience/technical/culture/negotiation/ranking 책임 분리 |
| `src/eval/` | evaluation code | golden set 기반 품질 평가 코드 |
| `src/ops/` | observability | structured logging, request-id middleware |
| `src/frontend/` | UI | API 소비 및 결과 시각화 |

## 3. Documentation Ownership

| Path | Purpose |
|---|---|
| `docs/architecture/` | 시스템 아키텍처와 레이어 책임 |
| `docs/data-flow/` | 런타임 플로우와 파이프라인 설명 |
| `docs/governance/` | 운영 규칙/계획/트레이서빌리티 |
| `docs/adr/` | 핵심 의사결정 기록 |
| `docs/eval/` | 평가 실행 결과 artifact |
| `requirements/` | 문제정의/요구사항 원문 및 정규화 문서 |

규칙:

1. 구현 상태 문서는 `README.md`, `docs/governance/PLAN.md`, `docs/governance/TRACEABILITY.md`가 동일 기준을 사용한다.
2. 목표 상태와 현재 상태를 혼동하지 않도록 반드시 구분해서 기록한다.
3. 새 기능 도입 시 코드와 함께 관련 문서를 같은 PR/커밋 범위에서 업데이트한다.

## 4. Tests Rules

`tests/`는 API/서비스/에이전트/랭킹 정책을 검증하는 회귀 테스트 집합이다.

- `tests/test_api_endpoints.py`
- `tests/test_agent_orchestration_service.py`
- `tests/test_agent_io_contracts.py`
- `tests/test_query_fallback_policy.py`
- `tests/test_retrieval_fallback.py`
- `tests/test_candidate_enricher_filters.py`
- `tests/test_job_profile_extractor.py`
- `tests/test_skill_overlap_scoring.py`
- `tests/test_rerank_pipeline.py`
- `tests/test_ranking_policy.py`

규칙:

1. 핵심 서비스(`matching`, `retrieval`, `scoring`, `agent_orchestration`) 변경 시 해당 테스트를 함께 업데이트한다.
2. 버그 수정 시 재발 방지 테스트를 최소 1개 추가한다.

## 5. Script and Config Rules

| Path | Rule |
|---|---|
| `scripts/` | 분석/마이그레이션/운영 보조 도구만 허용, 핵심 도메인 로직 금지 |
| `config/` | taxonomy/alias/정규화 규칙의 single source of truth로 유지 |

## 6. Guiding Principle

폴더 구조만 봐도 시스템 아키텍처와 책임 경계가 읽혀야 한다.
