# ADR-008 Bias & Fairness Guardrails (v1)

## Decision
Implement backend v1 bias and fairness guardrails: sensitive-term scan on JD/description text, culture weight cap, must-have vs culture gate, and top-K seniority distribution check. Expose warnings via `fairness.warnings` and frontend banner.

## Why
- Governance and audit: document what is being limited and how, for recruiter and compliance review
- Reduce risk of over-relying on culture score or must-have gaps masked by high culture fit
- Sensitive-attribute keyword detection surfaces potential bias in job or candidate text for human review

## Consequences
- Guardrails are heuristic (keyword list, thresholds); tuning and fairness metrics dashboard are follow-up work
- Frontend must handle and display warnings without blocking workflow; backend returns structured warnings only

---

## 동작 방식 (How It Works)

**호출 시점:** 매칭 파이프라인에서 shortlist 점수 계산이 끝난 직후, `MatchingService._run_fairness_guardrails()`가 한 번 호출된다. (동기 API·스트리밍 API 모두 최종 결과에 `fairness` 포함.)

**설정:** `settings.fairness_guardrails_enabled=False`이면 검사 없이 `enabled=False`인 FairnessAudit만 반환한다. 개별 검사는 `fairness_sensitive_term_enabled` 등으로 켜/끌 수 있다.

### 1. 민감어 스캔 (Sensitive term scan)

| 대상 | 동작 |
|------|------|
| **JD (job_description)** | `extract_sensitive_terms(job_description)`로 정규식 매칭. 히트 시 전역 경고 1건: `sensitive_term_in_query` (severity: critical). |
| **후보** | 각 후보의 `summary` + `agent_explanation` 합친 텍스트에 동일 정규식 적용. 히트 시 해당 후보용 경고: `sensitive_term_in_candidate_explanation` (severity: warning), 후보의 `bias_warnings`에 메시지 추가. |

민감어 목록: `young`, `old`, `male`, `female`, `man`, `woman`, `pregnant`, `maternity`, `married`, `single`, 종교·인종 관련 단어, `disability` 등 (`fairness.py`의 `_SENSITIVE_TERMS`). 단어 경계(`\b`) 기준, 대소문자 무시.

### 2. Culture weight cap

- 에이전트 가중치에서 `agent_scores.weights.culture` 값을 읽는다.
- `culture_weight > fairness_max_culture_weight` (기본 0.2)이면 해당 후보에 경고: `culture_weight_over_cap`.  
- “스킬·기술 근거가 주가 되어야 하고, culture 비중이 너무 크면 안 된다”는 정책을 넘은 경우를 표시한다.

### 3. Must-have vs culture gate

다음 네 가지가 **모두** 만족될 때만 경고(`must_have_underfit_high_culture`):

- `score_detail.must_have_match_rate < fairness_min_must_have_match_rate` (기본 0.5)
- `agent_scores.confidence.culture > fairness_high_culture_confidence` (기본 0.7)
- `candidate.score >= fairness_rank_score_floor` (기본 0.7)
- 즉, “must-have는 부족한데 culture 신뢰도는 높고, 전반 점수도 꽤 높은” 후보를 짚어낸다. “핵심 요건은 부족한데 문화 적합성으로 상위에 올라온 경우 검토하라”는 의미.

### 4. Top-K seniority 분포 검사

- **조건:** (1) 상위 `top_k`명이 최소 2명 이상 (그리고 `fairness_topk_distribution_min` 이상), (2) JD에 `preferred_seniority`가 **없음**.
- **검사:** 상위 K명의 `seniority_level`을 `normalize_seniority()`로 정규화(principal/lead/senior/mid/junior/unknown)한 뒤, 한 등급이 `fairness_seniority_concentration_threshold`(기본 0.85) 이상을 차지하면 경고: `seniority_concentration_topk`.  
- JD에서 시니어리티를 요구하지 않았는데 상위가 한 등급에 몰려 있으면 “의도치 않은 시니어리티 쏠림” 가능성을 알린다.

### 출력·프론트

- **백엔드:** `JobMatchResponse.fairness`에 `FairnessAudit` (enabled, policy_version, checks_run, warnings). 각 `FairnessWarning`은 code, severity, message, candidate_ids, metrics.  
- **후보별:** 해당 후보에게 붙은 경고 메시지는 `JobMatchCandidate.bias_warnings`에 문자열 리스트로 들어 간다.  
- **프론트:** `CandidateDetailModal`이 후보의 `bias_warnings`(및 possible_gaps 등)를 모아 `BiasGuardrailBanner`에 넘기면, “Guardrail Alert” 배너로 리스트 노출.  
- **로깅:** 모든 경고 발생 시 `logger.warning("fairness_guardrail_triggered", code=..., severity=..., ...)`로 기록되어 관측·감사 추적에 사용할 수 있다.

*Implementation:* `src/backend/services/matching/fairness.py`, `src/backend/core/jd_guardrails.py`  
*Frontend:* `BiasGuardrailBanner.tsx`, `CandidateDetailModal.tsx`
