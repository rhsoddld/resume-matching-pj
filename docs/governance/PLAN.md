---
name: resume-matching-capstone-plan
overview: Build and document an AI-powered resume matching system around deterministic ingestion, deterministic query understanding, hybrid retrieval, multi-agent evaluation, negotiated ranking, explainable output, and evaluation guardrails.
todos:
  - id: freeze-contracts
    content: 핵심 문서의 목표 아키텍처와 현재 구현 상태를 다시 고정하기
    status: completed
  - id: ingestion-pipeline
    content: 이력서 ingestion과 normalization, MongoDB / Milvus 인덱싱 파이프라인 유지 및 정리
    status: completed
  - id: baseline-matching-api
    content: FastAPI 기반 기본 매칭 API와 현재 하이브리드 점수 경로 유지
    status: completed
  - id: agent-evaluation-baseline
    content: Skill / Experience / Technical / Culture agent와 weight negotiation baseline 유지
    status: completed
  - id: query-understanding-v2
    content: deterministic structured query object v2를 정의하고 구현하기
    status: completed
  - id: query-understanding-v3-ontology
    content: JD parsing을 ontology-aligned role/skill/capability normalization으로 고도화하고 confidence/quality 지표를 노출하기
    status: completed
  - id: query-understanding-release-gate
    content: 직군별 golden set에 unknown_ratio/confidence 임계치를 추가하고 release gate 테스트로 고정하기
    status: completed
  - id: llm-fallback-policy
    content: deterministic query understanding 품질이 임계치 미만일 때만 제한적으로 LLM fallback 추출을 적용하기
    status: completed
  - id: hybrid-retrieval-v2
    content: vector + keyword + metadata를 동시 결합하는 hybrid retrieval로 확장하기
    status: completed
  - id: explainable-output-v2
    content: recommendation output에 gaps, weighting summary, evidence fields를 추가하기
    status: completed
  - id: deepeval-judge
    content: DeepEval 및 LLM-as-Judge 평가 루브릭과 실행 결과를 정리하기
    status: pending
  - id: bias-guardrails
    content: bias guardrails와 fairness metric 분석 경로를 문서화하고 구현하기
    status: pending
  - id: docs-sync-v2
    content: README, architecture, traceability, ADR를 목표 설계 기준으로 지속 동기화하기
    status: in_progress
isProject: false
---

## 목표 상태

최종 시스템은 아래 흐름을 명확하게 지원해야 한다.

1. 이력서는 offline deterministic ingestion pipeline에서 구조화되고 인덱싱된다.
2. JD는 deterministic query understanding layer에서 structured query object로 변환된다.
3. hybrid retrieval이 semantic, keyword, metadata 신호를 결합해 top-K 후보를 찾는다.
4. 4개의 evaluation agent가 후보를 서로 다른 관점에서 평가한다.
5. recruiter agent와 hiring manager agent가 서로 다른 weight를 제안한다.
6. negotiation agent가 최종 scoring weight를 확정한다.
7. ranking engine이 explainable recommendation을 반환한다.
8. DeepEval, LLM-as-Judge, Bias guardrails가 품질과 공정성을 검증한다.

## 현재 상태 요약

| Workstream | 상태 | 메모 |
|-----------|------|------|
| Offline ingestion / indexing | Done | MongoDB + Milvus 적재 경로와 normalization pipeline 존재 |
| Deterministic JD parsing | Done v3 baseline | query_profile에 roles/signals/metadata filters/lexical-query/semantic-expansion/confidence + fallback 메타데이터를 포함해 응답 제공 |
| Hybrid retrieval | Done baseline | vector + keyword + metadata fusion score 기반 shortlist 적용 |
| Multi-agent evaluation | Done baseline | 4-agent 계약과 orchestration 존재 |
| Weight negotiation | Done baseline | recruiter / hiring manager / final weight 구조 존재 |
| Explainable ranking output | Done baseline | `possible_gaps`, `weighting_summary`, `relevant_experience` 응답/화면 노출 완료 |
| Eval / guardrails | Partial | DeepEval stub 존재, bias guardrails는 미구현 |

## 다음 구현 우선순위

### Priority 1. Query Understanding v2

- `job_category`, `required_skills`, `related_skills`, `seniority_hint`, `filters`, `query_text_for_embedding`를 명시한 구조체 도입
- skill taxonomy mapping / alias normalization / role inference / keyword extraction / seniority heuristic 정리
- retrieval / agent / explanation이 동일 Query 객체를 사용하도록 계약 통일

### Priority 1-1. Query Understanding v3 Hardening

- ingestion과 동일 ontology/alias 기준으로 JD term extraction 일치율 측정
- role / skill / capability strength(`must have`, `main focus`, `nice to have`, `familiarity`) 정확도 보정
- `signal_quality.unknown_ratio`와 `confidence` 임계치 운영 정책 수립

### Priority 1-2. Deterministic-First Fallback Ops

- 저신뢰 JD에서만 동작하는 constrained LLM fallback 운영 로그/모니터링 추가
- fallback 비율, 이유(low_confidence / high_unknown_ratio), 개선 효과를 주간 리포트로 추적
- fallback 결과의 ontology normalization drift 점검 규칙 추가

### Priority 2. Hybrid Retrieval v2

- vector search 점수
- keyword overlap 점수
- metadata filter / boost
- shortlist merge policy

이 4개를 한 retrieval spec으로 문서화하고 구현한다.

### Priority 3. Explainable Recommendation v2

- candidate summary
- per-agent score
- matched skills / missing skills
- relevant experience
- technical strengths
- possible gaps
- recruiter vs hiring manager weighting summary

응답 계약과 UI 표시 항목을 함께 고정한다.

### Priority 4. Evaluation and Guardrails

- DeepEval ranking quality metric
- LLM-as-Judge explanation clarity / justification metric
- fairness metric 정의
- 민감속성 배제 규칙
- explanation auditing 방식

## 완료 기준

아래 조건을 만족하면 목표 설계와 현재 구현이 충분히 수렴했다고 본다.

1. Query object v2가 코드, API, 문서에 동일하게 반영된다.
2. hybrid retrieval이 fallback이 아니라 다중 신호 결합 구조로 동작한다.
3. explainable recommendation이 recruiter와 hiring manager 관점 차이를 보여준다.
4. 최소 1회 이상 DeepEval / LLM-as-Judge 결과가 문서화된다.
5. Bias guardrails 정책이 문서뿐 아니라 코드 경로와 연결된다.

## Backlog

| ID | 항목 | 우선순위 |
|----|------|---------|
| BL-01 | fairness dashboard / bias monitoring 시각화 | Low |
| BL-02 | retrieval fusion weight 실험 자동화 | Medium |
| BL-03 | role-specific weight profiles 저장 / 버전 관리 | Medium |
| BL-04 | reviewer demo용 canned dataset 및 시나리오 추가 | Medium |
| BL-05 | feedback loop 기반 랭킹 보정 | Medium |
| BL-06 | query fallback 운영 대시보드(비율/원인/품질 개선효과) | Medium |
