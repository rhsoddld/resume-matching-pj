# Resume Matching System

AI-powered Resume Intelligence & Candidate Matching — enter a job description (JD) to get semantic candidate retrieval plus agent-based evaluation, ranking, and explanations.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setup & Usage Instructions](#setup-usage-instructions)
3. [MongoDB & Milvus Setup (Docker)](#mongodb-milvus-setup-docker)
4. [Python Virtual Environment & Install Dependencies](#python-virtual-environment-install-dependencies)
5. [.env Configuration](#env-configuration)
6. [Ingest Data (CLI)](#ingest-data-cli)
7. [Start API Server](#start-api-server)
8. [Get Recommendations](#get-recommendations)
   - [Option A: CLI (curl)](#option-a-cli-curl)
   - [Option B: API Request](#option-b-api-request)
   - [Option C: Web Frontend](#option-c-web-frontend)
9. [Success Criteria Verification](#success-criteria-verification)
10. [Running Tests](#running-tests)
11. [Code Structure & Extensibility](#code-structure-extensibility)
12. [Caching & Performance](#caching-performance)
13. [Documentation Entry Points](#documentation-entry-points)

---

## Prerequisites

- **Python 3.10** — for backend, ingestion, and evaluation scripts
- **Docker & Docker Compose** — for MongoDB, Milvus, backend, and frontend
- **OpenAI API key** — for embeddings, matching, and agent evaluation

---

## Setup & Usage Instructions

Follow the steps below to run the full stack locally.

1. **Install dependencies** — Python venv + `pip install -r requirements.txt`
2. **Start infrastructure** — `docker compose up -d` (MongoDB, Milvus, Backend, Frontend)
3. **Configure environment** — copy `.env.example` to `.env` and set required values such as `OPENAI_API_KEY`
4. **Ingest data** — run `scripts/ingest_resumes.py` to index resumes from MongoDB → Milvus
5. **Open API / frontend** — Backend `http://localhost:8000/docs`, Frontend `http://localhost`

---

## MongoDB & Milvus Setup (Docker)

Bring up the vector DB (Milvus) and document store (MongoDB) together with Docker Compose.

```bash
docker compose up -d --build
```

Services started by Compose:

| Service  | Port   | Purpose |
|----------|--------|------|
| backend  | 8000   | FastAPI API |
| frontend | 80     | React web UI |
| mongodb  | 27017  | Candidate profile storage |
| milvus   | 19530  | Embedding vector search |
| attu     | 3000   | Milvus dashboard (optional) |

**Milvus dashboard:** open `http://localhost:3000` in your browser, then connect to `milvus:19530` (inside the Docker network) or `localhost:19530` (from the host).

---

## Python Virtual Environment & Install Dependencies

We recommend **Python 3.10**. To run ingestion/evaluation scripts locally, create a virtual environment and install dependencies.

```bash
python3.10 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## .env Configuration

Do not commit `.env` (it contains real secrets). Copy `.env.example` to `.env` and fill in values.

```bash
cp .env.example .env
# Edit .env: OPENAI_API_KEY, MONGODB_URI, MILVUS_URI, etc.
```

**Required:**

- `OPENAI_API_KEY` — used for matching/embeddings/agent calls
- `MONGODB_URI` — local example: `mongodb://admin:admin123@localhost:27017/`
- `MILVUS_URI` — local example: `http://localhost:19530`

When running the backend via Docker Compose, you can use `DOCKER_MONGODB_URI` and `DOCKER_MILVUS_URI` with container hostnames (`mongodb`, `milvus`). See `.env.example` comments for full variable descriptions.

**Optional — LangSmith (tracing & observability):**

If you set `LANGSMITH_API_KEY` and `LANGSMITH_ENDPOINT` (and optionally `LANGSMITH_PROJECT`) in `.env`, the app will send traces to LangSmith so you can inspect agent runs, latency, and token usage. Set `LANGSMITH_TRACING=true` to enable. No LangSmith config is required for local development; the system runs without it.

---

## Ingest Data (CLI)

Ingestion loads resume data into MongoDB and creates embeddings to index into Milvus. **This ingestion pipeline is for batch loading; the project does not provide a separate “upload one resume and immediately persist it” realtime registration API.**

```bash
# 1) Source data → MongoDB (parse + normalize) — example with Suri limited to 3000
python3 scripts/ingest_resumes.py --source all --target mongo --suri-limit 3000

# 2) Build Milvus vector index from MongoDB profiles (uses already ingested Mongo data → no --suri-limit needed)
python3 scripts/ingest_resumes.py --source all --target milvus --milvus-from-mongo
```

`--source all` means all default sources defined by this project. For source/target options, see `scripts/ingest_resumes.py` and `src/backend/services/ingest_resumes.py`.

### Test datasets & commands

- **Datasets:**
  - **Location:** `data/` folder at the repo root (CSV).
  - **Sneha:** use the full dataset unless you set a limit.
  - **Suri:** recommended default example is **3000 rows** (`--suri-limit 3000`). Use the option when ingesting a subset.
- **Standard ingestion (Suri 3000 example):**
  ```bash
  python3 scripts/ingest_resumes.py --source all --target mongo --suri-limit 3000
  python3 scripts/ingest_resumes.py --source all --target milvus --milvus-from-mongo
  ```
  (For quick smoke checks only, you can downscale with `--sneha-limit 200 --suri-limit 500`, etc.)
- **Match API smoke test:** use the curl examples under [Get Recommendations](#get-recommendations).
- **Evaluation:** run `./scripts/run_retrieval_eval.sh` or `./scripts/run_eval.sh` (the golden set uses `suri-*` IDs → requires Suri data).

For directory structure and a full command index, see [docs/data-flow/test_datasets_and_commands.md](docs/data-flow/test_datasets_and_commands.md).

---

## Start API Server

**With Docker:** `docker compose up -d` will run the backend on port 8000.

**Backend only (local run):**

```bash
source .venv/bin/activate
cd src/backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: **http://localhost:8000/docs**
- Health: **http://localhost:8000/api/health**

---

## Get Recommendations

### Option A: CLI (curl)

```bash
curl -X POST "http://localhost:8000/api/jobs/match" \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "Backend engineer, 3+ years experience, REST API design experience",
    "top_k": 10
  }'
```

### Option B: API Request

Call the same `POST /api/jobs/match` endpoint from code. The request schema is `JobMatchRequest` (e.g. `job_description`, `top_k`, filter options) and the response is `JobMatchResponse` (e.g. `matches[]`, explainability). The OpenAPI spec is available at `http://localhost:8000/docs`.

### Option C: Web Frontend

Open **http://localhost** (Docker default) or the URL where the frontend is served, enter a JD, and review match results, ranking, and explanations.

---

## Success Criteria Verification

- **Health:** `GET http://localhost:8000/api/health` → 200
- **Ready:** `GET http://localhost:8000/api/ready` → 200 (verifies DB/vector-store connectivity)
- **Match:** verify that using the curl example or the frontend returns a `matches` array plus explainability
- **Eval:** verify that `./scripts/run_eval.sh` completes successfully against the golden set

---

## Running Tests

From the project root (with venv activated and dependencies installed):

```bash
pytest
# or: pytest tests/ -v
```

Tests cover API endpoints, retrieval, scoring, ingestion, and agent flows. For evaluation scripts (golden set, LLM-as-Judge), see [Core Commands](#core-commands-quick-reference) and [docs/data-flow/test_datasets_and_commands.md](docs/data-flow/test_datasets_and_commands.md).

---

## Code Structure & Extensibility

| Path | Description |
|------|------|
| `src/backend/main.py` | FastAPI app + router registration |
| `src/backend/api/` | `candidates`, `jobs`, `ingestion`, `feedback` |
| `src/backend/services/matching_service.py` | Matching orchestration |
| `src/backend/services/candidate_enricher.py` | hit → enrich with Mongo doc + metadata filters |
| `src/backend/agents/` | Multi-agent pipeline (contracts + runtime) |
| `config/` | YAML configs (skill taxonomy, filters, etc.) |
| `docs/CODE_STRUCTURE.md` | Folder structure + extensibility guide |

For changing the embedding model, swapping the vector DB, extending query understanding, etc., see the Extensibility section in [docs/CODE_STRUCTURE.md](docs/CODE_STRUCTURE.md).

---

## Caching & Performance

- **Match result cache:** `src/backend/services/matching/cache.py` — caches `match_jobs` responses using LRU + TTL keyed by JD + parameters.
- **Configuration:** tune `token_cache_*` in `backend.core.settings` (token budget / cache TTL / max size). For trade-offs, see [docs/tradeoffs/design_tradeoffs.md](docs/tradeoffs/design_tradeoffs.md) and [docs/governance/cost_control.md](docs/governance/cost_control.md).

---

## Documentation Entry Points

- **Architecture diagram (single source):** `docs/assets/Architecture.png`
- **Codebase meaning (deep-dive):** [docs/deep-dive/codebase-meaning-reference.md](docs/deep-dive/codebase-meaning-reference.md) — what each directory/file represents (business + technical view)
- **Key Design Decisions:** [docs/design/key-design-decisions.md](docs/design/key-design-decisions.md)
- **Design rationale (ontology, cost, eval):** [docs/design/rationale-ontology-eval-cost.md](docs/design/rationale-ontology-eval-cost.md)
- **Core flows guide:** [docs/guides/codebase-core-flows.md](docs/guides/codebase-core-flows.md)
- **Scoring end-to-end:** [docs/guides/scoring-flow-guide.md](docs/guides/scoring-flow-guide.md)
- **Code Structure & Extensibility:** [docs/CODE_STRUCTURE.md](docs/CODE_STRUCTURE.md)
- **Architecture (includes a one-page Mermaid diagram):** [docs/architecture/system_architecture.md](docs/architecture/system_architecture.md), [docs/architecture/deployment_architecture.md](docs/architecture/deployment_architecture.md)
- **Data flow:** [docs/data-flow/resume_ingestion_flow.md](docs/data-flow/resume_ingestion_flow.md), [docs/data-flow/candidate_retrieval_flow.md](docs/data-flow/candidate_retrieval_flow.md)
- **Test datasets & commands:** [docs/data-flow/test_datasets_and_commands.md](docs/data-flow/test_datasets_and_commands.md)
- **Agent pipeline & scoring:** [docs/agents/multi_agent_pipeline.md](docs/agents/multi_agent_pipeline.md), [docs/agents/agent_evaluation_and_scoring.md](docs/agents/agent_evaluation_and_scoring.md)
- **Evaluation:** [docs/evaluation/evaluation_plan.md](docs/evaluation/evaluation_plan.md), [docs/evaluation/evaluation_results.md](docs/evaluation/evaluation_results.md), [docs/evaluation/golden_set_alignment.md](docs/evaluation/golden_set_alignment.md)
- **Current eval snapshot:** [docs/evaluation/short_eval_status_2026-03-17.md](docs/evaluation/short_eval_status_2026-03-17.md), [docs/evaluation/team_eval_snapshot_2026-03-17.md](docs/evaluation/team_eval_snapshot_2026-03-17.md), [docs/evaluation/next_sprint_checklist_2026-03-17.md](docs/evaluation/next_sprint_checklist_2026-03-17.md)
- **LLM-as-Judge:** [docs/evaluation/llm_judge_design.md](docs/evaluation/llm_judge_design.md)
- **Governance (requirements, traceability, cost, model, prompts):** [docs/governance/ai_governance.md](docs/governance/ai_governance.md), [docs/governance/TRACEABILITY.md](docs/governance/TRACEABILITY.md), [docs/governance/cost_control.md](docs/governance/cost_control.md), [docs/governance/model_policy.md](docs/governance/model_policy.md), [docs/governance/prompt_governance.md](docs/governance/prompt_governance.md)

---

## Core Commands (Quick Reference)

```bash
# Unit/integration tests
pytest

# Ingestion (Suri 3000 example: apply --suri-limit only for the mongo step)
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
├── requirements/          # functional_requirements, case-study
├── docs/                  # architecture, data-flow, agents, evaluation, adr, governance, ...
├── config/                # skill_taxonomy, job_filters, skill_aliases, ...
├── src/
│   ├── backend/           # FastAPI, API, services, agents, repositories
│   ├── frontend/          # React (Vite) + TypeScript
│   └── eval/              # eval_runner, golden set, LLM-as-Judge
├── scripts/               # ingest_resumes.py, run_eval.sh, ...
└── tests/                 # test_api, test_retrieval, test_scoring_service, ...
```
