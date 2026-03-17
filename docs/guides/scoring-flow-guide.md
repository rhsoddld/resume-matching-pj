# 스코어링 전체 흐름 가이드

**목적:** "몇 명을 필터해서 어떤 계산을 하는지"를 **처음부터 끝까지** 한 번에 이해할 수 있도록 단계별로 정리합니다.  
스코어링이 이 시스템에서 가장 복잡한 부분이므로, **인원 수**와 **계산 공식**을 명확히 적었습니다.

---

## 1. 한눈에 보는 전체 파이프라인

사용자가 **"상위 10명(top_k=10) 추천해줘"**라고 요청했다고 가정합니다.

```
[전체 DB] → Retrieval(N명) → Enrichment(메타 필터) → Shortlist(최대 top_k명) → 스코어 계산 → 최종 정렬
                ↑                    ↑                        ↑
           예: 10~50명          조건 미충족 탈락           그중 상위 10명
                                                      → 이 중 상위 5명만 에이전트 평가
                                                      → 나머지 5명은 규칙 기반 점수만
```

| 단계 | 담당 모듈 | 인원(예시, top_k=10) | 하는 일 |
|------|-----------|------------------------|---------|
| 1. Retrieval | `HybridRetriever` | **N명** (기본 10명, rerank 켜면 더 많이) | 벡터+키워드+메타데이터로 후보 검색 |
| 2. Enrichment | `candidate_enricher` | **N명 → M명** (M ≤ N) | Mongo 문서 결합 + 경력연차/학력/지역/산업 필터 적용 → 조건 안 맞으면 제외 |
| 3. Shortlist | `_shortlist_candidates` | **최대 top_k명(10명)** | rerank 게이트 통과 시 Cross-Encoder rerank 후 상위 10명, 아니면 fusion 순서 그대로 상위 10명 |
| 4. 스코어 계산 | `_score_candidates` + `build_match_candidate` | **10명 전원** | 10명 모두 **deterministic 점수** 계산 → 그중 **상위 5명(agent_eval_top_n)**만 에이전트 평가 → **최종 rank_score** 산출 |
| 5. 정렬·응답 | `MatchingService` | **10명** | 에이전트 평가 받은 사람 우선, 동일하면 `score` 내림차순 → `JobMatchResponse` 반환 |

---

## 2. 단계별 상세: 몇 명이 남고, 어떤 계산을 하는가

### 2.1 Retrieval — "몇 명을 가져올까"

- **목표 인원:** `retrieval_top_n`
  - rerank 비활성: `retrieval_top_n = top_k` (예: 10)
  - rerank 활성: `retrieval_top_n = max(top_k, rerank_pool_n)`  
    - `rerank_pool_n = max(top_k, min(rerank_top_n, rerank_gate_max_top_n))`  
    - 기본 설정: `rerank_top_n=50`, `rerank_gate_max_top_n=8` → top_k=10이면 **10명** 검색
- **하는 일:**
  1. **Mongo 키워드 검색** (항상): JD에서 뽑은 lexical query로 검색 → `keyword_hits`
  2. **Milvus 벡터 검색** (가능 시): JD 임베딩으로 유사도 검색 → `vector_hits`
  3. **합치기:** 동일 후보는 merge, 점수는 **fusion** 한 번에 합산
- **Fusion 공식 (Retrieval 단계):**
  ```
  fusion_score = (vector_weight × vector_score) + (keyword_weight × keyword_score) + (metadata_weight × metadata_score)
  ```
  - 기본 가중치: **vector 0.48, keyword 0.37, metadata 0.15**
  - `vector_score`: Milvus 유사도 [-1,1]을 [0,1]로 정규화
  - `keyword_score`: JD 필수 스킬·용어와 후보 스킬 겹침 비율
  - `metadata_score`: category/industry/경력연차/seniority 일치 여부
- **결과:** `fusion_score` 기준 정렬된 **N개의 hit** (각 hit에 `score`=원시 벡터점수, `fusion_score` 보관)

---

### 2.2 Enrichment — "메타 필터로 누구를 빼는가"

- **입력:** Retrieval에서 나온 **N명** (hit 리스트)
- **하는 일:**
  - 각 hit에 대해 Mongo에서 **전체 후보 문서** 조회
  - 아래 조건 하나라도 안 맞으면 **제외** (enriched 리스트에 안 넣음)
    - `min_experience_years`: 후보 경력 연차가 미만이면 제외
    - `education`: 학력 조건 불일치 시 제외
    - `region`: 지역/원격 조건 불일치 시 제외
    - `industry`: 산업 조건 불일치 시 제외
- **결과:** **(hit, candidate_doc)** 쌍 리스트 **M명** (M ≤ N). 이후 단계는 이 M명만 사용.

---

### 2.3 Shortlist — "최종 스코어링 대상 몇 명으로 자를까"

- **목표:** **최대 top_k명** (예: 10명)만 남겨서, 이들만 스코어 계산·에이전트 평가 대상으로 둠.
- **하는 일:**
  1. **Rerank 게이트** (`should_apply_rerank`):
     - rerank 비활성 또는 게이트 불통과 → `enriched_hits`를 **fusion_score 순**으로 정렬한 뒤 **앞에서 top_k명** 잘라서 shortlist
     - 게이트 통과 시 → `resolve_rerank_pool_n(top_k)`만큼만(예: 10명) Cross-Encoder rerank 호출 → rerank 점수와 기존 fusion을 **0.75×rerank + 0.25×fusion**으로 블렌딩 후, **상위 top_k명**을 shortlist
  2. **Shortlist 결과:** 항상 **최대 top_k명** (10명). 이 10명이 `shortlisted_hits`로 스코어 단계에 넘어감.

---

### 2.4 스코어 계산 — "10명 전원 점수 내기 + 상위 5명만 에이전트"

여기가 **가장 복잡한 부분**입니다. 두 가지 점수가 순서대로 나옵니다.

#### Step A: 10명 전원 — Deterministic 점수 (규칙 기반)

**모든 shortlist 후보(10명)**에 대해 먼저 **deterministic match score**를 한 번에 계산합니다.

- **입력 (hit + candidate_doc):**
  - `hit["score"]`: retrieval 단계의 **원시 벡터 유사도** (deterministic 공식의 semantic 입력)
  - `hit`의 `experience_years`, `seniority_level`, `category` 등
  - `candidate_doc["parsed"]`: 스킬·경력 등
  - `job_profile`: required_skills, expanded_skills, required_experience_years, preferred_seniority 등

- **1) 스킬 겹침 (skill_overlap)** — `scoring_service.compute_skill_overlap`
  - 후보의 core_skills / expanded_skills / normalized_skills와  
    JD의 required_skills·expanded_skills를 **soft overlap**으로 비교
  - **분모 캡:** JD 스킬은 상위 **최대 10개**만 사용 (과다 시 점수 과도 하락 방지)
  - core 있으면: `0.45×core_overlap + 0.35×expanded_overlap + 0.2×normalized_overlap`
  - core 없으면: `0.5×normalized_overlap + 0.5×expanded_overlap`
  - **에이전트 있을 때:** 위 값과 에이전트 스킬 점수를 50:50 블렌딩한 값을 최종 skill_overlap으로 사용 (매칭 시점 판단 반영)

- **2) Deterministic match score** — `scoring_service.compute_deterministic_match_score`
  ```
  semantic_similarity = (raw_similarity + 1) / 2   # 벡터 점수 [0,1]로
  experience_fit      = 경력 연차 적합도 (요구연차 대비, 과다 시 소폭 페널티)
  seniority_fit      = 시니어리티 레벨 거리 기반 0~1
  category_fit       = category 일치 시 category_bonus, 아니면 0

  final_score = w_sem×semantic_similarity + w_skill×skill_overlap + w_exp×experience_fit + w_seniority×seniority_fit + category_fit
  ```
  - \(w_\*\) 및 `category_bonus`는 **deterministic scoring policy(versioned)** 로 관리한다: `src/backend/services/scoring_policies.py` (기본 v1).
  - 위 값을 0~1로 clip한 것이 **deterministic_score**.

이 **deterministic_score**로 10명을 **정렬**한 뒤, **상위 agent_eval_top_n명(기본 5명)**만 다음 단계(에이전트)로 넘깁니다.

#### Step B: 상위 5명 — 에이전트 평가 + Agent 가중 점수

- **대상:** Step A에서 **점수 높은 순 5명**만 (`select_agent_eval_indices`).
- **하는 일 (1명당):**
  1. **4개 에이전트** 실행: Skill / Experience / Technical / Culture → 각 0~1 점수 + evidence
  2. **Recruiter vs Hiring Manager** 가중치 제안 → **WeightNegotiation**으로 최종 가중치 결정 (skill, experience, technical, culture 합=1.0)
  3. **Agent 가중 점수** 계산 — `compute_weighted_score`:
     ```
     agent_weighted_score = skill×w_skill + experience×w_exp + technical×w_tech + culture×w_culture
     ```

#### Step C: 10명 전원 — 최종 rank_score (노출용 점수)

**10명 모두**에 대해 `build_match_candidate` 안에서 **최종 노출 점수**를 냅니다.

- **에이전트 평가 받은 5명:**
  ```
  rank_score = rank_deterministic_weight × deterministic_score + rank_agent_weight × agent_weighted_score
  rank_score = rank_score × (1 - must_have_penalty)   # 0~1 클립
  ```
  - `must_have_penalty`: JD must-have 스킬 미충족 시 최대 0.12까지 감점 (adjacent 스킬로 일부 상쇄 가능).

- **에이전트 평가 안 받은 5명 (outside agent eval scope):**
  ```
  rank_score = deterministic_score
  rank_score = rank_score × (1 - must_have_penalty)
  ```

즉, **같은 deterministic만 써도**, 에이전트를 탄 5명은 **deterministic 30% + agent 70%**로 더 세밀하게 점수가 나오고, 나머지 5명은 **deterministic만(그대로)** 사용합니다.

---

### 2.5 정렬·응답

- **정렬 키:**  
  1) 에이전트 평가 적용된 사람 먼저, 2) 그 다음 `score`(rank_score) 내림차순.
- **Fairness guardrails** 적용 후 `JobMatchResponse`로 반환 (matches 리스트가 곧 “추천 후보 10명” + 각자 score·설명).

---

## 3. 수식만 모아 보기

| 단계 | 수식 요약 |
|------|-----------|
| **Skill overlap (표시·deterministic 입력)** | JD 스킬 상위 10개만 분모 사용. core 있음: `0.45×core + 0.35×expanded + 0.2×normalized` / core 없음: `0.5×normalized + 0.5×expanded`. 에이전트 O면 위 값과 agent 스킬 점수 50:50 블렌딩. |
| **Retrieval fusion** | `fusion = 0.48×vector + 0.37×keyword + 0.15×metadata` |
| **Deterministic score** | `w_sem×semantic + w_skill×skill_overlap + w_exp×experience_fit + w_seniority×seniority_fit + category_bonus(if matched)` (policy v1: `scoring_policies.py`) |
| **Agent weighted score** | `skill×w_s + experience×w_e + technical×w_t + culture×w_c` (가중치 합=1, 협상으로 결정) |
| **최종 rank_score (에이전트 O)** | `(rank_deterministic_weight×deterministic + rank_agent_weight×agent) × (1 - must_have_penalty)` |
| **최종 rank_score (에이전트 X)** | `deterministic × (1 - must_have_penalty)` |

---

## 4. 설정으로 바꿀 수 있는 숫자 (요약)

| 설정 | 기본값 | 의미 |
|------|--------|------|
| `top_k` | (요청 파라미터, 예: 10) | 최종 반환 인원 + shortlist 크기 |
| `retrieval_top_n` | top_k 또는 rerank 시 더 큼 | 1단계에서 가져오는 최대 인원 |
| `agent_eval_top_n` | 5 | 에이전트 평가할 상위 인원 (나머지는 deterministic만) |
| `rerank_top_n` / `rerank_gate_max_top_n` | 50 / 8 | rerank 풀 크기 상한 |
| `token_budget_enabled` | False | True면 agent_eval_top_n이 토큰 예산에 맞게 줄어들 수 있음 |
| `rank_deterministic_weight` / `rank_agent_weight` | 0.30 / 0.70 | 최종 rank_score에서 deterministic vs agent_weighted 블렌딩 비율 (env/Settings로 관리) |
| `fallback_recruiter_weights` / `fallback_hiring_manager_weights` | (문서 기본값) | LLM 협상 실패 시 fallback 협상 가중치(Recruiter/HM) 및 조정폭 (env/Settings로 관리) |
| `deterministic scoring policy` | v1 | deterministic 내부 가중치/보너스는 env가 아니라 **repo-managed 정책 버전**으로 관리 (`scoring_policies.py`) |

---

## 5. 관련 코드 위치

| 내용 | 파일 |
|------|------|
| 파이프라인 오케스트레이션 (retrieval → enrich → shortlist → score) | `src/backend/services/matching_service.py` |
| Retrieval fusion, 인원 수 | `src/backend/services/hybrid_retriever.py`, `src/backend/services/matching/rerank_policy.py` |
| Enrichment·메타 필터 | `src/backend/services/candidate_enricher.py` |
| Shortlist·rerank 게이트 | `src/backend/services/matching_service.py` (`_shortlist_candidates`), `src/backend/services/matching/rerank_policy.py` |
| Deterministic·skill overlap·최종 blend | `src/backend/services/scoring_service.py`, `src/backend/services/scoring_policies.py`, `src/backend/services/match_result_builder.py` |
| 에이전트 4개 + 가중치 협상 + agent_weighted_score | `src/backend/agents/runtime/service.py`, `src/backend/agents/runtime/helpers.py` |
| 에이전트 평가할 인덱스 선택 | `src/backend/services/matching/evaluation.py` (`select_agent_eval_indices`) |

이 문서만 따라가면 **“몇 명을 필터하고, 어떤 계산으로 점수를 내서 최종 10명을 주는지”**를 처음부터 끝까지 추적할 수 있습니다.
