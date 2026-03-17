# Problem Definition

**Requirements ↔ implementation traceability (reviewer guide):** [docs/governance/TRACEABILITY.md](../docs/governance/TRACEABILITY.md)

## Scope
This project builds an AI-powered candidate matching system that interprets natural-language job descriptions (JDs) and searches/evaluates/explains suitable candidates from a large resume pool.

Core scope:
- deterministic ingestion and normalization
- deterministic query understanding
- hybrid retrieval(vector + lexical + metadata)
- multi-agent evaluation
- recruiter/hiring-manager weight negotiation
- explainable ranking

## Core Problem Statements (Legacy Requirements Restored)

| ID | Problem Statement |
|---|---|
| PO.1 | Keyword-only search is not sufficient to evaluate technical fit, depth of proficiency, and career context. |
| PO.2 | If metadata (location/education/industry background) is not interpreted together, hiring decision quality degrades. |
| PO.3 | Exact-match search misses transferable / adjacent-skill candidates. |
| PO.4 | Parsing quality varies widely due to input format diversity (CSV/PDF/unstructured text). |
| PO.5 | A score-only system is hard to trust in practice; explainable evidence is required. |
| PO.6 | Manual review of large candidate pools is slow and inconsistent; automation/standardization is needed. |

## Objectives

| ID | Objective |
|---|---|
| OBJ.1 | Convert a JD into a structured query profile to stabilize retrieval signal quality. |
| OBJ.2 | Prioritize relevant-candidate recall at the retrieval stage. |
| OBJ.3 | Provide per-candidate evaluation across skill/experience/technical/culture plus a consensus-based weight policy. |
| OBJ.4 | Provide explainability in final recommendations, including score breakdown, evidence, and gaps. |
| OBJ.5 | Accumulate evaluation metrics (quality/performance/reliability/fairness) in a reproducible form. |

## Non-Goals (Current Capstone Boundary)

- We do not use generative-LLM parsing as the default ingestion path.
- A fine-tuned embedding training/operations pipeline is deferred to future work.
- A full ATS-replacement product scope (approval workflows, calendar integrations, org-wide permission model) is out of scope.
