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
| Agent 지연/UX | 병렬 후보 평가 + SSE 스트리밍 + agent_eval_top_n | 동기 단일 응답만 사용 | 멀티에이전트 통신으로 인한 장시간 처리 완화, 체감 대기·진행 표시 개선 | 스트리밍 이벤트 순서·에러 처리 복잡 | thought_process/candidate 순차 노출, ThreadPoolExecutor 병렬 |

## Agent 설계 트레이드오프: 지연 vs 품질·UX

### 문제: OpenAI SDK 기반 멀티에이전트 구조의 장시간 처리

| 항목 | 설명 |
|------|------|
| **원인** | OpenAI Agents SDK 경로에서는 후보 1명당 **다중 에이전트가 순차·handoff** 로 동작한다. Skill → Experience → Technical → Culture(각각 LLM 호출) → ScorePack → Recruiter → HiringManager → WeightNegotiation 순으로 통신이 이어져, 구조적으로 **에이전트 간 통신(멀티에이전트 통신) 횟수가 많고 총 처리 시간이 길어짐**. |
| **영향** | 사용자 관점에서 매칭 결과까지 대기 시간이 길어지고, 동기 API만 사용할 경우 빈 화면이 유지되는 UX 이슈가 발생할 수 있음. |

### 대응책

| 대응 | 설명 | 구현 위치 |
|------|------|-----------|
| **후보 단위 병렬 처리** | Top-K shortlist 내 후보들을 **동시에** 평가한다. 에이전트 런타임은 후보당 순차이지만, **후보들끼리는 ThreadPoolExecutor로 병렬** 실행해 전체 소요 시간을 줄인다. | `matching_service.stream_match_jobs` → `ThreadPoolExecutor(max_workers=max(1, min(10, len(shortlisted_hits))))`, `matching/evaluation.py` |
| **스트리밍(SSE) 표시** | 결과를 한 번에 기다리지 않고 **Server-Sent Events**로 순차 전달한다. query profile → session_id → **thought_process**(에이전트 진행 상황) → **candidate**(완료되는 후보부터) → fairness → done 순으로 스트리밍하여, **진행 상황과 결과가 점진적으로 표시**되도록 해 UX를 개선한다. | `POST /api/jobs/match/stream`, `stream_match_jobs`, `on_event` → `thought_process` / `candidate` 이벤트, 프론트 `streamMatchCandidates`, `App.tsx` |
| **agent_eval_top_n 상한** | 에이전트 평가를 받는 후보 수를 상한으로 제한한다. 상위 N명만 풀 에이전트 경로를 타고, 나머지는 deterministic 점수만 사용해 **지연·비용**을 제어한다. | `agent_eval_top_n` 설정, `select_agent_eval_indices` |
| **live_json / heuristic fallback** | SDK 경로 실패 또는 비활성 시 **단일 structured call** 기반 `live_json` 또는 규칙 기반 `heuristic`으로 전환한다. 멀티에이전트 통신 수를 줄이거나 제거해 **지연 완화·안정성**을 확보한다. | `AgentOrchestrationService._execute`, `live_runner`, `heuristics` |

### 요약

- **트레이드오프**: SDK 기반 멀티에이전트 설계 → 에이전트 간 통신 다발 → **장시간 처리**.
- **완화**: **병렬 처리**(후보 단위) + **스트리밍 표시**(profile / thought_process / candidate 순차 노출)로 체감 대기 시간과 UX를 개선하고, **agent_eval_top_n** 및 **live_json/heuristic** fallback으로 지연·비용·장애를 제어한다.

*구현 상세: [multi_agent_pipeline.md](../agents/multi_agent_pipeline.md), [candidate_retrieval_flow.md](../data-flow/candidate_retrieval_flow.md), [system_architecture.md](../architecture/system_architecture.md) § Multi-Agent Evaluation.*

## Scoring Tradeoffs (Legacy Scoring Design)

### Retrieval fusion
```text
fusion_score =
  0.48 * vector_score
+ 0.37 * keyword_score
+ 0.15 * metadata_score
```

### Skill overlap (skill_overlap)
- JD 쪽 스킬은 **상위 10개만** 분모에 사용 (분모 캡).
- core 있음: `0.45×core_overlap + 0.35×expanded_overlap + 0.2×normalized_overlap`
- core 없음: `0.5×normalized_overlap + 0.5×expanded_overlap`
- 에이전트 평가가 있으면: 위 값과 에이전트 스킬 점수를 **50:50** 블렌딩한 값을 skill_overlap으로 사용.

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
