#!/usr/bin/env python3
"""Wrapper entrypoint for ingestion pipeline.

Usage:
  python3 scripts/ingest_resumes.py --source all --target mongo
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

TARGET = ROOT / "src" / "backend" / "services" / "ingest_resumes.py"
runpy.run_path(str(TARGET), run_name="__main__")
