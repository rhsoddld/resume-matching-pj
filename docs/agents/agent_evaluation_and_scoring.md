# Agent 평가 로직 및 스코어링 관점

**목적:** 에이전트가 **무엇을 평가하는지**, **어떤 관점으로 점수를 내는지**, **최종 랭킹 점수가 어떻게 합성되는지**를 한 문서에 정리한다.

**관련 문서:** [multi_agent_pipeline.md](./multi_agent_pipeline.md), [ADR-004](../adr/ADR-004-agent-orchestration.md), [design/rationale-ontology-eval-cost.md](../design/rationale-ontology-eval-cost.md)

---

## 1. 전체 흐름 요약

1. **4개 차원 에이전트**가 각각 후보를 평가해 0~1 점수와 evidence/rationale를 낸다.  
   → Skill, Experience, Technical, Culture
2. **ScorePack**이 네 출력을 한 덩어리로 정리하고, 설명을 evidence-token 중심으로 맞춘다.
3. **Recruiter / Hiring Manager**가 각각 가중치 제안(proposal)을 내고, **WeightNegotiation**이 최종 가중치를 정한다.
4. **가중 합**으로 `agent_weighted_score`를 계산하고, deterministic 점수와 **blend(rank_deterministic_weight / rank_agent_weight)** 해서 최종 `rank_score`를 만든다.
5. 에이전트 실패 시 **heuristic fallback**으로 동일 스키마의 점수·설명을 규칙 기반으로 채운다.

---

## 2. 4개 차원: 무엇을 보고, 어떻게 점수 내는가

4개 에이전트는 공통으로 **`search_candidate_evidence`** 도구(RAG-as-a-Tool)를 갖고 있으며, 주어진 입력만으로 판단이 어려울 때만 **선택적으로** 호출해 후보의 구조화된 이력서(parsed 필드) 안에서 추가 증거를 검색한다. 도구 사용 조건·검색 대상 컬럼·구현 위치는 [multi_agent_pipeline.md § Evidence Retrieval (RAG as a Tool)](./multi_agent_pipeline.md#evidence-retrieval-rag-as-a-tool) 참고.

### 2.1 Skill (SkillEvalAgent)

| 항목 | 내용 |
|------|------|
| **입력** | `required_skills`, `preferred_skills`, `candidate_skills` / `candidate_normalized_skills` / `candidate_core_skills` / `candidate_expanded_skills`, summary, raw_resume_text |
| **출력** | `score` (0~1), `matched_skills`, `missing_skills`, `evidence`, `rationale` |
| **관점** | JD 필수/선호 스킬과 후보 스킬 정렬도. **Transferable skill·동등 기술**을 반드시 고려(예: AWS SageMaker ↔ Vertex AI, React ↔ Vue/Angular). exact keyword 부재만으로 과도히 감점하지 않음. |
| **루브릭** | 0.8–1.0 Excellent(핵심 스킬 또는 강한 동등), 0.6–0.79 Good(transferable), 0.4–0.59 Fair, &lt;0.4 Poor. |
| **Heuristic** | `compute_skill_score(required_skills, candidate_normalized_skills)` = required와 candidate **교집합 비율** (required 기준). evidence는 이력서 문장 중 required/matched 토큰 포함 문장 추출. |

*구현:* `contracts/skill_agent.py`, `runtime/heuristics.py`, `runtime/prompts.py` (skill_eval)

### 2.2 Experience (ExperienceEvalAgent)

| 항목 | 내용 |
|------|------|
| **입력** | `required_experience_years`, `preferred_seniority`, `candidate_experience_years`, `candidate_seniority_level`, experience_items, summary, raw_resume_text |
| **출력** | `score`, `experience_fit`, `seniority_fit`, `career_trajectory`, `evidence`, `rationale` |
| **관점** | **연차보다 역할의 영향·범위·복잡도**를 우선. 연수/타이틀 exact match보다 “관련 도메인에서의 고임팩트·시니어리티 증명”을 높이 평가. |
| **루브릭** | 0.8+ 고임팩트/시니어리티 증명, 0.6+ 탄탄한 역량. |
| **Heuristic** | `experience_fit`: 요구 연차 대비 후보 연차 비율(과다 시 소폭 페널티). `seniority_fit`: preferred와 후보 seniority 일치 1.0, 불일치 0.4. `score = (experience_fit + seniority_fit) / 2`. |

*구현:* `contracts/experience_agent.py`, `runtime/heuristics.py`, `runtime/helpers.py` (compute_experience_fit, compute_seniority_fit), `runtime/prompts.py` (experience_eval)

### 2.3 Technical (TechnicalEvalAgent)

| 항목 | 내용 |
|------|------|
| **입력** | `required_stack`, `preferred_stack`, `candidate_skills`, `candidate_projects`, summary, raw_resume_text |
| **출력** | `score`, `stack_coverage`, `depth_signal`, `evidence`, `rationale` |
| **관점** | 스택 커버리지 + **아키텍처/엔지니어링 깊이**. AWS vs GCP vs Azure, PostgreSQL vs MySQL 등 **동등 스택** 인정. 정확한 툴명이 약간 다르더라도 깊이·성숙도가 있으면 0.8+ 부여. |
| **Heuristic** | `stack_coverage` = required_stack vs candidate_skills overlap 비율. `depth_signal` = stack_coverage·0.8 + vector_score·0.2. `score = (stack_coverage + depth_signal) / 2`. evidence는 required_stack + "architecture", "designed", "implemented" 등 키워드 문장. |

*구현:* `contracts/technical_agent.py`, `runtime/heuristics.py`, `runtime/prompts.py` (technical_eval)

### 2.4 Culture (CultureEvalAgent)

| 항목 | 내용 |
|------|------|
| **입력** | `target_signals`, `candidate_signals`, summary, raw_resume_text |
| **출력** | `score`, `alignment`, `risk_flags`, `evidence`, (optional) `potential_*`, `rationale` |
| **관점** | 협업/소통/소유권 등 **문화·역량 시그널**. 기본은 0.7–0.8; **명시적 부정 시그널**(불합리한 잦은 이직, 전문성 트랙 부재 등)이 있을 때만 0.6 미만. |
| **Heuristic** | category_filter와 hit category 일치 시 0.75, 불일치 시 0.6. risk_flags는 불일치 시 `["indirect-domain-signal"]`. |

*구현:* `contracts/culture_agent.py`, `runtime/heuristics.py`, `runtime/prompts.py` (culture_eval)

### 2.5 Evidence 역할 구분 (EVIDENCE RULE, prompt v5 이상)

각 에이전트의 **evidence**는 서로 겹치지 않도록 역할이 나뉜다. UI에서 Skill/Technical 등 카드가 비슷한 문장으로 나오지 않도록 프롬프트에 명시되어 있다.

| 에이전트 | evidence에 넣을 내용 | 넣지 말아야 할 내용 |
|----------|----------------------|----------------------|
| **Skill** | **정렬(alignment)**만: 어떤 필수/선호 스킬이 매칭(또는 동등)인지, 어떤 게 부족·약한지. 예: "JD required X; candidate has X (or equivalent Y)", "Missing: A, B" | 후보 기술 나열만 (Technical 역할) |
| **Technical** | **스택 커버리지·깊이**만: 어떤 도구/플랫폼을 쓰는지, breadth(영역) 또는 depth(아키텍처·규모·ownership)를 어떻게 보여주는지. 기술은 컨텍스트로 인용 | 스킬 정렬/매칭/부족 표현 (Skill 역할) |
| **Experience** | **경력·시니어리티**만: 연차, 임팩트, 스코프, 레벨. 예: "N years in X roles; senior/lead scope" | 스킬·기술 나열 (Skill/Technical 역할) |
| **Culture** | **소프트 시그널**만: 협업, 소통, 오너십, 팀워크 | 스킬·기술·연차 (다른 3개 에이전트 역할) |

- **ScorePack**: 통합 시에도 위 역할을 유지하고, Skill=정렬 / Technical=커버리지·깊이 / Experience / Culture 를 섞거나 흐리게 하지 않는다.
- **ranking_explanation**: 기술 적합성이 결정 요인일 때는 Technical 에이전트의 스택 커버리지·깊이도 인용한다.

*구현:* `runtime/prompts.py` (각 에이전트 EVIDENCE RULE, score_pack, negotiation, live_orchestrator_system)

---

## 3. 가중치 협상 (Recruiter vs Hiring Manager)

| 역할 | 관점 (프롬프트 요약) |
|------|------------------------|
| **Recruiter** | 파이프라인·time-to-hire, transferable skill 가치, 불필요한 false negative 감소. must-have 갭은 무시하지 않되, 경직된 키워드 매칭보다 넓게 본다. |
| **Hiring Manager** | 실행 품질, 기술 fit, 리스크 감소, must-have 커버리지, 기술 깊이·시니어리티 fit. Recruiter 제안을 evidence로 검토·수용/수정/도전. **기술 fit이 약할 때 culture로 보상하지 않도록** 명시. |
| **WeightNegotiation** | 두 제안을 **단순 평균이 아니라** JD 우선순위·점수 evidence로 조정. 기술 역할에서 culture 가중치가 약한 기술 fit을 보상하지 못하도록 제한. Guardrail: must_have_match_rate &lt; 0.5 → technical+experience ≥ 0.6; technical_score &lt; 0.6 → culture ≤ 0.2. |

**출력:** `recruiter`, `hiring_manager`, `final` (각각 skill/experience/technical/culture 합=1.0), `rationale`, `ranking_explanation`.

**Fallback 가중치 (heuristic):**

- Recruiter 기본값 / Hiring Manager 기본값은 **환경 변수(Settings)** 로 관리한다. (예: `FALLBACK_RECRUITER_WEIGHTS`, `FALLBACK_HIRING_MANAGER_WEIGHTS`)
- 요구 연차 ≥ threshold이면 recruiter experience boost 등 **미세 조정 폭도 Settings** 로 관리한다.
- **Final** = 두 제안의 (정규화된) 중간값.

*구현:* `contracts/weight_negotiation_agent.py`, `runtime/helpers.py` (build_fallback_weight_negotiation), `runtime/prompts.py` (recruiter_view, hiring_manager_view, negotiation)

---

## 4. 에이전트 가중 점수 → 최종 랭킹 점수

### 4.1 Agent 가중 점수 (agent_weighted_score)

에이전트 실행 후 네 차원 점수와 **협상된 최종 가중치**로 한 번에 계산한다:

```text
agent_weighted_score = skill_score * w_skill + experience_score * w_exp + technical_score * w_tech + culture_score * w_culture
```

- `w_*`는 `weight_negotiation.final` (합=1.0).
- `skill_score` 등은 각 에이전트 출력의 `score` (LLM 또는 heuristic).

*구현:* `runtime/helpers.py` (`compute_weighted_score`), `runtime/service.py` (RankingAgentInput 구성 후 `compute_weighted_score` 호출 → `RankingAgentOutput.final_score`).

### 4.2 최종 랭킹 점수 (rank_score)

```text
rank_score_before_penalty = rank_deterministic_weight * deterministic_score + rank_agent_weight * agent_weighted_score
rank_score = rank_score_before_penalty * (1 - must_have_penalty)
```

- **deterministic_score**: semantic_similarity, skill_overlap, experience_fit, seniority_fit, category_fit 등으로 계산된 0~1 점수. 내부 가중치는 **버전 관리되는 deterministic scoring policy**(`src/backend/services/scoring_policies.py`)로 관리된다. skill_overlap은 JD 스킬 상위 10개만 분모에 사용하며, 에이전트가 있으면 결정론 값과 에이전트 스킬 점수를 50:50 블렌딩한 값이 사용된다.
- **agent_weighted_score**가 없으면(에이전트 미적용) `rank_score = deterministic_score`만 사용.
- **must_have_penalty**: must-have 미충족 시 적용되는 최대 0.12 수준 페널티.

즉, **에이전트가 있으면** 랭킹은 `RANK_DETERMINISTIC_WEIGHT`/`RANK_AGENT_WEIGHT` 비율로 결정되고, must-have 미달 시 그 위에 페널티가 곱해진다.

*구현:* `services/scoring_service.py` (`compute_final_ranking_score`, `compute_deterministic_match_score`), `services/scoring_policies.py` (deterministic policy), `services/match_result_builder.py` (rank_score 계산 및 `rank_policy` 문자열).

---

## 5. 설명(Explanation) 생성 관점

- **목표:** “왜 이 점수/순위인가”를 **evidence-token 중심**으로 설명. 일반적 문구(“strong experience”)보다 **JD/후보에 나온 리터럴 스킬·증거 토큰**을 넣는다.
- **템플릿 (prompt v5 / live_orchestrator):**
  - `Matched required skills: <literal tokens>.`
  - `Candidate evidence tokens: <literal tokens>; missing or weaker skills: <literal tokens or none>.`
  - `Scores/weights: skill=..., experience=..., technical=..., culture=...; final weights skill=..., ...`
  - 기술 fit이 결정 요인일 때는 Technical 에이전트의 stack coverage/depth도 인용.
- **Heuristic 설명:** `build_grounded_ranking_explanation`이 job_profile required_skills, candidate skill_input/technical_input, 각 에이전트의 matched/missing, final_weights를 넣어 동일 구조로 문자열을 만든다.

이렇게 하면 eval의 groundedness 휴리스틱(설명 문장과 스킬/evidence 토큰 overlap)과 맞고, 리뷰어가 “어떤 스킬로 매칭/갭이 판단됐는지” 추적하기 쉽다.

*구현:* `runtime/helpers.py` (`build_grounded_ranking_explanation`), `runtime/prompts.py` (negotiation, live_orchestrator_system), `match_result_builder.py` (deterministic 경로의 `_build_deterministic_explanation`).

---

## 6. 요약 표

| 구분 | 내용 |
|------|------|
| **평가 차원** | Skill(필수/선호·transferable), Experience(영향·시니어리티), Technical(스택·깊이), Culture(협업·리스크). |
| **스코어링 관점** | 각 차원 0~1; 동등 기술/transferable 인정, 과도한 exact-match 감점 지양; culture는 부정 시그널 있을 때만 낮춤. |
| **가중치** | Recruiter(파이프라인·transferable) vs Hiring Manager(기술·must-have)·협상 → final. 기술 역할은 culture로 기술 부족 보상 금지. |
| **최종 점수** | agent_weighted = 4차원 가중합; rank_score = `rank_deterministic_weight`·deterministic + `rank_agent_weight`·agent_weighted 후 must_have_penalty 적용. |
| **설명** | Evidence-token 중심 템플릿(Matched / Candidate evidence / missing; Scores/weights). 기술 결정 시 Technical stack/depth 인용. |
| **Evidence 역할** | Skill=정렬, Technical=커버리지·깊이, Experience=연차·임팩트, Culture=협업·소통 (v5 EVIDENCE RULE). |

**코드 위치 요약**

- 계약/스키마: `src/backend/agents/contracts/` (skill_agent, experience_agent, technical_agent, culture_agent, weight_negotiation_agent, ranking_agent).
- 프롬프트: `src/backend/agents/runtime/prompts.py`.
- 휴리스틱·가중합·설명: `src/backend/agents/runtime/helpers.py`, `heuristics.py`.
- 오케스트레이션·ranking_output: `src/backend/agents/runtime/service.py`.
- deterministic policy: `src/backend/services/scoring_policies.py`
- 최종 rank_score: `src/backend/services/scoring_service.py`, `match_result_builder.py`.
