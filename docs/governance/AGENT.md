# AGENT.md — AI Resume Matching System

---

## Mission

AI-powered Resume Intelligence & Candidate Matching 시스템을 **Python + FastAPI + MongoDB + Milvus + OpenAI Agents SDK**로 구현하고, LangSmith + DeepEval 기반 평가/관측을 포함한 FDE 스타일 결과물을 낸다.

---

## Parsing Strategy (핵심 결정)

| 시점 | 파싱 방법 | LLM 사용 |
|------|---------|--------|
| **Ingestion (오프라인, 1회)** | rule-based (regex + spaCy) | ❌ 사용 안 함 |
| **Embedding (인덱싱 단계)** | `embedding_text`를 벡터화하여 Milvus 적재 | ✅ 사용 (Embedding API만) |
| **RAG Pipeline (매칭 요청 시)** | 구조화 필드 우선 사용. null 필드가 있을 경우 raw_text를 컨텍스트에 포함시켜 Agent가 job description과 함께 판단 | ✅ scoring/explanation에만 |

> `ResumeParsingAgent`는 **독립 파싱 Agent로 운용하지 않음**.  
> 파싱이 불완전한 경우 RAG pipeline에서 raw_text를 컨텍스트로 제공하고, 각 Agent가 자신의 판단에 필요한 범위만 추출.
> 단, 벡터 검색 품질을 위한 **임베딩 API 호출은 허용**한다(파싱 목적 LLM 호출과 분리).

---

## Current Retrieval Standard (고정안)

`Job Description`  
→ `OpenAI embedding (text-embedding-3-small)`  
→ `Milvus vector search`  
→ `BM25 skill search`  
→ `Hybrid merge`  
→ `Top 30`  
→ `Feature extraction`  
→ `Deterministic scoring`  
→ `Top 10`  
→ `LLM rerank (gpt-4o-mini)`  
→ `Top 5 candidates`

- 이 고정안은 capstone 범위에서 **비용/속도/구현 단순성**을 우선한 기준이다.
- 명시적 요청이 없는 한 embedding/rerank 모델 선택은 변경하지 않는다.
- 정확도 개선이 필요하면 `text-embedding-3-large` 또는 reranker 강화로 확장한다.
- retrieval / scoring / rerank 역할은 분리하며, deterministic scoring은 explainable ranking의 핵심 레이어로 유지한다.

---

## Structure Choices

| 레이어 | 선택 | 핵심 이유 |
|-------|------|---------|
| **Backend** | FastAPI + Layered Architecture (`api → services → repositories → core/schemas`) | 계층 분리로 테스트 및 교체 용이 |
| **Data Store** | MongoDB (도메인 데이터) + Milvus (벡터 인덱스) | 역할 분리, Milvus → FAISS/Chroma 교체 가능한 abstraction 레이어 포함 |
| **Agent Framework** | OpenAI Agents SDK (Orchestrator + Skill/Exp/Tech/Culture/Ranking + Recruiter/HiringManager A2A) | SDK 표준 패턴 + A2A 가중치 조정 |
| **Evaluation** | DeepEval (LLM-as-Judge) + LangSmith (runs/datasets/experiments) | 재현성·회귀 분석·자동 품질 루프 |
| **Frontend** | Vite + React + TypeScript 단일 페이지 | 최소 데모 UI, 백엔드 독립 동작 |

---

## Fixed Contracts

### 데이터셋

| 구분 | 데이터셋 | 역할 |
|------|---------|------|
| Primary | `snehaanbhawal/resume-dataset` (`ID`, `Resume_str`, `Category`) | 주요 검색·매칭 코퍼스 |
| Supplementary | `suriyaganesh/resume-dataset-structured` | 구조화 필드 enrichment 레퍼런스 |

### Core APIs

| Method | Endpoint | 설명 |
|--------|----------|------|
| `POST` | `/api/ingestion/resumes` | Resume 데이터셋 ingestion |
| `POST` | `/api/jobs` | Job 등록 |
| `POST` | `/api/jobs/match` | 매칭 요청 |
| `GET` | `/api/health` | Mongo·Milvus·OpenAI 상태 체크 |
| `GET` | `/api/ready` | Readiness 체크 |

### Core Collections

| Store | Collection | 설명 |
|-------|-----------|------|
| MongoDB | `candidates` | 후보자 도메인 데이터 |
| MongoDB | `jobs` | Job description 및 파싱 결과 |
| MongoDB | `match_results` | 매칭 결과 + 점수 + 설명 |
| Milvus | `candidate_embeddings` | 후보자 임베딩 벡터 |

---

## Active Scope

- **Requirement 1 (Must)**: R1.1–R1.6 기본 매칭 + FastAPI 엔드포인트 구현.
- **Requirement 2 (Should)**: Multi-Agent scoring (SkillMatching · ExperienceEval · TechnicalEval · CultureFit · Ranking) · Hybrid retrieval · A2A weight negotiation. **ResumeParsingAgent 제외** (ingestion 시 rule-based 처리로 대체).
- **Requirement 3 (Should)**: DeepEval 평가 + LangSmith 추적 + golden set.
- **Requirement 4 (Should)**: React/Vite 데모 UI.
- **Requirement 5 (Must)**: README · 아키텍처 다이어그램 · TRACEABILITY · Reviewer Checklist.

---

## Progress Snapshot

| Phase | 설명 | Status |
|-------|------|--------|
| Phase 0 | Scope & Contracts | ✅ Done |
| Phase 1 | Happy Path (Ingestion + 기본 매칭 API + 최소 UI) | 🔄 In Progress |
| Phase 2 | Multi-Agent & Hybrid Retrieval | ⬜ Pending |
| Phase 3 | Evaluation & Observability | ⬜ Pending |
| Phase 4 | Reviewer Layer & Polish | ⬜ Pending |

**Legend**: ✅ Done · 🔄 In Progress · ⬜ Pending

### Phase 1 세부 현황 (2026-03-13)

| 항목 | 상태 | 증거 |
|------|------|------|
| MongoDB Ingestion (5,484건) | ✅ 완료 | `ingest_resumes.py` |
| Normalization v6 (norm-v6-substring) | ✅ 완료 | `core_skills empty 0.5% (25건)` |
| Skill Taxonomy v5 (260+항목) | ✅ 완료 | `config/skill_taxonomy.yml` |
| Skill Alias 확장 (11개 canonical merge) | ✅ 완료 | `config/skill_aliases.yml` |
| Sneha category → core_skills inject | ✅ 완료 | Sneha empty 0.0% |
| Substring matching (ex. `sql server 2012`→`sql server`) | ✅ 완료 | `skill_ontology.py` |
| Milvus 벡터 적재 | 🔴 미실행 | `embedding_hash null (5,484건)` |
| 기본 매칭 API (`POST /api/jobs/match`) | 🔄 구조 완료, E2E 테스트 대기 | `matching_service.py` |
| Deterministic scoring | ✅ 완료 | `scoring_service.py` |
| 5/5 유닛 테스트 | ✅ Pass | `tests/test_skill_overlap_scoring.py` |

> **Milvus 미적재 = 매칭 API 실질적 연동 불가**: `search_embeddings()` 0건 반환 상태.

---

## Next Slice

1. **Milvus 적재 실행** (`--target milvus --milvus-from-mongo --force-reembed`) — Phase 1 활성화 블로컨
2. 매칭 API end-to-end smoke test (`POST /api/jobs/match`)
3. Phase 2 Multi-Agent 시작 판단

---

## Do-Not-Touch (for now)

- Milvus 외 다른 벡터 DB로의 즉시 교체 (abstraction 레이어만 준비).
- 요구사항 외 대규모 UI/대시보드 추가.

---

## Evidence Locations

| 문서 유형 | 경로 |
|---------|------|
| Requirements | `requirements/requirements.md` |
| Architecture | `docs/architecture/system-architecture.md` |
| Data Flow | `docs/data-flow/` |
| Evaluation Plan & Results | `docs/eval/` · `src/eval/` |
| Traceability Matrix | `docs/governance/TRACEABILITY.md` |
| ADR (Architecture Decision Records) | `docs/adr/` |
