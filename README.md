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
| Embedding | OpenAI `text-embedding-3-small` |
| Vector DB | Milvus |
| Document DB | MongoDB 7 |
| Evaluation | DeepEval + LangSmith |
| Frontend | Vite + React + TypeScript |
| 컨테이너 | Docker Compose |

---

## 빠른 시작

### 1. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY, LANGSMITH_API_KEY 등을 설정합니다
```

### 2. 인프라 기동 (MongoDB + Milvus)

```bash
docker-compose up -d mongodb milvus
```

### 3. Python 환경 설정

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Resume 데이터 Ingestion

Kaggle 데이터셋을 `data/` 디렉토리에 배치한 후:

```bash
# Step 1: MongoDB에 먼저 적재
PYTHONPATH=src python src/backend/services/ingest_resumes.py \
  --source all --target mongo \
  --sneha-limit 200 --suri-limit 500

# Step 2: Milvus에 임베딩 적재 (MongoDB 데이터 활용)
PYTHONPATH=src python src/backend/services/ingest_resumes.py \
  --source all --target milvus --milvus-from-mongo \
  --sneha-limit 200 --suri-limit 500
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

```json
{
  "job_id": "job-abc123",
  "candidates": [
    {
      "candidate_id": "sneha-16852973",
      "category": "Data Science",
      "skills": ["Python", "Machine Learning", "SQL", "AWS"],
      "experience_years": 6.5,
      "seniority_level": "senior",
      "scores": {
        "skill_score": 0.87,
        "experience_score": 0.82,
        "technical_score": 0.79,
        "culture_score": 0.71,
        "final_score": 0.81
      },
      "explanation": "Strong Python and ML background with 6+ years of data science experience. AWS experience aligns well with the cloud requirement."
    }
  ],
  "pipeline_version": "v1",
  "trace_id": "req-xyz789"
}
```

---

## 프로젝트 구조

```
resume-matching-pj/
├── src/
│   ├── backend/
│   │   ├── api/           # FastAPI 라우터
│   │   ├── services/      # 도메인 서비스
│   │   ├── repositories/  # DB/벡터스토어 CRUD
│   │   ├── schemas/       # Pydantic 모델
│   │   └── core/          # 설정, 로깅, DB 클라이언트
│   ├── agents/            # OpenAI Agents SDK Multi-Agent
│   ├── eval/              # DeepEval 테스트, golden set
│   ├── frontend/          # Vite + React UI
│   └── ops/               # LangSmith tracer, 로깅 미들웨어
├── docs/
│   ├── architecture/      # 시스템 아키텍처
│   ├── data-flow/         # Ingestion / Retrieval / Agent 플로우
│   ├── eval/              # Eval plan, rubric, results
│   ├── governance/        # AGENT.md, TRACEABILITY.md, DESIGN_DOCTRINE.md
│   └── adr/               # Architecture Decision Records
├── tests/                 # pytest 테스트
├── requirements/          # 요구사항 문서
├── data/                  # Kaggle 데이터셋 (gitignore)
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

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
| ADR | [docs/adr/DECISIONS.md](docs/adr/DECISIONS.md) |
| Agent Guide | [docs/governance/AGENT.md](docs/governance/AGENT.md) |
