# Scoring Design

## 1. Current Ranking Pipeline

```text
JD
-> Deterministic Query Understanding
-> (optional) constrained LLM fallback when low confidence / high unknown ratio
-> ontology + alias normalization
-> Hybrid Retrieval (vector + keyword + metadata fusion)
-> Top-50 retrieval set
-> (optional) Cross-Encoder Rerank
-> Top-K shortlist
-> Deterministic score computation
-> Agent score pack (skill/experience/technical/culture)
-> Hybrid rank score (deterministic + agent weighted)
-> Must-have penalty
-> Explainable output
```

현재 랭킹 경로에는 LLM rerank 단계가 없다.  
LLM은 저신뢰 query understanding fallback과 optional rerank 단계에서만 제한적으로 사용한다.

## 2. Query Understanding Quality Gate

Fallback trigger:

```text
confidence < QUERY_FALLBACK_CONFIDENCE_THRESHOLD
or
unknown_ratio > QUERY_FALLBACK_UNKNOWN_RATIO_THRESHOLD
```

기본값:

- `QUERY_FALLBACK_CONFIDENCE_THRESHOLD=0.62`
- `QUERY_FALLBACK_UNKNOWN_RATIO_THRESHOLD=0.55`

Fallback을 적용하더라도 최종 query profile은 ontology/alias normalization을 반드시 다시 거친 결과만 사용한다.

## 3. Retrieval Fusion Score

Hybrid retrieval은 후보별로 아래 신호를 결합한다.

- `vector_score`: Milvus similarity 정규화 값
- `keyword_score`: normalized/core/expanded skill + summary overlap
- `metadata_score`: category / experience / seniority 정합성

기본 결합식:

```text
fusion_score =
0.55 * vector_score
+ 0.30 * keyword_score
+ 0.15 * metadata_score
```

`fusion_score`는 shortlist 정렬 기준이며, 이후 deterministic scoring/agent scoring의 입력으로 사용된다.

### 3-1. Optional Cross-Encoder Rerank

`RERANK_ENABLED=true`일 때만 동작한다.

```text
retrieval_top_n = max(top_k, RERANK_TOP_N)
hybrid_retrieval -> top-N
cross-encoder rerank -> top-K
```

기본값:

- `RERANK_ENABLED=false`
- `RERANK_TOP_N=50`
- `RERANK_MODEL=gpt-4.1-mini`

## 4. Deterministic Score

Deterministic 최상위 식:

```text
deterministic_score =
0.42 * semantic_similarity
+ 0.33 * skill_overlap
+ 0.18 * experience_fit
+ 0.07 * seniority_fit
+ category_fit
```

`category_fit`은 카테고리 매칭 시 `+0.03` 보너스다.

### 4-1. Ontology-aware Skill Overlap

Candidate skill source:

- `parsed.core_skills`
- `parsed.expanded_skills`
- `parsed.normalized_skills`

식:

```text
if candidate_core exists:
  skill_overlap = 0.6 * core_overlap + 0.3 * expanded_overlap + 0.1 * normalized_overlap
else:
  skill_overlap = 0.7 * normalized_overlap + 0.3 * expanded_overlap
```

Breakdown output:

```json
{
  "core_overlap": 0.5,
  "expanded_overlap": 0.2,
  "normalized_overlap": 0.1
}
```

## 5. Agent-augmented Rank Score

Agent weighted score가 있는 경우:

```text
rank_score_before_penalty =
0.55 * deterministic_score
+ 0.45 * agent_weighted_score
```

Agent weighted score가 없는 경우:

```text
rank_score_before_penalty = deterministic_score
```

`rank_policy`:

- `hybrid(deterministic:0.55,agent:0.45,must-have-penalty:max0.25)`
- `deterministic-only(must-have-penalty:max0.25)`

## 6. Must-have Penalty

`job_profile.skill_signals`에서 `must have`로 분류된 skill에 대해 match rate를 계산한다.

```text
must_have_match_rate = matched_must_have / total_must_have
must_have_penalty = min(0.25, (1 - must_have_match_rate) * 0.25)
final_score = rank_score_before_penalty * (1 - must_have_penalty)
```

결과 payload는 아래를 포함한다.

- `must_have_match_rate`
- `must_have_penalty`

## 7. Explainability Output Fields

결과별 출력 필드:

- `score`
- `score_detail.semantic_similarity/experience_fit/seniority_fit/category_fit`
- `score_detail.retrieval_fusion/retrieval_keyword/retrieval_metadata`
- `score_detail.must_have_match_rate/must_have_penalty`
- `skill_overlap_detail`
- `relevant_experience`
- `possible_gaps`
- `weighting_summary`

Query profile explainability:

- `confidence`
- `signal_quality.unknown_ratio`
- `fallback_used/fallback_reason/fallback_rationale/fallback_trigger`

## 8. Tuning Backlog

- 직군별 retrieval fusion weight calibration
- must-have penalty 상한(`0.25`) 민감도 실험
- fallback 임계치와 precision/recall trade-off 검증
- fairness metric과 score drift 모니터링 추가
