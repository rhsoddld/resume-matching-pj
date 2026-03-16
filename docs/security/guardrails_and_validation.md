# Guardrails and Validation

## Input Validation

- Job request schema validation is handled by Pydantic models in `src/backend/schemas/job.py`.
- JD text is normalized and bounded for token safety (`optimize_jd_tokens`).
- Ingestion request schema validation is handled by `src/backend/schemas/ingestion.py`.
- Ingestion endpoint supports API-key guard and rate limit policy (`src/backend/api/ingestion.py`).

## Prompt Injection Defense

- JD prompt-injection heuristics are implemented in `src/backend/core/jd_guardrails.py`.
- Untrusted JD text is wrapped with `<job_description>` boundaries before model use.

## Fairness Guardrails

- Sensitive-term scan on JD and explanation text
- Culture weight cap checks
- Must-have underfit + high culture confidence warning
- Top-K seniority concentration warning when JD seniority is unspecified

## Failure Safety

- If advanced paths fail, runtime degrades to safer fallback paths.
- Response payload preserves warning and fallback metadata for auditability.
- `GET /api/ready` exposes Mongo/Milvus dependency readiness (`ready`/`degraded`) for operators.
