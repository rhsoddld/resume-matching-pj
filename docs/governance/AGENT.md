# AGENT.md — AI Resume Matching System

---

## Mission

AI-powered Resume Intelligence & Candidate Matching 시스템을 **Python + FastAPI + MongoDB + Milvus + OpenAI Agents SDK**로 구현하고, LangSmith + DeepEval 기반 평가/관측을 포함한 FDE 스타일 결과물을 낸다.

---

## Documentation Discipline

발표 직전에 한 번에 정리하지 않도록, 아래 항목은 작업 중 결정되는 즉시 문서에 반영한다.

| 무엇을 기록할까 | 어디에 기록할까 |
|------|------|
| 아키텍처/기술 선택, 대안 비교, trade-off | `docs/adr/DECISIONS.md` |
| 현재 작업 우선순위, 다음 액션, 발표 준비 TODO | `docs/governance/PLAN.md` |
| 프로젝트 개요, 실행 방법, 폴더 구조, 심사용 문서 진입점 | `README.md` |

### 반드시 남길 Key Decision 포인트

- 왜 이 구조를 선택했는가
- 어떤 대안을 검토했고 왜 제외했는가
- 비용/성능/정확도/운영성 trade-off는 무엇인가
- fallback, validation, resilience는 어떻게 설계했는가
- 평가(quality/eval) 방식과 그 이유는 무엇인가

### 작업 원칙

- 구현 중 "이건 나중에 설명해야 할 것 같다" 싶으면 바로 `DECISIONS.md`에 남긴다.
- 문서 내용은 실제 코드/폴더 구조와 반드시 동기화한다.
- 발표 필수 아티팩트(README, architecture, data flow, decisions)는 항상 최신 상태로 유지한다.

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
→ `OpenAI embedding (OPENAI_EMBEDDING_MODEL, default text-embedding-3-small)`  
→ `Milvus vector search`  
→ `Mongo batch enrichment`  
→ `Deterministic scoring`  
→ `Top-K response`

- 이 고정안은 capstone 범위에서 **비용/속도/구현 단순성**을 우선한 기준이다.
- embedding 기본 모델을 `text-embedding-3-small`로 둔 이유는 대량 재임베딩/반복 실험 시 비용과 지연을 안정적으로 관리하기 위해서다.
- retrieval / enrichment / scoring 역할을 분리하고, deterministic scoring은 explainable ranking의 핵심 레이어로 유지한다.
- 정확도 상향이 필요하면 `OPENAI_EMBEDDING_MODEL=text-embedding-3-large`로 즉시 전환 가능하다.
- BM25/hybrid merge/rerank는 후속 Phase 확장 항목으로 관리한다.

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
| Milvus 벡터 적재 | ✅ 완료 | `ingest_complete: seen=5484, embedded=5484, embed_skipped=0` |
| 기본 매칭 API (`POST /api/jobs/match`) | 🔄 구조 완료, E2E 테스트 대기 | `matching_service.py` |
| Deterministic scoring | ✅ 완료 | `scoring_service.py` |
| 5/5 유닛 테스트 | ✅ Pass | `tests/test_skill_overlap_scoring.py` |

> **Milvus 인덱스 활성화 완료**: 이제 `POST /api/jobs/match` 경로의 실질 E2E 검증 단계로 진행 가능.

---

## Next Slice

1. 매칭 API end-to-end smoke test (`POST /api/jobs/match`)
2. retrieval/score 응답 품질 점검(Top-K, score breakdown)
3. Phase 2 Multi-Agent 시작 판단

### 발표 준비 관점의 병행 체크

4. 새 설계 판단이 생기면 `docs/adr/DECISIONS.md`에 즉시 추가
5. architecture / data flow / folder structure 문서와 실제 구현의 sync 유지
6. panel 질문 대비용 trade-off 메모를 누적 정리

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
| Evaluation Plan & Results | (목표 구조) `docs/eval/` · `src/eval/` |
| Traceability Matrix | `docs/governance/TRACEABILITY.md` |
| ADR (Architecture Decision Records) | `docs/adr/` |
| Known Trade-offs | `docs/governance/KNOWN_TRADEOFFS.md` |
