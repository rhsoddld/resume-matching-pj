# Scoring Design (Deterministic Layer)

## Fixed Pipeline Context

Embedding (`text-embedding-3-small`)
-> Milvus vector search
-> BM25 skill search
-> Hybrid merge
-> Top 30 candidates
-> Feature extraction
-> Deterministic scoring
-> Top 10
-> LLM rerank (`gpt-4o-mini`)
-> Top 5 candidates

This pipeline is fixed unless explicitly requested otherwise.

## Retrieval vs Scoring vs Rerank

Vector similarity and BM25 are used for recall-oriented candidate retrieval.

A deterministic feature-based scoring layer performs explainable initial ranking using
semantic similarity, ontology-aware skill overlap, and experience fit.

Skill overlap prioritizes core skill matches derived from the skill ontology
and uses expanded taxonomy relationships for partial matches.

An LLM reranker then refines the ranking and generates reasoning for the final candidate recommendations.

## Ontology-Aware Skill Overlap

`skill_overlap` uses the following candidate fields:
- `parsed.core_skills`
- `parsed.expanded_skills`
- `parsed.normalized_skills`

The following fields are intentionally excluded from scoring:
- `parsed.capability_phrases`
- `parsed.role_candidates`

### Scoring Rule

When `core_skills` exists:

```text
skill_overlap_score =
0.6 * core_overlap
+ 0.3 * expanded_overlap
+ 0.1 * normalized_overlap
```

When `core_skills` is empty:

```text
skill_overlap_score =
0.7 * normalized_overlap
+ 0.3 * expanded_overlap
```

### Explainability Breakdown

`skill_overlap` should expose a deterministic breakdown:

```json
{
  "core_overlap": 0.5,
  "expanded_overlap": 0.2,
  "normalized_overlap": 0.1
}
```

## Fixed Overall Formula (Unchanged)

The top-level deterministic scoring formula remains unchanged:

```text
score =
0.42 * semantic_similarity
+ 0.33 * skill_overlap
+ 0.18 * experience_fit
+ 0.07 * seniority_fit
+ category_fit
```

Current implementation notes:
- `score`는 최종 랭킹 결정용 deterministic 점수로 사용됨.
- `category_fit`: Sneha/Suri 카테고리 매칭 시 0.03 보너스 반영 중.
- `education_fit` 및 `recency_fit`: 설계상 확장 영역이며 현재 미구현.
