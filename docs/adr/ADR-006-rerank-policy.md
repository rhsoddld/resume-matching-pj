# ADR-006 Rerank Policy (Conditional Gate)

## Decision
Rerank is off by default; run only when gate conditions are met (e.g. tie-like top2 gap, ambiguous query). Use timeout and fallback to baseline shortlist on failure.

## Why
- Latency/quality A/B evidence for rerank ROI was not yet established at baseline; keeping default path stable avoids over-claiming
- Gate limits rerank to cases where it is most likely to help (ambiguous or close scores)
- Timeout and fallback preserve availability and UX when rerank is slow or failing

## Consequences
- Two code paths (baseline vs reranked) and model routing (default vs high-quality) increase complexity
- Rerank ROI and gate thresholds should be validated with benchmarks before tightening or expanding

*Implementation:* `src/backend/services/matching/rerank_policy.py`, `src/backend/services/cross_encoder_rerank_service.py`, `src/backend/core/model_routing.py`
