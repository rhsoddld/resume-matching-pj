# ADR-009 Observability Strategy

## Decision
Adopt structlog for structured logging, request_id middleware for request correlation, LangSmith for agent tracing (openai-agents), and `traceable_op` for retrieval/rerank spans. Expose liveness (`/api/health`) and readiness (`/api/ready` for Mongo + Milvus); optional MongoDB request log for persistence.

## Why
- Structured logs and request_id support debugging and ops without coupling to a specific vendor
- LangSmith and traceable_op give visibility into LLM and retrieval latency for cost and quality tuning
- Health/ready endpoints enable container orchestration (e.g. K8s probes) and graceful degradation checks

## Consequences
- Multiple observability touchpoints (logs, traces, metrics); custom retrieval metrics (top_k, elapsed_ms, candidates_per_sec, fairness_guardrail_triggered) live in logs or dedicated sinks—dashboard/alerting is follow-up
- MongoDB log handler is optional and async to avoid blocking request path

*Implementation:* `src/backend` logging middleware, `ops.logging`; LangSmith/traceable_op in retrieval and agent code.  
*Ref:* [docs/observability/logging_metrics.md](../observability/logging_metrics.md), [docs/observability/monitoring.md](../observability/monitoring.md)
