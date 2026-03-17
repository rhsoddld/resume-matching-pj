# Problem Definition

**요구사항↔구현 추적·레뷰어 가이드:** [docs/governance/TRACEABILITY.md](../docs/governance/TRACEABILITY.md)

## Scope
이 프로젝트는 자연어 Job Description(JD)을 해석하고, 대규모 이력서 풀에서 적합 후보를 검색/평가/설명하는 AI 기반 후보 매칭 시스템을 구축한다.

핵심 범위:
- deterministic ingestion 및 normalization
- deterministic query understanding
- hybrid retrieval(vector + lexical + metadata)
- multi-agent evaluation
- recruiter/hiring-manager weight negotiation
- explainable ranking

## Core Problem Statements (Legacy Requirements Restored)

| ID | Problem Statement |
|---|---|
| PO.1 | 단순 키워드 검색만으로는 기술 적합성, 숙련도 깊이, 경력 맥락을 충분히 평가하기 어렵다. |
| PO.2 | 위치/학력/산업 배경 같은 메타데이터를 함께 해석하지 않으면 실제 채용 의사결정 품질이 낮아진다. |
| PO.3 | exact match 중심 검색은 transferable/adjacent skill 후보를 놓친다. |
| PO.4 | CSV/PDF/비정형 텍스트 등 포맷 다양성 때문에 파싱 품질 편차가 크다. |
| PO.5 | 점수만 제공하는 시스템은 실무 신뢰를 얻기 어렵고, 설명 가능한 근거가 필요하다. |
| PO.6 | 대규모 후보군 수동 검토는 느리고 일관성이 낮아 자동화/표준화가 필요하다. |

## Objectives

| ID | Objective |
|---|---|
| OBJ.1 | JD를 구조화 query profile로 변환해 검색 신호 품질을 안정화한다. |
| OBJ.2 | retrieval 단계에서 relevant candidate recall을 우선 보장한다. |
| OBJ.3 | 후보별 skill/experience/technical/culture 평가와 합의형 가중치 정책을 제공한다. |
| OBJ.4 | 최종 추천 결과에 score breakdown, evidence, gap을 포함한 explainability를 제공한다. |
| OBJ.5 | 평가(quality/performance/reliability/fairness) 지표를 재현 가능한 형태로 축적한다. |

## Non-Goals (Current Capstone Boundary)

- ingestion 단계에서 생성형 LLM 파싱을 기본 경로로 사용하지 않는다.
- fine-tuned embedding 학습/운영 파이프라인은 후속 고도화로 남긴다.
- full ATS 대체 제품 범위(승인 워크플로/캘린더 통합/조직 권한 모델)는 현재 범위 밖이다.
