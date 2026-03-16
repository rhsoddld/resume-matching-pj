from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.eval_adapter import MatchPipelineAdapter
from backend.services.skill_ontology import RuntimeSkillOntology
from backend.services.skill_ontology.normalization import clean_token, dedupe_preserve


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "src" / "eval" / "golden_set.jsonl"
DEFAULT_OUTPUT = ROOT / "src" / "eval" / "golden_set.jsonl"
DEFAULT_BACKUP_PREFIX = ROOT / "src" / "eval" / "golden_set.backup"


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    required_overlap: float
    optional_overlap: float
    matched_required: list[str]
    matched_optional: list[str]
    fusion_score: float
    quality_score: float
    rank: int


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _normalize_terms(values: list[Any], ontology: RuntimeSkillOntology) -> list[str]:
    out: list[str] = []
    for value in values:
        token = clean_token(value)
        if not token:
            continue
        out.append(ontology.alias_to_canonical.get(token, token))
    return dedupe_preserve(out)


def _overlap(expected: list[str], observed: set[str]) -> tuple[float, list[str]]:
    if not expected:
        return 0.0, []
    matched = sorted(skill for skill in expected if skill in observed)
    return round(len(matched) / float(len(expected)), 4), matched


def _extract_fusion_score(hit: dict[str, Any]) -> float:
    value = hit.get("fusion_score")
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _grade_for(required_overlap: float, *, rank: int) -> int:
    if required_overlap >= 0.75 and rank == 0:
        return 3
    if required_overlap >= 0.5:
        return 3 if rank <= 1 else 2
    if required_overlap >= 0.35:
        return 2
    return 1


def _candidate_evidence(
    *,
    ranked_ids: list[str],
    hits_by_id: dict[str, dict[str, Any]],
    skills_by_id: dict[str, list[str]],
    required_skills: list[str],
    optional_skills: list[str],
) -> list[CandidateEvidence]:
    rows: list[CandidateEvidence] = []
    for rank, cid in enumerate(ranked_ids):
        hit = hits_by_id.get(cid) or {}
        observed = {clean_token(skill) for skill in (skills_by_id.get(cid) or [])}
        observed = {skill for skill in observed if skill}

        required_overlap, matched_required = _overlap(required_skills, observed)
        optional_overlap, matched_optional = _overlap(optional_skills, observed)
        fusion = _extract_fusion_score(hit)
        quality = round((required_overlap * 0.8) + (optional_overlap * 0.15) + (fusion * 0.05), 4)

        rows.append(
            CandidateEvidence(
                candidate_id=cid,
                required_overlap=required_overlap,
                optional_overlap=optional_overlap,
                matched_required=matched_required,
                matched_optional=matched_optional,
                fusion_score=fusion,
                quality_score=quality,
                rank=rank,
            )
        )
    return rows


def _select_candidates(
    evidences: list[CandidateEvidence],
    *,
    max_golden: int,
    min_required_overlap: float,
    relaxed_required_overlap: float,
    relaxed_min_quality: float,
) -> list[CandidateEvidence]:
    qualified: list[CandidateEvidence] = []
    for evidence in evidences:
        strong = evidence.required_overlap >= min_required_overlap
        relaxed = (
            evidence.required_overlap >= relaxed_required_overlap
            and evidence.quality_score >= relaxed_min_quality
            and (len(evidence.matched_required) >= 1 or len(evidence.matched_optional) >= 1)
        )
        if strong or relaxed:
            qualified.append(evidence)

    qualified.sort(
        key=lambda row: (
            row.quality_score,
            row.required_overlap,
            row.optional_overlap,
            row.fusion_score,
            -row.rank,
        ),
        reverse=True,
    )
    return qualified[:max_golden]


def _build_reason(row: CandidateEvidence) -> str:
    required = ", ".join(row.matched_required) if row.matched_required else "-"
    optional = ", ".join(row.matched_optional) if row.matched_optional else "-"
    return (
        f"required_overlap={row.required_overlap:.2f} (matched: {required}); "
        f"optional_overlap={row.optional_overlap:.2f} (matched: {optional}); "
        f"fusion={row.fusion_score:.4f}; quality={row.quality_score:.4f}"
    )


def regenerate_rows(
    *,
    rows: list[dict[str, Any]],
    ontology: RuntimeSkillOntology,
    adapter: MatchPipelineAdapter,
    top_k: int,
    max_golden: int,
    min_required_overlap: float,
    relaxed_required_overlap: float,
    relaxed_min_quality: float,
    min_candidates: int,
    include_soft: bool,
    include_families: set[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    processed = 0
    converted_to_soft = 0
    kept_hard = 0
    selected_counts: list[int] = []

    for row in rows:
        copied = dict(row)
        query_id = str(copied.get("query_id") or "")
        family = str(copied.get("job_family") or "").strip().lower()
        is_soft = bool(copied.get("soft_golden", False))
        if not query_id:
            updated.append(copied)
            continue
        if is_soft and not include_soft:
            updated.append(copied)
            continue
        if include_families and family not in include_families:
            updated.append(copied)
            continue

        required_skills = _normalize_terms(list(copied.get("expected_skills") or []), ontology)
        optional_skills = _normalize_terms(list(copied.get("expected_optional_skills") or []), ontology)
        job_description = str(copied.get("job_description") or "")
        if not job_description.strip():
            updated.append(copied)
            continue

        retrieval = adapter.retrieve(job_description=job_description, top_k=top_k)
        ranked_ids = [str(cid) for cid in retrieval.get("ranked_ids") or [] if str(cid)]
        hits = retrieval.get("hits") or []
        hits_by_id = {str(hit.get("candidate_id")): hit for hit in hits if hit.get("candidate_id")}
        candidate_skills = retrieval.get("candidate_skills") or {}

        evidences = _candidate_evidence(
            ranked_ids=ranked_ids,
            hits_by_id=hits_by_id,
            skills_by_id=candidate_skills,
            required_skills=required_skills,
            optional_skills=optional_skills,
        )
        selected = _select_candidates(
            evidences,
            max_golden=max_golden,
            min_required_overlap=min_required_overlap,
            relaxed_required_overlap=relaxed_required_overlap,
            relaxed_min_quality=relaxed_min_quality,
        )
        selected_counts.append(len(selected))
        processed += 1

        if len(selected) < min_candidates:
            copied["soft_golden"] = True
            copied["relevant_candidates"] = []
            copied["expected_candidate_ids"] = []
            copied["regen_note"] = (
                f"insufficient_quality_candidates({len(selected)}/{min_candidates}); "
                f"min_required_overlap={min_required_overlap}"
            )
            converted_to_soft += 1
            updated.append(copied)
            continue

        relevant_candidates: list[dict[str, Any]] = []
        for index, evidence in enumerate(selected):
            relevant_candidates.append(
                {
                    "candidate_id": evidence.candidate_id,
                    "grade": _grade_for(evidence.required_overlap, rank=index),
                    "reason": _build_reason(evidence),
                }
            )

        copied["relevant_candidates"] = relevant_candidates
        copied["expected_candidate_ids"] = [row["candidate_id"] for row in relevant_candidates]
        copied.pop("soft_golden", None)
        copied.pop("regen_note", None)
        kept_hard += 1
        updated.append(copied)

    summary = {
        "processed_rows": processed,
        "kept_hard_rows": kept_hard,
        "converted_to_soft_rows": converted_to_soft,
        "avg_selected_candidates": round(sum(selected_counts) / float(max(1, len(selected_counts))), 3)
        if selected_counts
        else 0.0,
    }
    return updated, summary


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file_obj:
        for row in rows:
            file_obj.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate golden_set.jsonl using current retrieval outputs.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input golden set JSONL.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output golden set JSONL.")
    parser.add_argument("--top-k", type=int, default=60, help="Retrieval top-k pool to scan.")
    parser.add_argument("--max-golden", type=int, default=5, help="Max relevant candidates per query.")
    parser.add_argument("--min-candidates", type=int, default=2, help="Minimum relevant candidates to keep hard-golden.")
    parser.add_argument("--min-required-overlap", type=float, default=0.4, help="Primary required-skill overlap threshold.")
    parser.add_argument("--relaxed-required-overlap", type=float, default=0.25, help="Relaxed required overlap threshold.")
    parser.add_argument("--relaxed-min-quality", type=float, default=0.24, help="Relaxed quality score threshold.")
    parser.add_argument("--include-soft", action="store_true", help="Also regenerate currently soft_golden rows.")
    parser.add_argument(
        "--families",
        default="",
        help="Comma-separated job_family whitelist (e.g. junior_software,senior_architect). Empty = all families.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write output file.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    rows = _load_rows(input_path)
    ontology = RuntimeSkillOntology.load_from_config(ROOT / "config")
    adapter = MatchPipelineAdapter()

    include_families: set[str] | None = None
    if args.families.strip():
        include_families = {token.strip().lower() for token in args.families.split(",") if token.strip()}

    updated_rows, summary = regenerate_rows(
        rows=rows,
        ontology=ontology,
        adapter=adapter,
        top_k=max(1, int(args.top_k)),
        max_golden=max(1, int(args.max_golden)),
        min_candidates=max(1, int(args.min_candidates)),
        min_required_overlap=max(0.0, min(1.0, float(args.min_required_overlap))),
        relaxed_required_overlap=max(0.0, min(1.0, float(args.relaxed_required_overlap))),
        relaxed_min_quality=max(0.0, min(1.0, float(args.relaxed_min_quality))),
        include_soft=bool(args.include_soft),
        include_families=include_families,
    )

    if not args.dry_run:
        if input_path == output_path and output_path.exists():
            stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            backup_path = Path(f"{DEFAULT_BACKUP_PREFIX}.{stamp}.jsonl")
            output_path.replace(backup_path)
            print(f"[regen] backup={backup_path}")
        _write_rows(output_path, updated_rows)
        print(f"[regen] wrote={output_path}")

    print(
        "[regen] summary "
        f"processed={summary['processed_rows']} "
        f"kept_hard={summary['kept_hard_rows']} "
        f"soft={summary['converted_to_soft_rows']} "
        f"avg_selected={summary['avg_selected_candidates']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
