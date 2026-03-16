# src/eval/regen_golden_set.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.database import get_collection
from backend.services.matching_service import matching_service

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = ROOT / "src" / "eval" / "golden_set.jsonl"
BACKUP_PATH = ROOT / "src" / "eval" / "golden_set.backup.jsonl"

MIN_REQUIRED_OVERLAP = 0.4  # required_skills 중 최소 이 정도는 겹쳐야 golden으로 인정
TOP_K = 20                  # /api 수준과 맞추는 retrieval top_k
GOLDEN_PER_QUERY = 5        # 쿼리당 golden 후보 수

def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows.append(row)
    return rows

def fetch_candidates(cids: list[str]) -> dict[str, dict[str, Any]]:
    coll = get_collection("candidates")
    docs = list(
        coll.find(
            {"candidate_id": {"$in": cids}},
            {"candidate_id": 1, "parsed.normalized_skills": 1, "_id": 0},
        )
    )
    return {d["candidate_id"]: d for d in docs}

def normalized_skills(doc: dict[str, Any]) -> set[str]:
    parsed = doc.get("parsed") or {}
    skills = parsed.get("normalized_skills") or []
    return {str(s).strip().lower() for s in skills if str(s).strip()}

def overlap_ratio(expected: list[str], skills: set[str]) -> float:
    exp = {s.lower() for s in expected}
    if not exp:
        return 0.0
    return len(exp & skills) / float(len(exp))

def build_reason(expected_skills: list[str], cand_doc: dict[str, Any]) -> str:
    skills = normalized_skills(cand_doc)
    exp = {s.lower() for s in expected_skills}
    ov = exp & skills
    return (
        f"{cand_doc.get('category', 'UNKNOWN')} profile with "
        f"{len(ov)} matched required skills ({', '.join(sorted(ov))}); "
        f"overlap={len(ov)/max(1,len(exp)):.2f}."
    )

def regenerate_row(row: dict[str, Any]) -> dict[str, Any]:
    """주어진 JD에 대해 matching_service를 다시 돌려 golden 후보를 재구성."""
    job_description = row["job_description"]
    expected_skills = [s.lower() for s in row.get("expected_skills", [])]

    resp = matching_service.match_jobs(job_description=job_description, top_k=TOP_K)

    # top-K 후보를 스킬 overlap 기준으로 다시 점수화
    coll = get_collection("candidates")
    cids = [m.candidate_id for m in resp.matches]
    docs = {
        d["candidate_id"]: d
        for d in coll.find(
            {"candidate_id": {"$in": cids}},
            {"candidate_id": 1, "parsed.normalized_skills": 1, "category": 1, "_id": 0},
        )
    }

    scored: list[tuple[float, dict[str, Any]]] = []
    for m in resp.matches:
        doc = docs.get(m.candidate_id)
        if not doc:
            continue
        ov = overlap_ratio(expected_skills, normalized_skills(doc))
        if ov < MIN_REQUIRED_OVERLAP:
            continue
        scored.append((ov, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:GOLDEN_PER_QUERY]

    new_rels = []
    for i, (_, doc) in enumerate(top):
        grade = 3 if i == 0 else 2
        new_rels.append(
            {
                "candidate_id": doc["candidate_id"],
                "grade": grade,
                "reason": build_reason(expected_skills, doc),
            }
        )

    # golden 후보가 하나도 안 나오면 이 row는 soft_golden으로 내려버림
    if not new_rels:
        row["soft_golden"] = True
        return row

    row["relevant_candidates"] = new_rels
    row["expected_candidate_ids"] = [r["candidate_id"] for r in new_rels]
    row.pop("soft_golden", None)
    return row

def main() -> None:
    rows = load_rows(GOLDEN_PATH)

    # 백업
    GOLDEN_PATH.rename(BACKUP_PATH)

    updated: list[dict[str, Any]] = []
    for row in rows:
        qid = row.get("query_id")
        if not qid:
            continue

        # backend/fullstack/senior architect만 우선 재생성
        if qid in {"gs-q-003", "gs-q-022", "gs-q-050"}:
            print(f"[regen] {qid}")
            row = regenerate_row(row)
        updated.append(row)

    with GOLDEN_PATH.open("w", encoding="utf-8") as f:
        for row in updated:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("Done. Old file backed up at:", BACKUP_PATH)

if __name__ == "__main__":
    main()