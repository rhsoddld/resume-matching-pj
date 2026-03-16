#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

PYTHONPATH=src "$PYTHON_BIN" -m eval.golden_set_maintenance \
  --mode all \
  --input src/eval/golden_set.jsonl \
  --output src/eval/golden_set.normalized.jsonl \
  --report src/eval/outputs/golden_skill_gap_report.md
