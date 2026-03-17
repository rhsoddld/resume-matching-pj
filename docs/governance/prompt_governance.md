# Prompt Governance

## Prompt Ownership

| 영역 | 소스 |
|---|---|
| Agent prompts | `src/backend/agents/runtime/prompts.py` |
| Prompt version | `PROMPT_VERSION` (현재 v5: evidence 역할 구분 반영) |
| Evidence 역할 구분 (v5) | [agent_evaluation_and_scoring.md § 2.5](../agents/agent_evaluation_and_scoring.md#25-evidence-역할-구분-evidence-rule-prompt-v5-이상) |
| Judge rubric reference | `docs/evaluation/evaluation_results.md` (rubric snapshot) |

## Prompt Change Rules

1. 프롬프트 변경은 버전 증가와 함께 적용한다.
2. 변경 시 스키마 출력 계약이 유지되어야 한다.
3. 비근거 추론/환각 방지 규칙을 프롬프트에 명시한다.
4. 보호 속성 배제 규칙을 프롬프트에 명시한다.
5. 변경 후 최소 1개 이상의 eval evidence를 남긴다.

## Mandatory Audit Fields

- `prompt_version`
- `runtime_mode`
- `request_id`
- `runtime_fallback_used`
- `runtime_reason`

## Judge Rubric Guardrails (Legacy Restored)

LLM-as-Judge 평가는 아래 원칙을 따른다.
- soft-skill alignment (40%)
- growth potential (40%)
- evidence quality (20%)

Hard rules:
1. soft-skill/potential 증거가 모두 부족하면 `<= 0.40`
2. 협업/책임감 요구와 명백히 모순되면 `<= 0.50`
3. generic evidence는 최대 `0.74`
4. 구체적/일관/성장 궤적 증거가 충분하면 `>= 0.75`

## Prompt Review Checklist

- 입력/출력 스키마가 문서와 일치하는가
- 금지된 근거(보호 속성, 허구)가 없는가
- fallback reason이 로그와 응답에 남는가
- 비용 대비 품질 이득이 확인되는가
