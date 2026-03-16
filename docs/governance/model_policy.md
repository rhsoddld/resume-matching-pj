# Model Policy

## Model Routing Policy

| Stage | Default | Optional / Fallback | Notes |
|---|---|---|---|
| Embedding | `text-embedding-3-small` | larger embedding model | 인덱싱 비용/속도 균형 기준 |
| Retrieval rerank | embedding-mode rerank | LLM rerank (`gpt-4o` 계열) | ambiguity/tie-like 조건에서만 실행 권장 |
| Agent runtime | `sdk_handoff` | `live_json` -> `heuristic` | 장애 시 graceful degradation |
| Judge | versioned judge model | 수동/휴먼 검증 | 결과는 평가 문서에 아카이브 |

Source:
- `src/backend/core/model_routing.py`
- `src/backend/core/settings.py`
- `src/backend/agents/runtime/service.py`

## Deterministic Boundaries

- ingestion parsing은 생성형 LLM을 기본 경로로 사용하지 않는다.
- query understanding은 deterministic extraction을 우선 사용한다.
- LLM은 rerank/agent evaluation/judge 보강 경로에서만 제한적으로 사용한다.

## Safety Policy

1. 보호 속성(나이/성별/인종/국적/종교/장애/혼인상태)을 점수 근거에 사용하지 않는다.
2. 설명 텍스트는 JD/후보 증거에 근거한 표현만 허용한다.
3. 근거 부족 시 과신(high-confidence claim)을 금지한다.
4. 민감어 탐지/과도한 culture weighting/must-have 미달 경고를 활성화한다.

## Fallback Policy

### Query fallback
- trigger: `confidence` 저하 또는 `unknown_ratio` 과다
- fallback 후에도 ontology/alias normalization을 반드시 재적용

### Agent fallback
- 순서: `sdk_handoff` -> `live_json` -> `heuristic`
- 응답에 runtime mode 및 fallback reason을 남겨 추적 가능해야 함

### Retrieval fallback
- 벡터 검색 실패 시 Mongo lexical fallback
- 실패 이벤트를 observability 지표에 누적
