#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo ".venv not found. Create it first: python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate

MODE="${1:-full}"

case "${MODE}" in
  smoke)
    python3 -m pytest -q \
      tests/test_job_profile_extractor.py \
      tests/test_retrieval_fallback.py \
      tests/test_ranking_policy.py \
      tests/test_skill_overlap_scoring.py \
      tests/test_query_fallback_policy.py \
      tests/test_rerank_pipeline.py \
      tests/test_matching_service_fairness.py \
      tests/test_api_endpoints.py \
      src/eval/test_query_understanding_quality.py
    ;;
  full)
    python3 -m pytest -q
    ;;
  eval)
    ./scripts/run_deepeval.sh "${2:-src/eval}"
    ;;
  *)
    echo "Unknown mode: ${MODE}"
    echo "Usage: ./scripts/run_local_tests.sh [smoke|full|eval] [eval_target]"
    exit 1
    ;;
esac
