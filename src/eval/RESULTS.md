# Current Eval Conclusion

시간 기준으로 지금 가져가야 할 결론만 남깁니다.

## Final Position

1. hybrid retrieval는 유지합니다.
2. rerank는 기본 경로에서 계속 끕니다.
3. eval에서는 `sdk_handoff`를 다시 켜지 않습니다.
4. agent는 `agent_eval_top_n=4`를 현재 기준점으로 둡니다.
5. explanation은 evidence-token 스타일을 유지합니다.
6. `LLM-as-Judge`는 보조 지표로만 봅니다.

## Why

- hybrid는 hard subset에서 여전히 의미가 있습니다.
- rerank는 지연 대비 개선이 부족했습니다.
- agent runtime은 `live_json -> heuristic` 경로에서만 안정적으로 평가됐습니다.
- explanation 품질은 좋아졌지만 latency는 아직 큽니다.

## Current Best Reference Run

- judged agent run:
  - [final_eval_report.md](outputs/short_eval/manual/agent6_livejson_top4_v4_judged/final_eval_report.md)

핵심 수치:

- `llm_as_judge_agreement = 0.4000`
- `llm_explanation_quality_score = 0.7200`
- `llm_explanation_groundedness_score = 0.7200`
- `explanation_presence_rate = 1.0000`
- `groundedness_score = 0.2177`
- `dimension_consistency_score = 0.8857`
- `e2e p95 = 45258.3658 ms`

## Interpretation

- 설명 존재율은 해결됐습니다.
- groundedness와 consistency도 이전보다 좋아졌습니다.
- 하지만 latency가 커서 이 상태를 최종 운영안으로 바로 채택하긴 어렵습니다.

## Practical Decision

- 지금은 eval을 더 넓히기보다 현재 결론을 고정하는 편이 맞습니다.
- 이후 우선순위는 새 평가보다 운영 latency를 줄이는 방향입니다.

## Do Not Spend More Time On

- rerank 재실험 확대
- eval에서 `sdk_handoff` 재활성화
- judge를 golden truth처럼 해석하는 일

## If We Resume Later

1. `top_n=4` vs `5`를 같은 prompt 버전으로 다시 비교
2. deterministic explanation 길이를 줄여 latency/cost 절감
3. judge와 golden이 갈린 query만 소량 분석
