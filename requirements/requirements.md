# Requirements — AI Resume Matching System

| 항목 | 내용 |
|------|------|
| **Case Study** | AI-Powered Resume Intelligence and Candidate Matching System |
| **Primary Dataset** | Kaggle `snehaanbhawal/resume-dataset` (`ID`, `Resume_str`, `Category`) |
| **User Persona** | Recruiter / Hiring Manager — 자연어 job description으로 빠르게 적합 후보를 찾고 싶어 하는 사용자 |

---

## R1 – Basic Matching (Must)

| ID | 요구사항 | 비고 |
|----|---------|------|
| R1.1 | Resume 텍스트(`Resume_str`)에 대해 임베딩을 생성하고 **Milvus에 인덱싱**해야 한다 | OpenAI embedding 사용 |
| R1.2 | 자연어 job description을 입력으로 받아 임베딩을 만들고 Milvus로 **Top-K 후보 검색** | `top_k` 파라미터 지원 |
| R1.3 | 각 후보에 대해 **기본 매칭 점수** (skill overlap · category match · 경험 연차) 계산 후 정렬 리스트 반환 | rule-based fallback 포함 |
| R1.4 | Category · 최소/최대 경력 연차 등 **기본 메타 필터** 지원 | Milvus 필드 필터 |
| R1.5 | 매칭 결과에 최소 후보의 **category · 핵심 skills 요약 · 총점** 포함 | Pydantic 응답 스키마 |
| R1.6 | job description 입력 및 resume ingestion/매칭 API를 **FastAPI REST 엔드포인트**로 제공 | `/api/jobs/match`, `/api/ingestion/resumes` |

---

## R2 – Advanced Matching & Multi-Agent (Should)

| ID | 요구사항 | 비고 |
|----|---------|------|
| R2.1 | **Multi-Agent 파이프라인** (Agent SDK)으로 skill · experience · technical · culture 측면별 점수 분리 계산 | OpenAI Agents SDK |
| R2.2 | **RankingAgent**가 부분 점수를 가중 합산하여 최종 점수 + explanation 생성 | 설명 가능한 점수 |
| R2.3 | **Hybrid retrieval** (벡터 + 메타데이터 필터), Milvus 장애 시 Mongo 텍스트 검색으로 **fallback** | graceful degradation |
| R2.4 | **RecruiterAgent ↔ HiringManagerAgent A2A** 상호작용으로 일부 가중치 조정 가능 | culture fit 비중 상향 등 |

---

## R3 – Evaluation & Observability (Should)

| ID | 요구사항 | 비고 |
|----|---------|------|
| R3.1 | **DeepEval + LLM-as-Judge**로 matching quality 자동 평가 | skill coverage · relevance metric |
| R3.2 | **LangSmith**로 evaluation run / experiment / dataset 추적 | 재현성·회귀 분석 |
| R3.3 | **golden_set.jsonl** 정의 (최소 10–15개 job description + 기대 candidate 라벨) | ground-truth set |
| R3.4 | 최소 1회 이상 eval 실행 결과를 **`docs/eval/eval-results.md`** 에 문서화 | 실증 증거 |
| R3.5 | **구조화 JSON 로그**, health/ready 엔드포인트, latency/throughput 지표 제공 | `request_id` 포함 |

---

## R4 – Frontend Demo (Should)

| ID | 요구사항 | 비고 |
|----|---------|------|
| R4.1 | **React/Vite 단일 페이지 UI** — job description 입력 + 매칭 결과 조회 | `src/frontend/` |
| R4.2 | UI — 후보 리스트 + 점수 breakdown + explanation을 **표/패널** 형태로 표시 | Score 4-way breakdown |
| R4.3 | API 스키마 ↔ UI 동작 ↔ README/아키텍처 문서 **일관성 유지** | traceability |

---

## R5 – Documentation & Handoff (Must)

| ID | 요구사항 | 비고 |
|----|---------|------|
| R5.1 | **README** — 설치 · 실행 · ingestion · 예시 요청/응답 포함 | `README.md` |
| R5.2 | **아키텍처/데이터플로우/에이전트 파이프라인 다이어그램** 제공 | Mermaid 포함 |
| R5.3 | **TRACEABILITY 매트릭스** — 요구사항 ID ↔ 코드/테스트/평가/문서 링크 | `docs/governance/TRACEABILITY.md` |
| R5.4 | **Reviewer Checklist (Senior+)** self-review 결과 + 남은 backlog 명시 | `TRACEABILITY.md §4` |

---

## 우선순위 요약

| Priority | 요구사항 IDs |
|----------|------------|
| **Must** | R1.1 – R1.6 · R5.1 – R5.4 |
| **Should** | R2.1 – R2.4 · R3.1 – R3.5 · R4.1 – R4.3 |
| **Nice-to-have** | Bias detection guardrails · Advanced analytics dashboard · Feedback loop · 추가 데이터셋 통합 |
