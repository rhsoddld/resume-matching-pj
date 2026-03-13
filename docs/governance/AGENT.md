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
| Phase 0 | Scope & Contracts | 🔄 In Progress |
| Phase 1 | Happy Path (Ingestion + 기본 매칭 API + 최소 UI) | ⬜ Pending |
| Phase 2 | Multi-Agent & Hybrid Retrieval | ⬜ Pending |
| Phase 3 | Evaluation & Observability | ⬜ Pending |
| Phase 4 | Reviewer Layer & Polish | ⬜ Pending |

**Legend**: ✅ Done · 🔄 In Progress · ⬜ Pending

---

## Next Slice

- Kaggle dataset 기준으로 `candidates`/`jobs` 스키마와 Milvus 인덱스 스키마를 코드 레벨에서 정의하고, ingestion happy path 스캐폴딩 작성.

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
