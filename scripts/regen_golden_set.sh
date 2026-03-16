#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

PYTHONPATH=src "$PYTHON_BIN" -m eval.regen_golden_set \
  --input src/eval/golden_set.jsonl \
  --output src/eval/golden_set.jsonl \
  --top-k 60 \
  --max-golden 5 \
  --min-candidates 2 \
  --min-required-overlap 0.4 \
  --relaxed-required-overlap 0.25 \
  --relaxed-min-quality 0.24
