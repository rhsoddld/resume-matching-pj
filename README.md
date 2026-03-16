# resume-matching-system

AI-powered Resume Intelligence & Candidate Matching system.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d --build
```

- Frontend: `http://localhost`
- Backend: `http://localhost:8000/docs`

## Core Commands

```bash
# Ingestion
python3 scripts/ingest_resumes.py --source all --target mongo
python3 scripts/ingest_resumes.py --source all --target milvus --milvus-from-mongo

# Evaluation
./scripts/run_eval.sh
./scripts/run_retrieval_eval.sh
./scripts/update_golden_set.sh
./scripts/regen_golden_set.sh
```

## Repository Structure

```text
resume-matching-system/
├── README.md
├── requirements/
│   ├── problem_definition.md
│   ├── functional_requirements.md
│   └── traceability_matrix.md
├── docs/
│   ├── architecture/
│   ├── data-flow/
│   ├── agents/
│   ├── evaluation/
│   ├── observability/
│   ├── security/
│   ├── governance/
│   ├── tradeoffs/
│   └── adr/
├── src/
│   ├── backend/
│   └── eval/
├── scripts/
│   ├── ingest_resumes.py
│   └── run_eval.sh
└── tests/
    ├── test_api.py
    └── test_retrieval.py
```

## Documentation Entry Points

- Architecture: [docs/architecture/system_architecture.md](/Users/lee/Desktop/resume-matching-pj/docs/architecture/system_architecture.md)
- Deployment: [docs/architecture/deployment_architecture.md](/Users/lee/Desktop/resume-matching-pj/docs/architecture/deployment_architecture.md)
- Ingestion flow: [docs/data-flow/resume_ingestion_flow.md](/Users/lee/Desktop/resume-matching-pj/docs/data-flow/resume_ingestion_flow.md)
- Retrieval flow: [docs/data-flow/candidate_retrieval_flow.md](/Users/lee/Desktop/resume-matching-pj/docs/data-flow/candidate_retrieval_flow.md)
- Agent pipeline: [docs/agents/multi_agent_pipeline.md](/Users/lee/Desktop/resume-matching-pj/docs/agents/multi_agent_pipeline.md)
- Evaluation: [docs/evaluation/evaluation_plan.md](/Users/lee/Desktop/resume-matching-pj/docs/evaluation/evaluation_plan.md), [docs/evaluation/evaluation_results.md](/Users/lee/Desktop/resume-matching-pj/docs/evaluation/evaluation_results.md)
- Golden alignment: [docs/evaluation/golden_set_alignment.md](/Users/lee/Desktop/resume-matching-pj/docs/evaluation/golden_set_alignment.md)
