from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from backend.services.skill_ontology import RuntimeSkillOntology
from backend.services.skill_ontology.normalization import clean_token, dedupe_preserve


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "src" / "eval" / "golden_set.jsonl"
DEFAULT_OUTPUT = ROOT / "src" / "eval" / "golden_set.normalized.jsonl"
DEFAULT_REPORT = ROOT / "src" / "eval" / "outputs" / "golden_skill_gap_report.md"


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        rows.append(json.loads(raw))
    return rows


def _normalize_skill_term(skill: object, ontology: RuntimeSkillOntology) -> str | None:
    token = clean_token(skill)
    if not token:
        return None
    return ontology.alias_to_canonical.get(token, token)


def _collect_expected_skills(rows: list[dict[str, Any]], *, include_soft: bool) -> list[str]:
    out: list[str] = []
    for row in rows:
        if not include_soft and bool(row.get("soft_golden", False)):
            continue
        for field in ("expected_skills", "expected_optional_skills"):
            values = row.get(field) or []
            if not isinstance(values, list):
                continue
            out.extend([str(value) for value in values if isinstance(value, str) and value.strip()])
    return out


def _audit(rows: list[dict[str, Any]], ontology: RuntimeSkillOntology, *, include_soft: bool) -> dict[str, Any]:
    raw_terms = _collect_expected_skills(rows, include_soft=include_soft)
    unique_raw = sorted({clean_token(term) for term in raw_terms if clean_token(term)})

    taxonomy_vocab = set(ontology.core_taxonomy.keys())
    alias_vocab = set(ontology.alias_to_canonical.keys())
    canonical_vocab = set(ontology.alias_to_canonical.values())
    known_vocab = taxonomy_vocab.union(alias_vocab).union(canonical_vocab)

    mapped: list[str] = []
    mapped_source_terms: list[str] = []
    unmapped: list[str] = []
    for term in unique_raw:
        canonical = ontology.alias_to_canonical.get(term, term)
        if canonical in known_vocab:
            mapped.append(canonical)
            mapped_source_terms.append(term)
        else:
            unmapped.append(term)

    family_counter: Counter[str] = Counter()
    for row in rows:
        if not include_soft and bool(row.get("soft_golden", False)):
            continue
        family = str(row.get("job_family") or "unknown").strip() or "unknown"
        family_counter[family] += 1

    return {
        "rows": len(rows),
        "rows_effective": sum(1 for row in rows if include_soft or not bool(row.get("soft_golden", False))),
        "unique_expected_skills": len(unique_raw),
        "mapped_unique_skills": len(mapped_source_terms),
        "mapped_unique_canonical_skills": len(set(mapped)),
        "unmapped_unique_skills": len(set(unmapped)),
        "mapped_ratio": round((len(mapped_source_terms) / float(max(1, len(unique_raw)))), 4),
        "unmapped_terms": sorted(set(unmapped)),
        "family_counts": dict(sorted(family_counter.items(), key=lambda item: item[0])),
    }


def _align_skill_list(values: list[object], ontology: RuntimeSkillOntology, *, drop_unknown: bool) -> tuple[list[str], list[str]]:
    aligned: list[str] = []
    unknown: list[str] = []
    known_vocab = set(ontology.core_taxonomy.keys()).union(set(ontology.alias_to_canonical.values()))

    for value in values:
        normalized = _normalize_skill_term(value, ontology)
        if not normalized:
            continue
        if normalized in known_vocab:
            aligned.append(normalized)
            continue
        if drop_unknown:
            unknown.append(normalized)
            continue
        aligned.append(normalized)
        unknown.append(normalized)
    return dedupe_preserve(aligned), dedupe_preserve(unknown)


def _align_rows(
    rows: list[dict[str, Any]],
    ontology: RuntimeSkillOntology,
    *,
    include_soft: bool,
    drop_unknown: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        copied = dict(row)
        if not include_soft and bool(copied.get("soft_golden", False)):
            out.append(copied)
            continue

        required_raw = copied.get("expected_skills") or []
        optional_raw = copied.get("expected_optional_skills") or []
        if not isinstance(required_raw, list):
            required_raw = []
        if not isinstance(optional_raw, list):
            optional_raw = []

        required_aligned, required_unknown = _align_skill_list(required_raw, ontology, drop_unknown=drop_unknown)
        optional_aligned, optional_unknown = _align_skill_list(optional_raw, ontology, drop_unknown=drop_unknown)

        copied["expected_skills"] = required_aligned
        if isinstance(copied.get("expected_optional_skills"), list):
            copied["expected_optional_skills"] = optional_aligned

        unknown_all = dedupe_preserve([*required_unknown, *optional_unknown])
        if unknown_all:
            copied["expected_skills_unmapped"] = unknown_all
        else:
            copied.pop("expected_skills_unmapped", None)
        out.append(copied)
    return out


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Golden Set Skill Gap Report",
        "",
        f"- rows (total): `{payload['rows']}`",
        f"- rows (effective): `{payload['rows_effective']}`",
        f"- unique expected skills: `{payload['unique_expected_skills']}`",
        f"- mapped unique skills: `{payload['mapped_unique_skills']}`",
        f"- mapped unique canonical skills: `{payload['mapped_unique_canonical_skills']}`",
        f"- unmapped unique skills: `{payload['unmapped_unique_skills']}`",
        f"- mapped ratio: `{payload['mapped_ratio']}`",
        "",
        "## Family Coverage",
    ]
    for family, count in payload["family_counts"].items():
        lines.append(f"- `{family}`: `{count}`")
    lines.append("")
    lines.append("## Unmapped Terms")
    if payload["unmapped_terms"]:
        for term in payload["unmapped_terms"]:
            lines.append(f"- `{term}`")
    else:
        lines.append("- (none)")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit/align golden_set skill terms with runtime ontology.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input golden set JSONL path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output aligned golden set JSONL path.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Output markdown report path.")
    parser.add_argument("--mode", choices=["audit", "align", "all"], default="all", help="Execution mode.")
    parser.add_argument("--include-soft", action="store_true", help="Include soft_golden rows in audit/alignment.")
    parser.add_argument(
        "--drop-unknown",
        action="store_true",
        help="Drop skill terms that are still not in ontology after alias normalization.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    report_path = Path(args.report).resolve()

    rows = _load_rows(input_path)
    ontology = RuntimeSkillOntology.load_from_config(ROOT / "config")

    audit_payload = _audit(rows, ontology, include_soft=args.include_soft)
    _write_report(report_path, audit_payload)

    print(
        "[golden-maintenance] "
        f"rows={audit_payload['rows_effective']} "
        f"unique_skills={audit_payload['unique_expected_skills']} "
        f"unmapped={audit_payload['unmapped_unique_skills']} "
        f"mapped_ratio={audit_payload['mapped_ratio']}"
    )
    print(f"[golden-maintenance] report={report_path}")

    if args.mode in {"align", "all"}:
        aligned = _align_rows(
            rows,
            ontology,
            include_soft=args.include_soft,
            drop_unknown=args.drop_unknown,
        )
        _write_rows(output_path, aligned)
        print(f"[golden-maintenance] aligned_output={output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
