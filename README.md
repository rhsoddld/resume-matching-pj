# AI Resume Matching System

AI-powered Resume Intelligence & Candidate Matching — FastAPI + OpenAI Agents SDK + MongoDB + Milvus

---

## 아키텍처 요약

```
Recruiter UI (React/Vite)
      │
  FastAPI API
      │
  ┌───┴────────────────┐
  │                    │
IngestionService   MatchingService
  │                    │
  ├── MongoDB       HybridRetriever ──── Milvus
  └── Milvus            │
                   OrchestratorAgent
                        │
          ┌─────────────┼──────────────┐
     SkillAgent  ExperienceAgent  TechnicalAgent
                        │
                  RankingAgent → ExplainableScores
```

---

## 기술 스택

| 구분 | 선택 |
|------|------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Agent | OpenAI Agents SDK |
| Embedding | OpenAI `OPENAI_EMBEDDING_MODEL` (default: `text-embedding-3-small`) |
| Vector DB | Milvus |
| Document DB | MongoDB 7 |
| Evaluation | DeepEval + LangSmith |
| Frontend | Vite + React + TypeScript |
| 컨테이너 | Docker Compose |

### Embedding 모델 선택 이유 (`text-embedding-3-small`)

- capstone 범위에서 **비용/응답속도/구현 안정성**을 우선하기 위해 small을 기본값으로 채택했습니다.
- 현재 파이프라인은 deterministic scoring breakdown을 함께 제공하므로, baseline 품질 대비 운영 효율이 중요했습니다.
- 정확도 개선이 필요하면 `OPENAI_EMBEDDING_MODEL` 환경변수만 변경해 `text-embedding-3-large`로 확장할 수 있게 설계했습니다.

---

## 빠른 시작

### 1. 환경 변수 설정

```bash
# .env 파일을 생성/수정하고 OPENAI_API_KEY, MONGODB_URI, MILVUS_URI 등을 설정합니다
```

### 2. 인프라 기동 (MongoDB + Milvus)

```bash
docker-compose up -d mongodb milvus
```

### 3. Python 환경 설정

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Resume 데이터 Ingestion

Kaggle 데이터셋을 `data/` 디렉토리에 배치한 후:

```bash
# Step 1: MongoDB에 적재 (full dataset)
PYTHONPATH=src python src/backend/services/ingest_resumes.py \
  --source all --target mongo --parser-mode hybrid

# Step 2: Milvus에 임베딩 적재 (MongoDB 데이터 활용)
PYTHONPATH=src python src/backend/services/ingest_resumes.py \
  --source all --target milvus --milvus-from-mongo --force-reembed
```

| 옵션 | 설명 |
|------|------|
| `--source` | `sneha` / `suri` / `all` |
| `--target` | `mongo` / `milvus` / `all` |
| `--milvus-from-mongo` | Milvus 적재 시 MongoDB에서 읽음 |
| `--sneha-limit` | Sneha 데이터셋 행 수 제한 |
| `--suri-limit` | Suri 데이터셋 사람 수 제한 |

### Ontology Runtime Config (운영 기준)

Ingestion 런타임은 아래 파일을 최종 기준으로 사용합니다.

- `config/skill_aliases.yml`
- `config/skill_taxonomy.yml`
- `config/skill_role_candidates.yml`
- `config/versioned_skills.yml`
- `config/skill_capability_phrases.yml`
- `config/skill_review_required.yml`

초안/이력 파일은 `docs/ontology/`에 보관합니다.

### Clean Rebuild 가이드 (MongoDB + Milvus)

정규화/스키마/임베딩 버전 변경 후에는 clean rebuild를 권장합니다.

```bash
# 1) Mongo candidates 컬렉션 드롭
mongosh "mongodb://admin:admin123@localhost:27017/resume_matching?authSource=admin" --eval 'db.candidates.drop()'

# 2) Mongo + Milvus 일괄 재적재
PYTHONPATH=src python src/backend/services/ingest_resumes.py \
  --source all --target all \
  --force-mongo-upsert --force-reembed
```

### 5. API 서버 기동

```bash
PYTHONPATH=src uvicorn backend.main:app --reload --port 8000
```

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 발표/심사용 문서

평가자가 먼저 확인할 가능성이 높은 핵심 문서는 아래 기준으로 관리합니다.

| 항목 | 문서 |
|------|------|
| README / 실행 방법 / 폴더 구조 | `README.md` |
| 시스템 아키텍처 | `docs/architecture/system-architecture.md` |
| 데이터 흐름 | `docs/data-flow/ingestion-flow.md` |
| 주요 설계 결정 / trade-off / justification | `docs/adr/DECISIONS.md` |
| 요구사항 추적 / 체크리스트 | `docs/governance/TRACEABILITY.md`, `docs/Reviewer_Checklist.md` |

`docs/adr/DECISIONS.md`에는 구현 중 발생한 핵심 의사결정을 계속 누적 기록합니다.  
특히 아래 항목은 결정이 생길 때마다 바로 남겨두는 것을 기준으로 합니다.

- 아키텍처 선택과 대안 비교
- 데이터 처리 방식과 validation 전략
- 모델/프롬프트/평가 방식 선택 이유
- 비용, 성능, 운영 복잡도 관련 trade-off
- guardrail, fallback, resilience 설계

---

## 데이터셋 구조

`data/` 디렉토리에 아래 구조로 배치합니다:

```
data/
├── snehaanbhawal/
│   └── resume-dataset/
│       └── Resume.csv          # ID, Resume_str, Category
└── suriyaganesh/
    └── resume-dataset-structured/
        ├── 01_people.csv
        ├── 02_abilities.csv
        ├── 03_education.csv
        ├── 04_experience.csv
        └── 05_person_skills.csv
```

---

## 주요 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/ingestion/resumes` | Resume 데이터셋 ingestion 트리거 |
| `POST` | `/api/jobs` | Job 등록 |
| `POST` | `/api/jobs/match` | 매칭 요청 → Top-K 후보 + 점수 + 설명 |
| `GET` | `/api/health` | Mongo·Milvus·OpenAI 상태 체크 |
| `GET` | `/api/ready` | 서비스 준비 상태 확인 |

### 예시 요청 — 매칭

```bash
curl -X POST http://localhost:8000/api/jobs/match \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "We are looking for a senior data scientist with 5+ years of experience in Python, machine learning, and SQL. Experience with cloud platforms (AWS/GCP) preferred.",
    "top_k": 5,
    "filters": {
      "experience_level": "senior",
      "category": "Data Science"
    }
  }'
```

### 예시 응답

> **Note**: 아래는 **현재 구현된 deterministic scoring** 기반의 응답입니다. `Multi-Agent scoring`과 `explanation` 필드는 Phase 2에서 구현 예정입니다.

```json
[
  {
    "candidate_id": "sneha-16852973",
    "category": "INFORMATION-TECHNOLOGY",
    "summary": "Software engineer with 6 years of experience in Python and machine learning.",
    "skills": ["python", "machine learning", "sql", "aws"],
    "core_skills": ["information technology", "python", "machine learning", "sql", "aws"],
    "expanded_skills": ["information technology", "technology", "programming", "python", "backend"],
    "experience_years": 6.5,
    "seniority_level": "senior",
    "score": 0.8240,
    "vector_score": 0.7812,
    "skill_overlap": 0.6500,
    "score_detail": {
      "semantic_similarity": 0.8812,
      "experience_fit": 1.0,
      "seniority_fit": 1.0,
      "category_fit": 0.0
    },
    "skill_overlap_detail": {
      "core_overlap": 0.6667,
      "expanded_overlap": 0.5000,
      "normalized_overlap": 0.6667
    }
  }
]
```

---

## 프로젝트 구조

```
resume-matching-pj/
├── config/                # Skill taxonomy / alias / runtime normalization 설정
├── data/                  # Kaggle 데이터셋 원본 및 적재 입력
├── docs/
│   ├── adr/               # Architecture Decision Records
│   ├── architecture/      # 시스템 아키텍처
│   ├── data-flow/         # 현재 구현된 ingestion flow
│   ├── governance/        # AGENT.md, PLAN.md, TRACEABILITY.md, DESIGN_DOCTRINE.md
│   ├── ontology/          # Ontology 분석/정제 초안 및 버전 이력
│   ├── Reviewer_Checklist.md
│   ├── ingestion_normalization_design.md
│   └── scoring_design.md
├── requirements/          # 문제정의 및 요구사항 문서
├── scripts/               # Ontology 분석/정제 보조 스크립트
├── src/
│   └── backend/
│       ├── api/           # FastAPI 라우터
│       ├── core/          # 설정, DB 클라이언트, startup, vector store
│       ├── repositories/  # Mongo 조회 래퍼
│       ├── schemas/       # Pydantic 모델
│       └── services/      # ingestion, parsing, matching, scoring, ontology
├── tests/                 # pytest 테스트
├── test_api.py            # API 스모크 테스트 스크립트
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── README.md
```

### 현재 구현 상태 메모

- 위 트리는 **현재 저장소에 실제 존재하는 폴더/파일 기준**입니다.
- `src/agents/`, `src/eval/`, `src/frontend/`, `src/ops/`, `docs/eval/`, `.env.example`는 아직 생성되지 않았습니다.
- Multi-Agent, 평가 전용 디렉토리, 프론트엔드 확장은 **Phase 2 이후 목표 범위**로 관리합니다.

---

## 문서 링크

| 문서 | 경로 |
|------|------|
| 요구사항 | [requirements/requirements.md](requirements/requirements.md) |
| 시스템 아키텍처 | [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) |
| Ingestion Flow | [docs/data-flow/ingestion-flow.md](docs/data-flow/ingestion-flow.md) |
| Traceability Matrix | [docs/governance/TRACEABILITY.md](docs/governance/TRACEABILITY.md) |
| Design Doctrine | [docs/governance/DESIGN_DOCTRINE.md](docs/governance/DESIGN_DOCTRINE.md) |
| Design Decision Matrix | [docs/governance/DESIGN_DECISION_MATRIX.md](docs/governance/DESIGN_DECISION_MATRIX.md) |
| Known Trade-offs | [docs/governance/KNOWN_TRADEOFFS.md](docs/governance/KNOWN_TRADEOFFS.md) |
| ADR | [docs/adr/DECISIONS.md](docs/adr/DECISIONS.md) |
| Agent Guide | [docs/governance/AGENT.md](docs/governance/AGENT.md) |
