# Model Policy

## Model Routing Policy

| Stage | Default | Optional / Fallback | Notes |
|---|---|---|---|
| Embedding | `text-embedding-3-small` | larger embedding model | indexing cost/speed balance baseline |
| Retrieval rerank | embedding-mode rerank | LLM rerank (`gpt-4o` family) | recommended only for ambiguity / tie-like cases |
| Agent runtime | `sdk_handoff` | `live_json` -> `heuristic` | graceful degradation on failures |
| Judge | versioned judge model | manual/human verification | archive results in evaluation docs |

Source:
- `src/backend/core/model_routing.py`
- `src/backend/core/settings.py`
- `src/backend/agents/runtime/service.py`

## Deterministic Boundaries

- Do not use generative LLM parsing as the default ingestion path.
- Prefer deterministic extraction for query understanding.
- Use LLMs only as limited augmentation paths (rerank / agent evaluation / judge).

## Safety Policy

1. Do not use protected attributes (age/gender/race/nationality/religion/disability/marital status) as scoring evidence.
2. Allow explanation text only when grounded in JD/candidate evidence.
3. When evidence is lacking, forbid overconfident claims.
4. Enable sensitive-term detection, excessive culture-weighting warnings, and must-have shortfall warnings.

## Fallback Policy

### Query fallback
- trigger: degraded `confidence` or excessive `unknown_ratio`
- after fallback, always re-apply ontology/alias normalization

### Agent fallback
- order: `sdk_handoff` -> `live_json` -> `heuristic`
- responses must include runtime mode and fallback reason for traceability

### Retrieval fallback
- if vector search fails, fall back to Mongo lexical retrieval
- accumulate failure events in observability metrics
