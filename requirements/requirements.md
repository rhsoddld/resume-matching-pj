# Requirements — AI-Powered Resume Intelligence and Candidate Matching System

## 1) Scope and Goal

이 문서는 [case-study.pdf](/Users/lee/Desktop/resume-matching-pj/requirements/case-study.pdf)의 요구사항을 빠짐없이 반영한 단일 기준 문서다.  
목표는 자연어 기반 채용 요구를 해석하고, 대규모 이력서 풀에서 적합 후보를 검색/평가/설명하는 AI 기반 후보 매칭 시스템을 구축하는 것이다.

---

## 2) Source Sections (Case Study)

- Problem
- Objective
- Key Capabilities
- Requirement 1 (Basic)
- Requirement 2 (Advanced)
- Hybrid Candidate Retrieval
- Multi-Stage Hiring Agent Pipeline
- Additional Hiring Intelligence
- Deliverables
- Dataset

---

## 3) Problem and Objective Requirements

| ID | Requirement |
|---|---|
| PO.1 | 단순 키워드 검색을 넘어 후보자의 기술 적합성, 숙련도 깊이, 경력 흐름, 직무 정합성을 평가해야 한다. |
| PO.2 | 위치, 학력, 산업 배경 등 메타데이터 기반 필터링/해석을 지원해야 한다. |
| PO.3 | 키워드가 정확히 일치하지 않아도 전이 가능한(transferable/adjacent) 역량을 탐지해야 한다. |
| PO.4 | PDF/포트폴리오 링크/구조화 프로필 등 다양한 이력서 포맷에서 일관된 정보 추출이 가능해야 한다. |
| PO.5 | 시스템은 단순 조회를 넘어 후보 요약 인사이트와 설명 가능한 매칭 점수를 제공해야 한다. |
| PO.6 | 대규모 후보군 탐색을 빠르게 수행해 수동 검토 시간을 줄이고 평가 일관성을 높여야 한다. |

---

## 4) Key Capabilities Requirements

| ID | Capability Requirement |
|---|---|
| KC.1 | 자연어 채용 요구에서 기술, 툴, 경험 수준(시니어리티)을 의미적으로 해석해야 한다. |
| KC.2 | 후보 기술/경험/배경과 JD 정합성을 기반으로 지능형 매칭을 수행해야 한다. |
| KC.3 | 스킬 사용 맥락을 고려해 기초 친숙도와 심화 전문성을 구분해야 한다. |
| KC.4 | 경력 성장, 역할 전환, 연차 수준을 포함한 Career Progression 분석을 제공해야 한다. |
| KC.5 | 전이 가능한 스킬을 가진 후보를 추천할 수 있어야 한다. |
| KC.6 | 후보별 핵심 강점, 관련 경험, 성과를 구조화된 인사이트로 제공해야 한다. |
| KC.7 | 추천 사유가 포함된 설명 가능한 매칭 점수를 제공해야 한다. |

---

## 5) Requirement 1 (Basic) — Core MVP

| ID | Basic Requirement |
|---|---|
| R1.1 | Basic RAG 기반 후보 검색을 제공해야 한다. |
| R1.2 | Skills-based semantic matching을 지원해야 한다. |
| R1.3 | Skill overlap 기반의 simple ranking agent를 제공해야 한다. |
| R1.4 | Job category filtering을 지원해야 한다. |
| R1.5 | Basic job-resume alignment scoring을 제공해야 한다. |
| R1.6 | 입력 가드레일(유효한 job requirement 검사)을 제공해야 한다. |
| R1.7 | Resume parsing validation을 제공해야 한다. |
| R1.8 | Metadata filtering(경력 수준, role category, education)을 지원해야 한다. |
| R1.9 | 핵심 기능을 외부에서 사용할 수 있도록 API endpoint로 노출해야 한다. |

---

## 6) Requirement 2 (Advanced)

| ID | Advanced Requirement |
|---|---|
| R2.1 | DeepEval 기반 matching quality 및 diversity metrics 평가를 지원해야 한다. |
| R2.2 | Custom evaluation(스킬 커버리지, 경험 적합도, culture match)을 제공해야 한다. |
| R2.3 | Fine-tuned job-resume embeddings 기반 rerank를 지원해야 한다. |
| R2.4 | LLM-as-judge를 이용해 soft skills 및 성장 가능성(potential)을 평가해야 한다. |
| R2.5 | 대량 스크리닝을 위한 token usage optimization을 제공해야 한다. |
| R2.6 | 성능 벤치마킹(초당 처리 후보 수, candidates/sec)을 제공해야 한다. |
| R2.7 | 편향 감지 가드레일(인구통계/언어)을 제공해야 한다. |
| R2.8 | 최종 사용자 상호작용을 보여줄 수 있는 간단한 프론트엔드 UI를 제공해야 한다. |

---

## 7) Hybrid Candidate Retrieval Requirements

| ID | Requirement |
|---|---|
| HCR.1 | 벡터 임베딩 검색 + 키워드 검색을 결합한 hybrid search를 제공해야 한다. |
| HCR.2 | 경험, 스킬, 학력, 산업 기준 동적 필터링(dynamic filtering)을 지원해야 한다. |
| HCR.3 | Cross-encoder relevance scoring 기반 reranking을 제공해야 한다. |

---

## 8) Multi-Stage Hiring Agent Pipeline Requirements

| ID | Requirement |
|---|---|
| MSA.1 | 다중 에이전트 기반 평가 파이프라인을 구현해야 한다. |
| MSA.2 | Resume Parsing Agent: 구조화된 후보 정보를 추출해야 한다. |
| MSA.3 | Skill Matching Agent: JD와 후보 스킬을 비교 평가해야 한다. |
| MSA.4 | Experience Evaluation Agent: 연차와 경력 궤적을 분석해야 한다. |
| MSA.5 | Technical Evaluation Agent: 기술 전문성 깊이를 추정해야 한다. |
| MSA.6 | Culture Fit Agent: 커뮤니케이션/소프트스킬 신호를 평가해야 한다. |

---

## 9) Additional Hiring Intelligence Requirements

| ID | Requirement |
|---|---|
| AHI.1 | 설명 가능한 후보 랭킹 및 매칭 점수 breakdown을 제공해야 한다. |
| AHI.2 | 랭킹 모델 개선을 위한 recruiter feedback loop를 제공해야 한다. |
| AHI.3 | skill demand 및 candidate trend를 보여주는 hiring analytics dashboard를 제공해야 한다. |
| AHI.4 | interview scheduling agent로의 handoff를 지원해야 한다. |
| AHI.5 | recruiter와 hiring manager 간 Agent-to-Agent (A2A) communication을 지원해야 한다. |

---

## 10) Deliverables Requirements

| ID | Deliverable Requirement |
|---|---|
| D.1 | Architecture Diagram(JPEG/PDF) 제출: ingestion/parsing, chunking/embeddings, hybrid retrieval, multi-agent pipeline, final ranking/explanation 데이터 흐름 포함. |
| D.2 | Design 문서 제출: 임베딩 모델 선택, 긴 이력서 chunking 전략, hybrid vs semantic-only trade-off, agent orchestration, bias mitigation 전략 포함. |
| D.3 | Full Executable Code(Microservice) 제출: 모듈성/가독성 확보, README에 setup/run, ingestion/indexing, JD query 예시, ranked output+explanation 예시 포함. |
| D.4 | 10분 Panel Presentation 준비: 8분 데모(입력→검색→평가→설명형 랭킹), 2분 Q&A 포함. |

---

## 11) Dataset Requirements

| ID | Requirement |
|---|---|
| DS.1 | Primary dataset: `snehaanbhawal/resume-dataset` 사용 가능해야 한다. |
| DS.2 | Alternative datasets(명시된 Kaggle 링크들) 교체/확장 사용 가능해야 한다. |
| DS.3 | CSV/JSON/PDF 포맷을 처리 가능해야 한다. |
| DS.4 | 핵심 필드(skills, experience, education, category, resume_text)를 추출/정규화할 수 있어야 한다. |
| DS.5 | 스킬/역할/경력 기반 분류 정보를 semantic matching, filtering, ranking에 활용해야 한다. |

---

## 12) Coverage Mapping (Requested Section Mapping)

| Case Study Section | Covered Requirement IDs |
|---|---|
| Problem | PO.1, PO.2, PO.3, PO.4, PO.5, PO.6 |
| Objective | PO.5, PO.6, KC.1, KC.2, KC.6, KC.7, R1.9 |
| Key Capabilities | KC.1, KC.2, KC.3, KC.4, KC.5, KC.6, KC.7 |
| Requirement 1 (Basic) | R1.1, R1.2, R1.3, R1.4, R1.5, R1.6, R1.7, R1.8, R1.9 |
| Requirement 2 (Advanced) | R2.1, R2.2, R2.3, R2.4, R2.5, R2.6, R2.7, R2.8 |
| Hybrid Candidate Retrieval | HCR.1, HCR.2, HCR.3 |
| Multi-Stage Hiring Agent Pipeline | MSA.1, MSA.2, MSA.3, MSA.4, MSA.5, MSA.6 |
| Additional Hiring Intelligence | AHI.1, AHI.2, AHI.3, AHI.4, AHI.5 |
| Deliverables | D.1, D.2, D.3, D.4 |
| Dataset | DS.1, DS.2, DS.3, DS.4, DS.5 |

---

## 13) Priority Guidance (Execution Plan)

- Phase 1 (MVP): R1.*, KC.*, PO.*
- Phase 2 (Advanced Intelligence): R2.*, HCR.*, MSA.*, AHI.*
- Phase 3 (Delivery Readiness): D.*, DS.*

본 문서 기준으로는 케이스 스터디 원문 요구사항을 누락 없이 포함한다.
