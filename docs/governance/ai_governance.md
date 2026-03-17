# AI Governance

## Governance Mission (Legacy AGENT/PLAN Merged)

Governance goals:
1. Maintain deterministic-first principles for ingestion/query understanding
2. Clarify responsibility boundaries across retrieval → evaluation → negotiation → ranking
3. Treat explainable output and fairness guardrails as baseline contracts
4. Ensure traceability across requirements ↔ code ↔ evaluation artifacts

## Canonical Documents and Roles

| Document | Role |
|---|---|
| `requirements/problem_definition.md` | Problem definition / objectives |
| `requirements/functional_requirements.md` | Requirement ID system (R1/R2/HCR/MSA/AHI/D/DS) |
| `requirements/traceability_matrix.md` | Links implementation/verification/document evidence |
| `docs/architecture/system_architecture.md` | Target architecture and layer responsibilities |
| `docs/data-flow/*.md` | Ingestion/retrieval runtime flows |
| `docs/evaluation/*.md` | Evaluation criteria/results |
| `docs/adr/*.md` | Design decisions and background |

## Status Labels

- `Implemented`: code + documentation + verification evidence all exist
- `Partial`: code exists but operational verification or quality evidence is lacking
- `Planned`: design/backlog state

## Governance Control Rules

1. Ship new features with code + documentation updated in the same change.
2. For scoring/prompt/model-routing changes, leave at least one evaluation evidence artifact.
3. Keep fallback policy (`sdk_handoff -> live_json -> heuristic`) synchronized between docs and implementation.
4. Exclude sensitive attributes from scoring evidence and record related warnings in responses/logs.
5. When changing version fields (`normalization_version`, `taxonomy_version`, `embedding_text_version`, `PROMPT_VERSION`), document the rationale.

## Review Cadence

| Cadence | Review items |
|---|---|
| Per PR | requirements impact, test impact, documentation impact |
| Weekly | trends for retrieval/agent/fairness metrics |
| Pre-release | refresh traceability matrix, review evaluation results, update ADRs |

## Current Governance Priorities

1. Automate regression detection for retrieval quality
2. Improve validation of rerank impact vs latency/cost
3. Operationalize a dashboard for fairness warning metrics
4. Strengthen evidence data for feedback loops and hiring intelligence
