# Functional Requirements

This document is the canonical baseline that merges core requirement IDs from the legacy requirements master into the current structure.

**Requirements ↔ implementation traceability (reviewer guide):** [docs/governance/TRACEABILITY.md](../docs/governance/TRACEABILITY.md)

## 1) Requirement 1 (Basic)

| ID | Requirement |
|---|---|
| R1.1 | Provide basic RAG-based candidate retrieval. |
| R1.2 | Support skills-based semantic matching. |
| R1.3 | Provide a baseline ranking policy centered on skill overlap. |
| R1.4 | Support job category filtering. |
| R1.5 | Provide basic job–resume alignment scoring. |
| R1.6 | Provide guardrails for JD input (validation / prompt-injection defense / token safety). |
| R1.7 | Provide resume parsing/normalization validation. |
| R1.8 | Support metadata filtering (experience, role/category, education). |
| R1.9 | Expose core functionality via API endpoints. |

## 2) Requirement 2 (Advanced)

| ID | Requirement |
|---|---|
| R2.1 | Support DeepEval-based quality/diversity evaluation. |
| R2.2 | Provide custom evaluation (skill/experience/culture/potential). |
| R2.3 | Support advanced reranking paths (embedding/LLM/fine-tuned). |
| R2.4 | Support LLM-as-Judge-based soft-skill/potential evaluation. |
| R2.5 | Provide token-usage optimization strategies. |
| R2.6 | Provide throughput/latency benchmarks (including candidates/sec). |
| R2.7 | Provide bias/fairness guardrails. |
| R2.8 | Provide a frontend suitable for reviewer demos. |

## 3) Hybrid Candidate Retrieval

| ID | Requirement |
|---|---|
| HCR.1 | Provide hybrid retrieval combining vector + keyword signals. |
| HCR.2 | Provide dynamic filtering (exp/skill/edu/seniority/category). |
| HCR.3 | Provide a shortlist reranking path. |

## 4) Multi-Stage Hiring Agent Pipeline

| ID | Requirement |
|---|---|
| MSA.1 | Provide orchestration for multi-agent evaluation. |
| MSA.2 | Provide a Skill Matching Agent. |
| MSA.3 | Provide an Experience Evaluation Agent. |
| MSA.4 | Provide a Technical Evaluation Agent. |
| MSA.5 | Provide a Culture Fit Agent. |
| MSA.6 | Connect the agent score pack into final ranking. |

## 5) Additional Hiring Intelligence

| ID | Requirement |
|---|---|
| AHI.1 | Provide explainable ranking and score breakdown. |
| AHI.2 | Provide a recruiter feedback loop. |
| AHI.3 | Provide a hiring analytics observability path. |
| AHI.4 | Provide interview scheduling / email draft handoff. |
| AHI.5 | Provide recruiter/hiring-manager A2A negotiation. |

## 6) Deliverables and Dataset

| ID | Requirement |
|---|---|
| D.1 | Provide a system architecture diagram (ingestion/retrieval/agent/ranking). |
| D.2 | Provide design decisions and trade-off documents. |
| D.3 | Provide runnable code + README + example requests. |
| D.4 | Provide a results summary suitable for demos/presentations. |
| DS.1 | Provide a usage path for the primary dataset (snehaanbhawal). |
| DS.2 | Provide an expansion path for the alternate dataset (suriyaganesh). |
| DS.3 | Provide input handling paths for CSV/JSON/PDF. |
| DS.4 | Provide extraction of key fields (skill/experience/education/category). |
| DS.5 | Use extracted fields in retrieval/filtering/scoring. |

## 7) Priority Guidance

1. Phase 1 (MVP): `PO.*`, `KC.*`, `R1.*`
2. Phase 2 (Advanced): `R2.*`, `HCR.*`, `MSA.*`, `AHI.*`
3. Phase 3 (Delivery): `D.*`, `DS.*`
