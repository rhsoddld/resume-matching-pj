# Functional Requirements

이 문서는 기존 요구사항 마스터 문서의 핵심 요구사항 ID를 현재 구조로 병합한 기준 문서다.

**요구사항↔구현 추적·레뷰어 가이드:** [docs/governance/TRACEABILITY.md](../docs/governance/TRACEABILITY.md)

## 1) Requirement 1 (Basic)

| ID | Requirement |
|---|---|
| R1.1 | Basic RAG 기반 후보 검색을 제공해야 한다. |
| R1.2 | Skills-based semantic matching을 지원해야 한다. |
| R1.3 | Skill overlap 중심의 baseline ranking 정책을 제공해야 한다. |
| R1.4 | Job category filtering을 지원해야 한다. |
| R1.5 | Basic job-resume alignment scoring을 제공해야 한다. |
| R1.6 | JD 입력 guardrails(유효성/주입 방어/토큰 안전)를 제공해야 한다. |
| R1.7 | Resume parsing/normalization validation을 제공해야 한다. |
| R1.8 | Metadata filtering(경력, role/category, education)을 지원해야 한다. |
| R1.9 | 핵심 기능을 API endpoint로 제공해야 한다. |

## 2) Requirement 2 (Advanced)

| ID | Requirement |
|---|---|
| R2.1 | DeepEval 기반 quality/diversity 평가를 지원해야 한다. |
| R2.2 | Custom eval(skill/experience/culture/potential)을 제공해야 한다. |
| R2.3 | Rerank 고도화(embedding/LLM/fine-tuned 경로)를 지원해야 한다. |
| R2.4 | LLM-as-Judge 기반 soft-skill/potential 평가를 지원해야 한다. |
| R2.5 | Token usage optimization 전략을 제공해야 한다. |
| R2.6 | Throughput/latency benchmark(candidates/sec 포함)를 제공해야 한다. |
| R2.7 | Bias/fairness guardrail을 제공해야 한다. |
| R2.8 | Reviewer demo 가능한 frontend를 제공해야 한다. |

## 3) Hybrid Candidate Retrieval

| ID | Requirement |
|---|---|
| HCR.1 | Vector + keyword 결합 hybrid retrieval을 제공해야 한다. |
| HCR.2 | Dynamic filtering(exp/skill/edu/seniority/category)을 제공해야 한다. |
| HCR.3 | Shortlist reranking 경로를 제공해야 한다. |

## 4) Multi-Stage Hiring Agent Pipeline

| ID | Requirement |
|---|---|
| MSA.1 | 다중 에이전트 기반 평가 오케스트레이션을 제공해야 한다. |
| MSA.2 | Skill Matching Agent를 제공해야 한다. |
| MSA.3 | Experience Evaluation Agent를 제공해야 한다. |
| MSA.4 | Technical Evaluation Agent를 제공해야 한다. |
| MSA.5 | Culture Fit Agent를 제공해야 한다. |
| MSA.6 | Agent score pack을 최종 랭킹에 연결해야 한다. |

## 5) Additional Hiring Intelligence

| ID | Requirement |
|---|---|
| AHI.1 | Explainable ranking과 score breakdown을 제공해야 한다. |
| AHI.2 | Recruiter feedback loop를 제공해야 한다. |
| AHI.3 | Hiring analytics 관측 경로를 제공해야 한다. |
| AHI.4 | Interview scheduling/email draft handoff를 제공해야 한다. |
| AHI.5 | Recruiter/HiringManager A2A negotiation을 제공해야 한다. |

## 6) Deliverables and Dataset

| ID | Requirement |
|---|---|
| D.1 | 시스템 아키텍처(ingestion/retrieval/agent/ranking) 다이어그램을 제공해야 한다. |
| D.2 | 설계 의사결정과 tradeoff 문서를 제공해야 한다. |
| D.3 | 실행 가능한 코드/README/예시 요청을 제공해야 한다. |
| D.4 | 데모/발표를 위한 결과 요약 자료를 제공해야 한다. |
| DS.1 | primary dataset(snehaanbhawal) 사용 경로를 제공해야 한다. |
| DS.2 | 대체 데이터셋(suriyaganesh) 확장 경로를 제공해야 한다. |
| DS.3 | CSV/JSON/PDF 입력 처리 경로를 제공해야 한다. |
| DS.4 | skill/experience/education/category 핵심 필드 추출을 제공해야 한다. |
| DS.5 | 추출 필드를 retrieval/filtering/scoring에 활용해야 한다. |

## 7) Priority Guidance

1. Phase 1 (MVP): `PO.*`, `KC.*`, `R1.*`
2. Phase 2 (Advanced): `R2.*`, `HCR.*`, `MSA.*`, `AHI.*`
3. Phase 3 (Delivery): `D.*`, `DS.*`
