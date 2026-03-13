# DESIGN DECISION MATRIX — AI Resume Matching System

> 주요 기술 선택에 대한 **대안 비교 및 최종 결정 이유**를 기록합니다.  
> 변경이 필요하면 ADR(`docs/adr/`)을 새로 작성하고 이 매트릭스를 업데이트합니다.

---

## 1. Backend Framework

| 항목 | FastAPI ✅ | Flask | Django REST |
|------|-----------|-------|------------|
| 비동기 지원 | native async/await | 제한적 | 별도 설정 필요 |
| 자동 OpenAPI 문서 | ✅ 내장 | ❌ | 별도 패키지 |
| Pydantic 통합 | ✅ 네이티브 | ❌ | ❌ |
| 성능 | 높음 | 중간 | 중간 |
| **선택 이유** | Pydantic schema-first 설계와 자동 API 문서화가 FDE 스타일 결과물에 최적 | — | — |

---

## 2. Vector Store

| 항목 | Milvus ✅ | Chroma | FAISS | Pinecone |
|------|-----------|--------|-------|---------|
| 프로덕션 수준 | ✅ | 개발용 | 개발용 | 관리형 |
| 메타데이터 필터 | ✅ 강력 | 제한적 | ❌ | ✅ |
| Self-hosted | ✅ | ✅ | ✅ | ❌ |
| Docker 지원 | ✅ | ✅ | ❌ | ❌ |
| Hybrid search | ✅ | 제한 | ❌ | ✅ |
| **선택 이유** | Hybrid search + category/연차 메타 필터를 동시에 지원, Docker Compose로 로컬 환경 일치. Abstraction layer로 Chroma/FAISS 교체 가능하게 설계 | — | — | — |

---

## 2-1. Retrieval / Rerank Baseline (고정안)

| 항목 | 선택안 ✅ | 대안 | 판단 근거 |
|------|----------|------|---------|
| Embedding model | `text-embedding-3-small` | `text-embedding-3-large` | capstone 범위에서 비용/속도/구현 단순성 우선 |
| Lexical retrieval | BM25 skill search | 벡터 검색 단독 | exact skill 매칭 보완 |
| Rerank model | `gpt-4o-mini` | 별도 cross-encoder reranker | 설명 생성(explanation)과 연계가 쉬움 |

**Current baseline pipeline (fixed)**  
`Job Description` → `OpenAI embedding (text-embedding-3-small)` → `Milvus vector search` → `BM25 skill search` → `Hybrid merge` → `Top 30` → `Feature extraction` → `Deterministic scoring` → `Top 10` → `LLM rerank (gpt-4o-mini)` → `Top 5 candidates`

현재 프로젝트는 capstone 범위와 개발 속도를 고려해 `text-embedding-3-small`을 기본 embedding 모델로 사용한다.  
이 선택은 비용, 속도, 구현 단순성을 우선한 결정이다.  
정확도 개선이 필요하면 향후 `text-embedding-3-large` 또는 별도 reranker 강화로 확장할 수 있다.

---

## 2-2. Deterministic Scoring Feature Priorities (Mongo 데이터 근거)

| 계층 | Feature | 정책 |
|------|---------|------|
| Core (high trust) | `semantic_similarity`, `skill_overlap`, `experience_fit` | 기본 점수의 중심 신호로 사용 |
| Weak support | `seniority_fit` | label skew를 고려해 낮은 가중치로만 반영 |
| Conditional bonus | `category_fit` | `JD.category`와 `candidate.category`가 모두 존재할 때만 반영 |
| Conditional bonus | `education_fit` | JD에 학위 요구가 있을 때만 반영 |
| Conditional bonus | `recency_fit` | date 기반의 light heuristic만 반영 |

**Current deterministic formula (recommended)**  
`score = 0.42 * semantic_similarity + 0.33 * skill_overlap + 0.18 * experience_fit + 0.07 * seniority_fit + category_fit_conditional + education_fit_bonus + recency_fit_light`

설계 원칙:
- Vector similarity + BM25는 recall-oriented retrieval에 사용
- Deterministic scoring은 explainable initial ranking을 담당
- LLM rerank는 final ranking refinement + reasoning 생성을 담당

---

## 3. Document Store

| 항목 | MongoDB ✅ | PostgreSQL | Elasticsearch |
|------|-----------|-----------|--------------|
| 스키마 유연성 | ✅ (JSON 네이티브) | 제한적 | ✅ |
| 풀텍스트 검색 | 기본 제공 | pg_trgm 필요 | ✅ 강력 |
| Milvus fallback 검색 | ✅ 적합 | 가능 | 더 적합 |
| 도메인 모델 표현 | ✅ 중첩 구조 자연스러움 | 정규화 필요 | ✅ |
| **선택 이유** | Resume의 가변 구조(경력 수, 학력 수 불규칙)를 중첩 JSON으로 자연스럽게 표현. Milvus 장애 시 text/keyword fallback 검색도 지원 | — | — |

---

## 4. Agent Framework

| 항목 | OpenAI Agents SDK ✅ | LangChain | Custom |
|------|---------------------|-----------|--------|
| A2A 지원 | ✅ 내장 | 별도 구성 | 직접 구현 |
| Structured output | ✅ Pydantic 통합 | 가능 | 직접 구현 |
| Tool 기반 DB 접근 | ✅ | ✅ | 직접 구현 |
| Orchestration 내장 | ✅ | ✅ | ❌ |
| LangSmith 연계 | 가능 | ✅ 네이티브 | ❌ |
| **선택 이유** | Orchestrator→Sub-agent 패턴과 A2A(Recruiter↔HiringManager)를 SDK 표준 방식으로 구현 가능. Pydantic 구조화 출력 기본 지원 | — | — |

---

## 5. Evaluation Framework

| 항목 | DeepEval + LangSmith ✅ | RAGAS | 자체 평가 스크립트 |
|------|------------------------|-------|----------------|
| LLM-as-Judge | ✅ | ✅ | 직접 구현 |
| 실험 추적 | LangSmith ✅ | ❌ | ❌ |
| Golden set 관리 | ✅ | ✅ | 직접 구현 |
| 커스텀 메트릭 | ✅ | 제한 | ✅ |
| **선택 이유** | DeepEval은 LLM-as-Judge 커스텀 metric 정의가 유연하고, LangSmith는 run/experiment/dataset 추적으로 재현성과 회귀 분석을 동시에 지원 | — | — |

---

## 6. Normalization Strategy (Agentic AI 연계)

| 항목 | 현재 선택 ✅ | 대안 A: Agent-side 파싱 | 대안 B: 온디맨드 파싱 |
|------|-----------|----------------------|-------------------|
| 시점 | **Ingestion 시 1회 계산** | 매칭 요청 시 Agent가 파싱 | API 요청마다 파싱 |
| 지연 시간 | 낮음 (캐시됨) | 높음 (매번 LLM 호출) | 높음 |
| 품질 | 규칙 기반 (결정론적) | LLM 기반 (확률적) | 혼합 |
| 비용 | 낮음 | 높음 | 가변 |
| Agent 의존성 | 없음 (정제된 필드 제공) | 높음 | 중간 |
| **선택 이유** | Ingestion 시 정규화된 필드(skills, experience_years, seniority)를 미리 계산하여 Agent에게 clean context를 제공. **Substring matching** 도입으로 비정형 스킬 매핑 극대화(empty 0.5% 달성), **Category injection**으로 데이터 편중 보완. | — | — |

---

## 7. Frontend

| 항목 | Vite + React + TypeScript ✅ | Next.js | Plain HTML |
|------|------------------------------|---------|-----------|
| 개발 속도 | 빠름 (HMR) | 빠름 | 빠름 |
| SSR 필요 | ❌ (데모용) | ✅ | ❌ |
| 복잡도 | 낮음 | 높음 | 매우 낮음 |
| 타입 안전성 | ✅ TypeScript | ✅ | ❌ |
| **선택 이유** | 데모용 최소 UI이므로 SSR 불필요. Vite의 빠른 개발 환경과 TypeScript 타입 안전성으로 API 스키마 일관성 유지 | — | — |
