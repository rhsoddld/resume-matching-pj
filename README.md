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
./scripts/run_rerank_eval.sh
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

- **Key Design Decisions:** [docs/Key Design Decisions.md](./docs/Key%20Design%20Decisions.md)
- **Code Structure & Extensibility:** [docs/CODE_STRUCTURE.md](./docs/CODE_STRUCTURE.md)
- Architecture: [docs/architecture/system_architecture.md](./docs/architecture/system_architecture.md)
- Deployment: [docs/architecture/deployment_architecture.md](./docs/architecture/deployment_architecture.md)
- Ingestion flow: [docs/data-flow/resume_ingestion_flow.md](./docs/data-flow/resume_ingestion_flow.md)
- Retrieval flow: [docs/data-flow/candidate_retrieval_flow.md](./docs/data-flow/candidate_retrieval_flow.md)
- Agent pipeline: [docs/agents/multi_agent_pipeline.md](./docs/agents/multi_agent_pipeline.md)
- Evaluation: [docs/evaluation/evaluation_plan.md](./docs/evaluation/evaluation_plan.md), [docs/evaluation/evaluation_results.md](./docs/evaluation/evaluation_results.md)
- Golden alignment: [docs/evaluation/golden_set_alignment.md](./docs/evaluation/golden_set_alignment.md)

## Current Eval Snapshot

- Current short-path status: [docs/evaluation/short_eval_status_2026-03-17.md](./docs/evaluation/short_eval_status_2026-03-17.md)
- Team one-pager: [docs/evaluation/team_eval_snapshot_2026-03-17.md](./docs/evaluation/team_eval_snapshot_2026-03-17.md)
- Next sprint checklist: [docs/evaluation/next_sprint_checklist_2026-03-17.md](./docs/evaluation/next_sprint_checklist_2026-03-17.md)
- LLM-as-Judge design: [docs/evaluation/llm_judge_design.md](./docs/evaluation/llm_judge_design.md)
