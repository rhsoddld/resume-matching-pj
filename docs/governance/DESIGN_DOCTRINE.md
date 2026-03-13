# DESIGN DOCTRINE — AI Resume Matching System

> 이 문서는 시스템 전반에 적용되는 **설계 원칙과 공학적 신조**를 정의합니다.  
> 새로운 기능을 추가하거나 설계 결정을 내릴 때 이 원칙들을 기준으로 판단합니다.

---

## 1. 핵심 원칙 (Core Principles)

| 원칙 | 정의 | 예시 |
|------|------|------|
| **Separation of Concerns** | API / Service / Repository / Agent 계층은 명확히 분리되어야 한다 | API 라우터에 DB 쿼리 직접 작성 금지 |
| **Graceful Degradation** | 외부 의존성 장애 시 품질은 낮아지되 서비스는 유지되어야 한다 | LLM 장애 → rule-based fallback |
| **Explainability First** | 모든 매칭 결과에는 사람이 이해할 수 있는 설명이 포함되어야 한다 | RankingAgent의 score breakdown + 자연어 explanation |
| **Reproducibility** | 평가 결과는 재현 가능해야 하며, 실험 단위로 추적되어야 한다 | LangSmith run trace + golden_set.jsonl |
| **Schema as Contract** | 모든 데이터 경계(API, Agent I/O, DB)는 Pydantic 스키마로 명시된다 | `Candidate`, `MatchRequest`, `MatchResult` |
| **PII Minimization** | 로그와 trace에 resume 원문이나 개인 식별 정보를 그대로 노출하지 않는다 | 요약/해시/마스킹 처리 |
| **Testability** | 각 레이어는 독립적으로 테스트 가능해야 한다 | Repository mock으로 Service 단위 테스트 |

---

## 2. 아키텍처 원칙

### 2-1. 계층 설계 규칙

| 레이어 | 허용 의존 방향 | 금지 사항 |
|-------|-------------|---------|
| `api/` | → `services/` | 직접 DB/Agent 호출 금지 |
| `services/` | → `repositories/`, `agents/` | 직접 HTTP 클라이언트 금지 |
| `repositories/` | → `core/` (DB 클라이언트) | 비즈니스 로직 금지 |
| `agents/` | → `repositories/` (tool로만) | 직접 API 응답 조작 금지 |
| `core/` | 외부 없음 | 비즈니스 로직 금지 |

### 2-2. Agent 설계 규칙

| 규칙 | 내용 |
|------|------|
| **단일 책임** | 각 Agent는 하나의 평가 차원(Skill / Experience / Technical / Culture)만 담당한다 |
| **도구 기반 데이터 접근** | Agent는 DB를 직접 참조하지 않고 Tool 함수(resolver)를 통해 접근한다 |
| **구조화 출력** | Agent의 출력은 반드시 Pydantic 모델로 파싱되어야 한다 (자유 텍스트 직접 사용 금지) |
| **Idempotent** | 동일 입력에 대해 Agent 실행 결과가 일관되어야 한다 (온도 0 권장) |
| **Fallback 포함** | Agent 실패 시 rule-based 점수로 대체할 수 있어야 한다 |

### 2-3. Normalization 원칙 (Agentic AI 연계 기준)

**핵심 원칙: Ingestion 파싱은 LLM 금지 + 결정론적 규칙 기반**

| 원칙 | 내용 | 적용 대상 |
|------|------|------|
| **Ingestion = rule-based only** | Ingestion 파싱은 regex + spaCy 기반 결정론적 파싱만 수행. 생성형 LLM 호출 금지 | `ingest_resumes.py` |
| **Incremental by hash** | `normalization_hash` / `embedding_hash`를 기준으로 변경분만 upsert/embedding 처리 | `ingest_resumes.py` |
| **스킬 정규화 선행** | `normalized_skills`는 ingestion 시 계산 완료. Agent는 읽기만 함 | SkillMatchingAgent |
| **경력 연수 파생 보장** | `experience_years` / `seniority_level`은 ingestion 시 결정론적으로 계산 | ExperienceEvalAgent |
| **카테고리 통일** | `category`는 두 데이터셋 간 동일한 vocabulary 사용 | 필터링, CultureFitAgent |
| **RAG pipeline fallback** | 구조화 필드(experience_items 등)가 null이면 RAG 컨텍스트에 `raw.resume_text` 포함. Agent가 JD 기준으로 필요한 부분만 판단 | ExperienceEvalAgent, TechnicalEvalAgent |
| **Embedding 단계 분리** | 파싱과 임베딩을 분리 운영. 임베딩 API 호출은 인덱싱 단계로 허용 | Milvus ingestion |
| **ResumeParsingAgent 제외** | 독립 파싱 Agent는 운용하지 않음. 신규 단건 이력서 등록 시에도 동일한 rule-based pipeline 사용 | — |

---

## 3. Fallback 전략 계층

```
LLM 기반 (최고 품질)
  ↓ [LLM/Agent 장애]
임베딩-only 랭킹 + rule-based 스코어
  ↓ [Milvus 장애]
Mongo keyword/text 검색 + category/연차 필터
  ↓ [DB 장애]
API 오류 응답 (503) + request_id 포함 로그
```

---

## 4. 평가 원칙 (Eval Doctrine)

| 원칙 | 내용 |
|------|------|
| **LLM-as-Judge 중심** | DeepEval + OpenAI 모델로 자동 품질 평가 |
| **Golden Set 필수** | 최소 10–15개 `(job_description, expected_candidates)` 쌍을 ground-truth로 유지 |
| **실험 단위 추적** | LangSmith experiment 단위로 파라미터/프롬프트/결과를 추적하여 회귀 분석 가능 |
| **결과 문서화** | 최소 1회 eval 실행 결과를 `docs/eval/eval-results.md`에 기록 |

---

## 5. 보안 / 운영 원칙

| 원칙 | 내용 |
|------|------|
| **입력 검증** | 모든 API 입력은 Pydantic 스키마 통과 필수, 길이 제한 적용 |
| **request_id 전파** | HTTP 헤더 →서비스 로그 → LangSmith trace까지 동일 ID 유지 |
| **Health / Ready 분리** | `/health`(인프라 연결 상태) ≠ `/ready`(인덱싱 완료 등 비즈니스 준비 상태) |
| **환경 변수 격리** | API Key 등 민감 설정은 `.env` + `Settings` Pydantic model로만 관리 |
| **Connection Pooling 기본값** | MongoDB는 pool 설정(`max/min pool`)을 고정하고, Milvus는 alias pool 기반으로 분산 연결 |
| **Cold Start Warmup** | 앱 시작 시 Mongo client/index 초기화 + Milvus collection preload로 첫 검색 지연 최소화 |
