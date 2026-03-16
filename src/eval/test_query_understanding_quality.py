from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
CONFIG = ROOT / "config"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services.job_profile_extractor import build_job_profile
from backend.services.skill_ontology import RuntimeSkillOntology


def _load_cases() -> list[dict]:
    path = ROOT / "src" / "eval" / "query_understanding_golden_set.jsonl"
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _build_ontology() -> RuntimeSkillOntology:
    return RuntimeSkillOntology.load_from_config(CONFIG)


def test_query_understanding_golden_set_release_gate():
    cases = _load_cases()
    assert cases

    ontology = _build_ontology()

    role_hits = 0
    skill_hits = 0
    capability_hits = 0
    role_targets = 0
    skill_targets = 0
    capability_targets = 0
    confidence_hits = 0
    unknown_ratio_hits = 0
    by_family: dict[str, dict[str, int]] = {}

    for case in cases:
        family = (case.get("family") or "unknown").lower()
        by_family.setdefault(family, {"total": 0, "skill_hits": 0, "role_hits": 0})
        by_family[family]["total"] += 1

        profile = build_job_profile(case["job_description"], ontology=ontology)
        got_roles = {r.lower() for r in profile.roles}
        got_skills = {s.lower() for s in profile.required_skills}
        got_capabilities = {c.name.lower() for c in profile.capability_signals}

        exp_roles = {r.lower() for r in case.get("expected_roles", [])}
        exp_skills = {s.lower() for s in case.get("expected_skills", [])}
        exp_caps = {c.lower() for c in case.get("expected_capabilities", [])}

        if exp_roles:
            role_targets += 1
        if exp_roles and got_roles.intersection(exp_roles):
            role_hits += 1
            by_family[family]["role_hits"] += 1
        if exp_skills:
            skill_targets += 1
        if exp_skills and got_skills.intersection(exp_skills):
            skill_hits += 1
            by_family[family]["skill_hits"] += 1
        if exp_caps:
            capability_targets += 1
        if exp_caps and got_capabilities.intersection(exp_caps):
            capability_hits += 1

        max_unknown_ratio = float(case.get("max_unknown_ratio", 0.8))
        min_confidence = float(case.get("min_confidence", 0.5))
        unknown_ratio = float(profile.signal_quality.get("unknown_ratio", 1.0))
        confidence = float(profile.confidence)
        if unknown_ratio <= max_unknown_ratio:
            unknown_ratio_hits += 1
        if confidence >= min_confidence:
            confidence_hits += 1

    total = len(cases)
    assert skill_targets > 0
    assert capability_targets > 0
    assert role_targets > 0
    # Extended golden set now includes harder, production-like JDs derived
    # from strict retrieval golden_set. We keep the gate meaningful but
    # slightly relaxed to reflect the increased difficulty.
    assert skill_hits / skill_targets >= 0.60
    assert capability_hits / capability_targets >= 0.40
    assert role_hits / role_targets >= 0.50
    assert unknown_ratio_hits / total >= 0.90
    assert confidence_hits / total >= 0.90

    # family-level release gate: each family should maintain minimal skill hit quality.
    for family, stats in by_family.items():
        if stats["total"] == 0:
            continue
        assert stats["skill_hits"] / stats["total"] >= 0.40, f"family skill gate failed: {family}"
