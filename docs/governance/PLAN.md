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
  - id: agents-sdk-migration
    content: 4개 평가 agent + recruiter/hiring manager + negotiation orchestration을 OpenAI Agents SDK runtime으로 전환하기
    status: in_progress
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
    status: completed
  - id: bias-guardrails
    content: bias guardrails와 fairness metric 분석 경로를 문서화하고 구현하기
    status: completed
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
| Multi-agent evaluation | Done baseline (hybrid runtime) | score pack 생성은 SDK/live/heuristic 경로를 지원하며 서비스 레벨 fallback 유지 |
| Weight negotiation | Done baseline (SDK handoff + fallback) | negotiation 구간은 `Recruiter -> HiringManager -> WeightNegotiation` handoff를 시도하고 실패 시 degrade |
| Explainable ranking output | Done v3 baseline | UI에서 runtime mode/fallback reason/recruiter·hiring·final policy까지 노출 |
| Eval / guardrails | Partial | DeepEval/LLM-as-Judge(quality/diversity/custom/potential) + live judge 아카이빙 + bias guardrails backend v1 구현 완료, 남은 작업은 fairness metric 운영 고도화 |

## 다음 구현 우선순위 (requirements/requirements.md 기준)

### Priority 1. API/Core Gap Closing

- `R1.9`: ingestion 기능을 API endpoint로 노출 (완료: `POST /api/ingestion/resumes`)
- `PO.4`: PDF/포트폴리오 링크 처리 경로 보강
- `D.3`: README의 실행/운영 시나리오를 API 중심으로 갱신

### Priority 2. Advanced Eval & Guardrails

- `R2.7`: bias detection guardrail 운영 고도화(대시보드/임계치/triage)
- `D.2`: bias mitigation 근거를 설계 문서에 연결

### Priority 3. Ranking and Performance

- `MSA.1`: SDK handoff가 negotiation 구간에 적용된 상태에서 4-agent 실행 경로까지 handoff-native로 확장
- `R2.3`: fine-tuned embedding rerank는 현재 intentionally deferred. capstone 범위에서는 실제 학습/운영 대신 baseline rerank 실험 근거만 유지
- `HCR.3`: shortlist 이후 LLM rerank baseline의 latency/quality benchmark 및 timeout/fallback 정책 고정
- `R2.5`: token usage optimization (요청 예산/캐시/배치)
- `R2.6`: candidates/sec 벤치마크 결과 자동 아카이브 유지 + 고부하 부하 테스트 자동화

### Priority 4. Hiring Intelligence Expansion

- `AHI.2`: recruiter feedback loop 데이터 모델/API 추가
- `AHI.3`: hiring analytics dashboard 구현
- `AHI.4`: interview scheduling agent handoff 경로 추가
- `AHI.5`: A2A negotiation audit trail 강화

## 완료 기준

아래 조건을 만족하면 목표 설계와 현재 구현이 충분히 수렴했다고 본다.

1. `requirements/requirements.md`의 모든 ID가 TRACEABILITY에 증거 링크를 가진다.
2. `R1.9`, `R2.5~R2.6`, `AHI.2~AHI.4`가 Planned에서 최소 Partial 이상으로 상승한다.
3. 최소 1회 이상 평가 실행 결과가 `docs/eval/eval-results.md`로 기록된다.
4. README, AGENT, TRACEABILITY, ADR의 상태 표기가 동일한 기준(Implemented/Partial/Planned)을 유지한다.
5. 제출물 기준으로 `D.1`(JPEG/PDF 아키텍처), `D.4`(발표 자료)가 준비된다.

## Backlog

| ID | 항목 | 우선순위 |
|----|------|---------|
| BL-01 | fairness dashboard / bias monitoring 시각화 | Low |
| BL-02 | retrieval fusion weight 실험 자동화 | Medium |
| BL-03 | role-specific weight profiles 저장 / 버전 관리 | Medium |
| BL-04 | reviewer demo용 canned dataset 및 시나리오 추가 | Medium |
| BL-05 | feedback loop 기반 랭킹 보정 | Medium |
| BL-06 | query fallback 운영 대시보드(비율/원인/품질 개선효과) | Medium |
| BL-07 | Agents SDK observability tracing 표준화 | Medium |
| BL-08 | ingestion API endpoint + 인증/레이트리밋 설계 | High |
| BL-09 | candidates/sec 고부하 부하 테스트 자동화 및 CI 리포트 고도화 | High |
