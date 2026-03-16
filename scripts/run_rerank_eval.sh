#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

DEFAULT_GOLDEN="src/eval/golden_set.normalized.jsonl"
if [[ ! -f "$DEFAULT_GOLDEN" ]]; then
  DEFAULT_GOLDEN="src/eval/golden_set.jsonl"
fi

GOLDEN_SET="${GOLDEN_SET:-$DEFAULT_GOLDEN}"
RUN_LABEL="${RUN_LABEL:-rerank-only}"
OUTPUTS_DIR="${OUTPUTS_DIR:-src/eval/outputs}"

PYTHONPATH=src "$PYTHON_BIN" -m eval.eval_runner \
  --golden-set "$GOLDEN_SET" \
  --mode rerank \
  --run-label "$RUN_LABEL" \
  --outputs-dir "$OUTPUTS_DIR"
