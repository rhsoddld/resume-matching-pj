# 설계 근거: 온톨로지, 비용, 평가

**목적:** 이 문서는 “왜 스킬 온톨로지인가”, “장기 비용 구조”, “평가 수치와 관점”을 한곳에 정리해 설계 의사결정과 운영 방향을 설명한다.

**관련 문서:** [Key Design Decisions](./key-design-decisions.md), [evaluation_plan.md](../evaluation/evaluation_plan.md), [cost_control.md](../governance/cost_control.md), [ADR-004](../adr/ADR-004-agent-orchestration.md). **에이전트 평가·스코어링 상세:** [agents/agent_evaluation_and_scoring.md](../agents/agent_evaluation_and_scoring.md).

---

## 1. 왜 온톨로지(Ontology)인가? — Agentic AI 친화성

### 1.1 정의

본 시스템의 **스킬 온톨로지**는 다음으로 구성된다.

- **Core taxonomy** (`config/skill_taxonomy.yml`): 스킬 → `domain`, `family`, `parents` 계층
- **Aliases** (`config/skill_aliases.yml`): 동의어/표현 → canonical 스킬 매핑
- **Role candidates** (`config/skill_role_candidates.yml`): 역할 후보 집합
- **Capability phrases** (`config/skill_capability_phrases.yml`): 역량 표현 구문
- **Versioned skills** (`config/versioned_skills.yml`): 버전별 스킬 정규화
- **Review required** (`config/skill_review_required.yml`): 검토 대상 스킬

런타임에는 `RuntimeSkillOntology`가 위 설정을 로드해 **JD 파싱 · retrieval · scoring · 에이전트 평가** 전 단계에서 동일한 vocabulary와 계층을 사용한다.

### 1.2 Agentic AI와의 궁합

에이전트 기반 평가(Agentic AI)와 온톨로지를 함께 쓰는 이유는 다음과 같다.

| 관점 | 설명 |
|------|------|
| **입력/출력의 일관성** | 에이전트가 “무엇을 평가할지”가 온톨로지로 고정된다. JD에서 뽑은 `required_skills`·`related_skills`·`role`이 모두 canonical/alias 정규화되어 있어, 에이전트 프롬프트와 도구 입력이 **같은 용어 체계**를 따른다. |
| **작업 범위의 명시성** | 스킬 후보 추출(`_extract_ontology_candidates`), 역할 추론(`_infer_roles`), 역량 시그널(`_extract_capability_signals`), 인접 스킬(`find_adjacent_skills`)이 모두 온톨로지 vocabulary 기반이다. 에이전트는 “이미 구조화된 요구사항”에 대해 점수와 근거만 내면 되므로, 할 일이 명확하다. |
| **Transferable/adjacent skill** | PO.3(transferable/adjacent skill 후보 누락)을 위해 `find_adjacent_skills`(domain/family/parents 공유)와 `adjacent_match_score`로 **동일 온톨로지 내**에서 확장 매칭을 한다. 에이전트는 “이 스킬은 저 스킬과 domain/family가 같다”는 식의 설명을 일관된 용어로 할 수 있다. |
| **도구와의 정합성** | 에이전트가 사용하는 `search_candidate_evidence` 등은 retrieval 결과·JD 프로필과 같은 스키마를 사용한다. 프로필이 온톨로지로 정규화되어 있으므로, 에이전트가 참조하는 “증거”와 “요구 스킬”이 서로 대응 가능하다. |
| **유지보수와 확장** | 스킬 추가/통합은 YAML 수정으로 이루어지고, 에이전트 코드를 바꾸지 않고도 vocabulary와 계층이 확장된다. 에이전트 행동은 “주어진 ontology”에 맞춰 자동으로 확장된다. |

정리하면, **온톨로지는 “에이전트가 이해하고, 말하고, 평가하는 대상”을 하나의 체계로 묶어 주기 때문에 Agentic AI와 친화적**이다.

### 1.3 파이프라인 내 사용처

- **Query understanding** (`job_profile_extractor.py`): JD → ontology 기반 `required_skills`, `related_skills`, `role`, `core_skills`, `adjacent_skills`(evidence 포함)
- **Filter options** (`filter_options.py`): `skill_taxonomy.yml`의 domain/family를 industries/job_families와 병합해 API 옵션 제공
- **Match result** (`match_result_builder.py`): `adjacent_match_score`로 JD 관련 스킬–후보 스킬 간 인접 매칭 점수·매칭 목록 계산
- **Ingestion** (`ingestion/transformers.py`): 이력서 스킬을 온톨로지 계층(parents 등)으로 보강

---

## 2. 장기 비용이 유리한 이유 — 에이전트 작업 처리의 비용 효과

### 2.1 설계 원칙: deterministic-first, 에이전트는 선택적

- **Deterministic 경로**가 기본: JD 파싱(온톨로지+규칙), hybrid retrieval, deterministic scoring은 LLM 호출 없이 처리된다.
- **고비용 단계(에이전트, rerank)**는 **조건·상한**이 있을 때만 실행되도록 설계했다.

이렇게 하면 “비싼 작업”을 **꼭 필요한 후보·쿼리에만** 쓰게 되어, 장기적으로 비용이 줄어든다.

### 2.2 에이전트에 의한 작업 처리의 비용 극대화

| 메커니즘 | 설명 |
|----------|------|
| **`agent_eval_top_n` 상한** | 에이전트 평가를 받는 후보 수를 상한으로 막는다. 나머지 후보는 deterministic score만 사용. 토큰 지출이 “상위 N명”으로 제한된다. |
| **캐시 (LRU + TTL)** | 동일/유사 JD에 대한 반복 요청은 retrieval·에이전트·rerank 없이 캐시에서 반환. 반복 질의 비용이 크게 감소한다. |
| **Rerank 비활성 기본값** | Rerank는 품질 대비 지연/비용이 아직 정당화되지 않아 기본 꺼짐. 에이전트 비용만으로도 목표 품질을 맞추는 방향이다. |
| **Fallback 체인** | SDK handoff → live_json → heuristic 순으로 fallback하므로, 에이전트 실패 시에도 토큰 추가 소모 없이 휴리스틱으로 결과를 낸다. |
| **온톨로지로 “질 높은 입력”** | JD·후보가 온톨로지로 정규화되어 있어, 에이전트가 불필요한 추론이나 긴 문맥 없이도 “무엇을 볼지” 명확하다. 프롬프트/토큰을 요구사항 평가에 집중할 수 있다. |

즉, **에이전트가 “처리하는 작업량”을 상한 짓고, 나머지는 deterministic·캐시로 처리**함으로써 **에이전트 비용 대비 효과를 극대화**하는 구조다.

### 2.3 정리

- **장기적으로 비용이 좋은 이유:** 고비용 LLM(에이전트)을 **꼭 필요한 경우·상위 N명**에만 쓰고, 나머지는 온톨로지 기반 deterministic + 캐시로 처리하기 때문이다.
- **에이전트에 의한 작업 처리**가 “많은 후보를 다 LLM으로 보는 것”이 아니라 **“정제된 입력 + 제한된 수의 후보”**에만 적용되므로 비용 효과가 크다.

상세 제어 항목은 [cost_control.md](../governance/cost_control.md) 참고.

---

## 3. 평가(Eval): 수치가 적은 이유, 어떤 관점에서 하나?

### 3.1 “Eval 수치가 적다”의 두 가지 의미

- **(A) 측정된 지표 값이 낮다**  
  예: recall@10 목표 대비 부족, groundedness/agreement 수치가 아직 낮음 등.
- **(B) 평가에 쓰는 데이터 포인트/실험 수가 적다**  
  예: short-eval은 6개 쿼리 등 소규모 subset 위주; full golden 50은 있으나 상시 full run은 아님.

아래는 두 가지를 구분해 정리한다.

### 3.2 Eval을 보는 관점 (Evaluation Philosophy)

평가는 **단일 점수**가 아니라 **단계(stage)별·재현 가능·리뷰어 대면**으로 설계된다.

| 원칙 | 내용 |
|------|------|
| **Retrieval-first truth** | 하류 rerank/에이전트는 “한번 retrieval에서 빠진 후보”를 복구할 수 없다. 따라서 **retrieval 품질(recall@10/20, MRR)**이 최우선 품질 게이트다. |
| **Stage attribution** | 품질·지연·비용을 **query understanding / retrieval / rerank / agent** 단계별로 분해해 측정한다. |
| **Measurable over anecdotal** | 주장은 명시적 KPI(recall, MRR, NDCG@5, groundedness, agreement 등)에 매핑되어야 한다. |
| **Traceability** | 평가 결과는 버전된 입력(golden set, ontology, 코드)과 실행 명령으로 재현 가능해야 한다. |
| **Operational axes** | 품질뿐 아니라 fairness, reliability, cost, latency를 별도 축으로 평가한다. |

따라서 “eval”은 **한 번의 점수**가 아니라 **retrieval → rerank → agent**를 나누어, 각 단계가 기여하는지·비용 대비 가치가 있는지를 보는 것이다.

### 3.3 왜 (일부) Eval 수치가 낮은가?

- **Retrieval**  
  - Short-eval 기준 recall@10 ≈ 0.525, recall@20 ≈ 0.71.  
  - 목표(예: recall@10 ≥ 0.50)에 근접하지만 아직 개선 여지가 있다.  
  - Golden set·ontology 정렬이 안 맞으면 unmapped skill 때문에 비교 자체를 보류한다(golden_set_alignment.md).

- **Rerank**  
  - NDCG@5, MRR delta 등에서 **추가 지연 대비 품질 이득이 불명확**해, 현재는 기본 경로에서 제외하고 optional/gate로만 둔다.  
  - 따라서 “rerank 수치”는 있지만, 그 수치가 “기본 경로에 넣을 만큼 좋다”는 결론을 주지 않아서 “낮게 본다”고 해석할 수 있다.

- **Agent (설명 품질)**  
  - **Groundedness가 낮았던 이유** (short_eval_status 정리):  
    - 설명이 너무 일반적(“strong experience”, “technical expertise”)  
    - Groundedness 휴리스틱이 **실제 스킬/증거 토큰 overlap**을 요구하는데, 예전 설명은 소수 도구만 언급하고 후보 evidence 토큰(예: ec2, vpc, cloudwatch)은 빠짐  
    - Explanation presence 자체가 일부만 채워져서(agent-evaluated 행만 설명 있음) 집계가 낮아짐  
  - **대응:** prompt v4에서 evidence-token 중심 템플릿(Matched required skills, Candidate evidence tokens, missing/weaker skills 등)을 쓰고, ontology와 맞춘 증거를 노출하도록 했다.  
  - **LLM-as-Judge**는 최근에 실제 생성 경로가 생겼고, 아직 subset·early-stage 수준이라 “production KPI”로 쓰기에는 이르다.

- **Short-eval 샘플 수**  
  - 빠른 검증을 위해 **6개 쿼리** 등 소규모 subset으로 돌리기 때문에, “수치가 적다”는 것은 “실험 수/데이터 포인트가 적다”는 의미도 된다.  
  - Full golden 50에 대한 상시 full run, 직군별 slice 분석은 백로그로 명시되어 있다.

### 3.4 Eval 관점 요약

| 질문 | 답변 |
|------|------|
| **Eval은 어떤 관점에서 하나?** | Stage별( retrieval → rerank → agent ), 재현 가능한 golden 기반, 리뷰어가 신뢰할 수 있는 증거(품질·성능·비용·신뢰성·공정성)를 만드는 관점이다. |
| **왜 (일부) 수치가 적어 보이나?** | (1) Agent 설명 품질(groundedness)은 예전에 일반적 설명·evidence 부족으로 낮았고, prompt v4·evidence-token 정렬로 개선 중이다. (2) Rerank는 수치상 기본 경로 채택이 타당하지 않아 꺼둔 상태다. (3) Short-eval은 샘플 수를 적게 써서 빠른 검증에 초점을 둔다. |
| **무엇을 우선 보나?** | Retrieval recall을 1순위로 두고, 그 다음에 rerank/agent의 증분 이득과 비용을 본다. |

상세 메트릭·아티팩트·체크리스트는 [evaluation_plan.md](../evaluation/evaluation_plan.md), [short_eval_status_2026-03-17.md](../evaluation/short_eval_status_2026-03-17.md), [llm_judge_design.md](../evaluation/llm_judge_design.md) 참고.

---

## 4. 평가 스택 선택 근거 (DeepEval, Confident AI, sdk_handoff bypass)

**목적:** “DeepEval 쓰나?”, “Confident AI 왜 안 쓰나?”, “eval에서 sdk_handoff 왜 끄나?”에 대한 방어 논리가 아니라 **선택 이유**를 명시한다.

### 4.1 DeepEval

| 사실 | 설명 |
|------|------|
| **문서/requirements** | `requirements.txt`에 `deepeval` 포함, Key Design Decisions·system_architecture에서 “DeepEval 기반 평가”로 기술. |
| **구현** | **코드에서 deepeval 라이브러리를 import하거나 호출하지 않음.** recall@k, MRR, NDCG, groundedness 휴리스틱, LLM-as-Judge 연동 등은 `src/eval/metrics.py`·`eval_runner.py`에서 자체 구현. |
| **정리** | 평가 **방식**(golden set, stage별 메트릭, LLM-as-Judge)은 DeepEval과 정렬되어 있으나, **실제 의존은 없음**. 향후 DeepEval API를 도입할지는 선택 사항. |

### 4.2 Confident AI

| 사실 | 설명 |
|------|------|
| **환경 변수** | `.env.example`에 `CONFIDENT_API_KEY`, `CONFIDENT_REGION` 존재. |
| **구현** | **백엔드에서 Confident AI API를 호출하는 코드 없음.** Guardrails는 `fairness.py`, `jd_guardrails.py` 등 자체 구현으로만 동작. |
| **미사용 이유** | Confident AI(서비스/제품)는 현재 **미통합** 상태. 사용 불가(서비스 중단·접근 제한 등)였거나, 우선순위상 자체 guardrails로 충분하다고 판단했을 수 있음. 문서상 “사용 불가이기 때문에”라고 단정할 근거는 없고, “미통합·미사용”으로 기술함. |

### 4.3 Eval에서 sdk_handoff를 쓰지 않는 이유 (방어 논리 아님)

| 사실 | 설명 |
|------|------|
| **문제** | **Agents SDK handoff 경로가 불안정**했음. short_eval에서 관측된 현상: `ScorePackOutput`/negotiation **스키마 불일치**, handoff 구간 **event-loop·연결 불안정**, long idle tails로 eval run이 끝까지 완료되지 않음. |
| **결과** | 에이전트 **품질**을 평가하려면 eval이 안정적으로 끝나야 하는데, SDK handoff를 쓰면 run 자체가 실패하거나 타임아웃에 걸려 품질 지표를 수집할 수 없었음. |
| **대응** | Eval 모드에서는 **sdk_handoff를 사용하지 않고** `live_json → heuristic` 경로만 사용. “Agentic AI 전체가 불안정하다”가 아니라 **특정 런타임 경로(SDK handoff)가 불안정**하므로, 그 경로가 검증될 때까지 eval에서는 bypass하는 것이다. |
| **문서** | [short_eval_status_2026-03-17.md](../evaluation/short_eval_status_2026-03-17.md), [RESULTS.md](../eval/RESULTS.md): “eval-only SDK bypass until Agents SDK handoff is proven stable”, “eval에서는 sdk_handoff를 다시 켜지 않습니다.” |

정리: **Confident AI 미사용**은 “사용 불가” 단정 없이 미통합·미사용으로 두고, **sdk_handoff bypass**는 Agents SDK handoff 경로의 불안정(스키마·이벤트 루프) 때문에 eval 안정성을 위해 선택한 것으로 명시한다.

---

## 5. 요약 표

| 주제 | 한 줄 요약 |
|------|------------|
| **왜 온톨로지?** | 에이전트가 “무엇을 평가할지”와 “어떤 용어로 말할지”를 하나의 체계로 쓰게 해서 Agentic AI와 맞고, transferable skill·도구·유지보수까지 한 번에 맞춘다. |
| **장기 비용** | Deterministic-first + `agent_eval_top_n` + 캐시로 고비용 LLM을 꼭 필요한 곳에만 써서, 에이전트에 의한 작업 처리가 비용 대비 효과를 극대화한다. |
| **Eval 수치·관점** | Stage별·재현 가능·리뷰어 대면으로 평가하며; 일부 수치가 낮은 이유는 설명 품질(groundedness)·rerank ROI·short-eval 샘플 수 등으로 설명되며, retrieval-first로 우선순위를 둔다. |
| **DeepEval** | 문서·requirements에는 있으나 코드에서 라이브러리 미호출; 메트릭은 자체 구현. |
| **Confident AI** | env만 있고 미통합; guardrails는 자체 구현. |
| **sdk_handoff bypass** | Agents SDK handoff 경로(스키마·event-loop) 불안정으로 eval이 완료되지 않아, eval에서는 live_json→heuristic만 사용. |
