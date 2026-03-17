# Resume Matching System

AI-powered Resume Intelligence & Candidate Matching — JD를 입력하면 의미 기반 후보 검색과 에이전트 기반 평가·순위·설명을 제공합니다.

---

## Table of Contents

1. [Setup & Usage Instructions](#setup--usage-instructions)
2. [MongoDB & Milvus Setup (Docker)](#mongodb--milvus-setup-docker)
3. [Python Virtual Environment & Install Dependencies](#python-virtual-environment--install-dependencies)
4. [.env Configuration](#env-configuration)
5. [Ingest Data (CLI)](#ingest-data-cli)
6. [Start API Server](#start-api-server)
7. [Get Recommendations](#get-recommendations)
   - [Option A: CLI (curl)](#option-a-cli-curl)
   - [Option B: API Request](#option-b-api-request)
   - [Option C: Web Frontend](#option-c-web-frontend)
8. [Success Criteria Verification](#success-criteria-verification)
9. [Code Structure & Extensibility](#code-structure--extensibility)
10. [Caching & Performance](#caching--performance)
11. [Documentation Entry Points](#documentation-entry-points)

---

## Setup & Usage Instructions

아래 순서대로 진행하면 로컬에서 전체 스택을 실행할 수 있습니다.

1. **의존성 설치** — Python venv + `pip install -r requirements.txt`
2. **인프라 기동** — `docker compose up -d` (MongoDB, Milvus, Backend, Frontend)
3. **환경 변수** — `.env.example`을 복사해 `.env`를 만들고 `OPENAI_API_KEY` 등 필수 값 설정
4. **데이터 적재** — `scripts/ingest_resumes.py`로 이력서를 MongoDB → Milvus 인덱싱
5. **API/프론트 접속** — Backend `http://localhost:8000/docs`, Frontend `http://localhost`

---

## MongoDB & Milvus Setup (Docker)

벡터 DB(Milvus)와 문서 저장소(MongoDB)는 Docker Compose로 한 번에 띄웁니다.

```bash
docker compose up -d --build
```

기동되는 서비스:

| 서비스   | 포트   | 용도 |
|----------|--------|------|
| backend  | 8000   | FastAPI API |
| frontend | 80     | React 웹 UI |
| mongodb  | 27017  | 후보 프로필 저장 |
| milvus   | 19530  | 임베딩 벡터 검색 |
| attu     | 3000   | Milvus 대시보드 (선택) |

**Milvus 대시보드 확인:** 브라우저에서 `http://localhost:3000` 접속 후, 연결 주소 `milvus:19530`(컨테이너 내부) 또는 호스트에서 직접 연동 시 `localhost:19530` 사용.

---

## Python Virtual Environment & Install Dependencies

**Python 3.10** 사용을 권장합니다. 로컬에서 ingestion/평가 스크립트를 돌리려면 가상환경과 의존성이 필요합니다.

```bash
python3.10 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## .env Configuration

실제 시크릿이 들어가는 `.env`는 저장소에 올리지 마세요. `.env.example`을 복사해 `.env`를 만든 뒤 값을 채웁니다.

```bash
cp .env.example .env
# .env 편집: OPENAI_API_KEY, MONGODB_URI, MILVUS_URI 등
```

**필수:**

- `OPENAI_API_KEY` — 매칭/임베딩/에이전트 호출에 사용
- `MONGODB_URI` — 로컬: `mongodb://admin:admin123@localhost:27017/`
- `MILVUS_URI` — 로컬: `http://localhost:19530`

Docker Compose로 백엔드를 띄울 때는 `DOCKER_MONGODB_URI`, `DOCKER_MILVUS_URI`로 컨테이너 내부 호스트명(`mongodb`, `milvus`)을 사용할 수 있습니다. 자세한 변수 설명은 `.env.example` 주석을 참고하세요.

---

## Ingest Data (CLI)

이력서 데이터를 MongoDB에 넣고, 임베딩을 생성해 Milvus에 인덱싱합니다. **Ingestion은 배치 적재용이며, 사용자가 이력서 1건을 올려 곧바로 DB에 반영하는 리얼타임 등록 API는 별도로 제공하지 않는다.**

```bash
# 1) 소스 데이터 → MongoDB (파싱·정규화) — Suri 3000건 제한 예시
python3 scripts/ingest_resumes.py --source all --target mongo --suri-limit 3000

# 2) MongoDB 프로필 기준으로 Milvus 벡터 인덱스 생성 (Mongo에 이미 적재된 데이터 사용 → --suri-limit 불필요)
python3 scripts/ingest_resumes.py --source all --target milvus --milvus-from-mongo
```

`--source all`은 프로젝트에서 정의한 기본 소스 전체를 의미합니다. 소스/타겟 옵션은 `scripts/ingest_resumes.py` 및 `src/backend/services/ingest_resumes.py`를 참고하세요.

### 테스트용 데이터셋 & 커맨드

- **데이터셋:**
  - **위치:** 프로젝트 루트의 `data/` 폴더 (CSV).
  - **Sneha:** 별도 limit 없으면 전체 사용.
  - **Suri:** **3000건**을 권장·기본 예시로 사용 (`--suri-limit 3000`). 전체가 아닌 일부만 적재할 때 이 옵션을 명시합니다.
- **표준 ingestion (Suri 3000건 예시):**
  ```bash
  python3 scripts/ingest_resumes.py --source all --target mongo --suri-limit 3000
  python3 scripts/ingest_resumes.py --source all --target milvus --milvus-from-mongo
  ```
  (빠른 검증 시에만 `--sneha-limit 200 --suri-limit 500` 등으로 건수 조절 가능.)
- **매칭 API 테스트:** 아래 [Get Recommendations](#get-recommendations) curl 예시 사용.
- **평가 테스트:** `./scripts/run_retrieval_eval.sh` 또는 `./scripts/run_eval.sh` (golden set은 `suri-*` ID 사용 → Suri 데이터 필요).

자세한 디렉터리 구조·전체 커맨드 정리는 [docs/data-flow/test_datasets_and_commands.md](docs/data-flow/test_datasets_and_commands.md) 참고.

---

## Start API Server

**Docker 사용 시:** `docker compose up -d` 만 하면 backend가 8000 포트에서 동작합니다.

**로컬에서만 백엔드 실행 시:**

```bash
source .venv/bin/activate
cd src/backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API 문서: **http://localhost:8000/docs**
- Health: **http://localhost:8000/api/health**

---

## Get Recommendations

### Option A: CLI (curl)

```bash
curl -X POST "http://localhost:8000/api/jobs/match" \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "백엔드 개발자, 3년 이상 경력, REST API 설계 경험",
    "top_k": 10
  }'
```

### Option B: API Request

동일한 `POST /api/jobs/match` 엔드포인트를 코드에서 호출합니다. 요청 스키마는 `JobMatchRequest` (예: `job_description`, `top_k`, 필터 옵션), 응답은 `JobMatchResponse` (예: `matches[]`, explainability)입니다. OpenAPI 스펙은 `http://localhost:8000/docs`에서 확인할 수 있습니다.

### Option C: Web Frontend

브라우저에서 **http://localhost** (Docker 기준) 또는 프론트엔드가 서빙되는 URL로 접속한 뒤, JD를 입력하고 매칭 결과·순위·설명을 확인합니다.

---

## Success Criteria Verification

- **Health:** `GET http://localhost:8000/api/health` → 200
- **Ready:** `GET http://localhost:8000/api/ready` → 200 (DB/벡터 스토어 연결 확인)
- **Match:** 위 curl 또는 프론트에서 JD 입력 시 `matches` 배열과 explainability가 내려오는지 확인
- **Eval:** `./scripts/run_eval.sh` 실행 시 golden set 기준 평가가 완료되는지 확인

---

## Code Structure & Extensibility

| 경로 | 설명 |
|------|------|
| `src/backend/main.py` | FastAPI 앱, 라우터 등록 |
| `src/backend/api/` | `candidates`, `jobs`, `ingestion`, `feedback` |
| `src/backend/services/matching_service.py` | 매칭 오케스트레이션 |
| `src/backend/services/candidate_enricher.py` | hit → Mongo 문서 보강·메타 필터 |
| `src/backend/agents/` | Multi-agent 파이프라인 (contracts + runtime) |
| `config/` | 스킬 택소노미, 필터 옵션 등 YAML |
| `docs/CODE_STRUCTURE.md` | 폴더 구조·확장 가이드 상세 |

임베딩 모델 변경, Vector DB 교체, Query Understanding 확장 등은 [docs/CODE_STRUCTURE.md](docs/CODE_STRUCTURE.md)의 Extensibility 섹션을 참고하세요.

---

## Caching & Performance

- **매칭 결과 캐시:** `src/backend/services/matching/cache.py` — JD + 파라미터 기준 LRU + TTL로 `match_jobs` 응답 캐싱.
- **설정:** `backend.core.settings`의 `token_cache_*` (토큰 예산/캐시 TTL/최대 크기)로 제어 가능합니다. 자세한 트레이드오프는 [docs/tradeoffs/design_tradeoffs.md](docs/tradeoffs/design_tradeoffs.md), [docs/governance/cost_control.md](docs/governance/cost_control.md)를 참고하세요.

---

## Documentation Entry Points

- **Key Design Decisions:** [docs/Key Design Decisions.md](docs/Key%20Design%20Decisions.md)
- **Design rationale (ontology, cost, eval):** [docs/design_rationale_ontology_eval_cost.md](docs/design_rationale_ontology_eval_cost.md)
- **Code Structure & Extensibility:** [docs/CODE_STRUCTURE.md](docs/CODE_STRUCTURE.md)
- **Architecture:** [docs/architecture/system_architecture.md](docs/architecture/system_architecture.md), [docs/architecture/deployment_architecture.md](docs/architecture/deployment_architecture.md)
- **Data flow:** [docs/data-flow/resume_ingestion_flow.md](docs/data-flow/resume_ingestion_flow.md), [docs/data-flow/candidate_retrieval_flow.md](docs/data-flow/candidate_retrieval_flow.md)
- **테스트용 데이터셋 & 커맨드:** [docs/data-flow/test_datasets_and_commands.md](docs/data-flow/test_datasets_and_commands.md)
- **Agent pipeline & scoring:** [docs/agents/multi_agent_pipeline.md](docs/agents/multi_agent_pipeline.md), [docs/agents/agent_evaluation_and_scoring.md](docs/agents/agent_evaluation_and_scoring.md)
- **Evaluation:** [docs/evaluation/evaluation_plan.md](docs/evaluation/evaluation_plan.md), [docs/evaluation/evaluation_results.md](docs/evaluation/evaluation_results.md), [docs/evaluation/golden_set_alignment.md](docs/evaluation/golden_set_alignment.md)
- **Current eval snapshot:** [docs/evaluation/short_eval_status_2026-03-17.md](docs/evaluation/short_eval_status_2026-03-17.md), [docs/evaluation/team_eval_snapshot_2026-03-17.md](docs/evaluation/team_eval_snapshot_2026-03-17.md), [docs/evaluation/next_sprint_checklist_2026-03-17.md](docs/evaluation/next_sprint_checklist_2026-03-17.md)
- **LLM-as-Judge:** [docs/evaluation/llm_judge_design.md](docs/evaluation/llm_judge_design.md)

---

## Core Commands (Quick Reference)

```bash
# Ingestion (Suri 3000건 예시: mongo 단계에만 --suri-limit 적용)
python3 scripts/ingest_resumes.py --source all --target mongo --suri-limit 3000
python3 scripts/ingest_resumes.py --source all --target milvus --milvus-from-mongo

# Evaluation
./scripts/run_eval.sh
./scripts/run_retrieval_eval.sh
./scripts/run_rerank_eval.sh
./scripts/update_golden_set.sh
./scripts/regen_golden_set.sh
```

---

## Repository Structure (High-Level)

```text
resume-matching-pj/
├── README.md
├── .env.example
├── requirements.txt
├── docker-compose.yml
├── requirements/          # problem_definition, functional_requirements, traceability_matrix
├── docs/                  # architecture, data-flow, agents, evaluation, adr, governance, ...
├── config/                # skill_taxonomy, job_filters, skill_aliases, ...
├── src/
│   ├── backend/           # FastAPI, API, services, agents, repositories
│   ├── frontend/          # React (Vite) + TypeScript
│   └── eval/              # eval_runner, golden set, LLM-as-Judge
├── scripts/               # ingest_resumes.py, run_eval.sh, ...
└── tests/                 # test_api, test_retrieval, test_scoring_service, ...
```
