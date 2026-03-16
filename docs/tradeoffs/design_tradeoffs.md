# Design Tradeoffs

이 문서는 기존 `DESIGN_DECISION_MATRIX.md` + `KNOWN_TRADEOFFS.md` + `scoring_design.md`의 핵심 결정을 통합한다.

## Decision Matrix (Restored)

| Decision | Chosen | Alternatives | Why Chosen | Tradeoff | Mitigation |
|---|---|---|---|---|---|
| Ingestion parsing | Rule-based deterministic | Generative parsing | 비용/재현성/운영 안정성 | 비정형 이력서의 필드 누락 가능성 | raw text 유지 + matching 단계 fallback |
| Data store | MongoDB + Milvus dual store | Single store | 문서 모델 유연성 + 벡터 검색 성능 | 동기화 복잡도 증가 | hash 기반 증분 upsert |
| Retrieval strategy | Hybrid (vector + lexical + metadata) | semantic-only, keyword-only | recall/precision 균형 | 파라미터 튜닝 필요 | fusion weight 실험 자동화 |
| Ranking baseline | Deterministic-first + optional agent blend | agent-only scoring | 회귀/설명 가능성 우수 | 의미적 뉘앙스 손실 가능 | agent score를 선택적으로 결합 |
| Rerank policy | Gated optional rerank | always-on rerank | 비용/지연 대비 효과 불확실 | 복잡도 증가 | gate + timeout + fallback |
| Embedding model | `text-embedding-3-small` | larger embedding | 비용/반복 인덱싱 속도 우수 | edge semantic case 손실 가능 | env 설정으로 업그레이드 가능 |
| Agent runtime | `sdk_handoff -> live_json -> heuristic` | single-path runtime | 장애 내성 및 서비스 연속성 | 모드별 동작 이해 필요 | mode/fallback 메타데이터 노출 |

## Scoring Tradeoffs (Legacy Scoring Design)

### Retrieval fusion
```text
fusion_score =
  0.55 * vector_score
+ 0.30 * keyword_score
+ 0.15 * metadata_score
```

### Deterministic score
```text
deterministic_score =
  0.42 * semantic_similarity
+ 0.33 * skill_overlap
+ 0.18 * experience_fit
+ 0.07 * seniority_fit
+ category_fit_bonus
```

### Final hybrid score
```text
rank_score_before_penalty =
  0.30 * deterministic_score
+ 0.70 * agent_weighted_score

final_score = rank_score_before_penalty * (1 - must_have_penalty)
```

참고:
- 코드 기준 가중치는 `compute_final_ranking_score` 기본값을 따른다.
- 응답 `rank_policy` 문자열은 레거시 라벨일 수 있으므로 운영 판단은 실제 계산식을 기준으로 한다.

## Known Risk Notes

1. rerank는 일부 실험에서 latency 증가 대비 품질 개선이 제한적이었다.
2. fair ranking은 culture score 과대반영 위험이 있어 guardrail cap을 유지해야 한다.
3. taxonomy 확장 시 explainability는 좋아지지만 관리 비용이 늘어난다.
4. 다중 모드 fallback은 안정적이지만 운영 관측 항목이 많아진다.

## Backlog

1. 직군별 fusion weight 자동 튜닝
2. must-have penalty 민감도 실험
3. rerank ROI(A/B + rollback) 운영 문서화
4. fairness drift 감지 자동화
