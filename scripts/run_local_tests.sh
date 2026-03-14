#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo ".venv not found. Create it first: python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate

python -m pytest -q tests/test_job_profile_extractor.py tests/test_retrieval_fallback.py tests/test_ranking_policy.py tests/test_skill_overlap_scoring.py tests/test_query_fallback_policy.py tests/test_rerank_pipeline.py
python -m pytest -q src/eval/test_query_understanding_quality.py
