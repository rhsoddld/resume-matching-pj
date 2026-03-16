from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backend.services.skill_ontology import RuntimeSkillOntology
from eval.golden_set_maintenance import _audit, _load_rows


def test_golden_set_expected_skills_are_covered_by_ontology() -> None:
    root = Path(__file__).resolve().parents[1]
    rows = _load_rows(root / "src" / "eval" / "golden_set.jsonl")
    ontology = RuntimeSkillOntology.load_from_config(root / "config")
    payload = _audit(rows, ontology, include_soft=False)
    assert payload["unmapped_unique_skills"] == 0
