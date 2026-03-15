#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo ".venv not found. Create it first: python3 -m venv .venv"
  exit 1
fi

source .venv/bin/activate

# Load project env if present so OPENAI_API_KEY / CONFIDENT_API_KEY are picked up.
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is required for LLM-as-Judge metrics."
  echo "Set it in .env (or export it) and run again."
  exit 1
fi

if [[ -z "${CONFIDENT_API_KEY:-}" ]]; then
  echo "CONFIDENT_API_KEY is not set. Running DeepEval in local-only mode (no Confident AI upload)."
else
  echo "CONFIDENT_API_KEY detected. Results will be logged to Confident AI."
fi

IDENTIFIER="${DEEPEVAL_IDENTIFIER:-resume-matching-$(date +%Y%m%d-%H%M%S)}"
TARGET="${1:-src/eval}"

echo "Running: deepeval test run ${TARGET} -id ${IDENTIFIER}"
deepeval test run "${TARGET}" -id "${IDENTIFIER}"
