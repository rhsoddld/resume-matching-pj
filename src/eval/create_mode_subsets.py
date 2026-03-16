from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.services.eval_adapter import MatchPipelineAdapter
from eval.metrics import mrr, must_have_coverage, ndcg_at_k, recall_at_k


@dataclass
class QueryDiagnostics:
    row: dict[str, Any]
    retrieved_ids: list[str]
    recall_at_10: float
    mrr: float
    must_have_coverage: float
    ndcg_at_5: float
    top1_relevant: bool
    first_relevant_rank: int | None
    top2_gap: float | None
    retrieval_stage_signal: str


def _load_golden_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        row = json.loads(raw)
        if bool(row.get("soft_golden", False)):
            continue
        rows.append(row)
    return rows


def _first_relevant_rank(retrieved_ids: list[str], expected_ids: set[str]) -> int | None:
    for idx, candidate_id in enumerate(retrieved_ids, start=1):
        if candidate_id in expected_ids:
            return idx
    return None


def _top2_gap(hits: list[dict[str, Any]]) -> float | None:
    if len(hits) < 2:
        return None
    first = hits[0].get("fusion_score", hits[0].get("score"))
    second = hits[1].get("fusion_score", hits[1].get("score"))
    if not isinstance(first, (int, float)) or not isinstance(second, (int, float)):
        return None
    return round(float(first) - float(second), 6)


def _collect_diagnostics(row: dict[str, Any], adapter: MatchPipelineAdapter) -> QueryDiagnostics:
    job_description = str(row.get("job_description") or "")
    expected_skills = [str(skill) for skill in (row.get("expected_skills") or [])]
    relevant_candidates = row.get("relevant_candidates") or []
    relevance_by_id = {
        str(item.get("candidate_id")): int(item.get("grade", 0))
        for item in relevant_candidates
        if item.get("candidate_id")
    }
    expected_ids = set(relevance_by_id.keys())

    retrieval = adapter.retrieve(job_description=job_description, top_k=20)
    retrieved_ids = [str(cid) for cid in (retrieval.get("ranked_ids") or []) if cid]
    candidate_skills = retrieval.get("candidate_skills") or {}
    candidate_skill_lists = [list(candidate_skills.get(cid) or []) for cid in retrieved_ids[:10]]

    top1_relevant = bool(retrieved_ids and retrieved_ids[0] in expected_ids)
    first_rank = _first_relevant_rank(retrieved_ids, expected_ids)
    return QueryDiagnostics(
        row=row,
        retrieved_ids=retrieved_ids,
        recall_at_10=recall_at_k(expected_ids, retrieved_ids, 10),
        mrr=mrr(expected_ids, retrieved_ids),
        must_have_coverage=must_have_coverage(expected_skills, candidate_skill_lists),
        ndcg_at_5=ndcg_at_k(relevance_by_id, retrieved_ids, 5),
        top1_relevant=top1_relevant,
        first_relevant_rank=first_rank,
        top2_gap=_top2_gap(list(retrieval.get("hits") or [])),
        retrieval_stage_signal=str(retrieval.get("retrieval_stage_signal") or "unknown"),
    )


def _hybrid_sort_key(item: QueryDiagnostics) -> tuple[float, float, float]:
    first_rank = item.first_relevant_rank if item.first_relevant_rank is not None else 999
    return (item.recall_at_10, item.mrr, first_rank)


def _rerank_sort_key(item: QueryDiagnostics) -> tuple[float, float, int]:
    top_gap = item.top2_gap if item.top2_gap is not None else 999.0
    first_rank = item.first_relevant_rank if item.first_relevant_rank is not None else 999
    return (top_gap, item.ndcg_at_5, first_rank)


def _agent_sort_key(item: QueryDiagnostics) -> tuple[float, float, int]:
    first_rank = item.first_relevant_rank if item.first_relevant_rank is not None else 999
    return (-item.recall_at_10, -item.ndcg_at_5, first_rank)


def _limit_per_family(rows: list[QueryDiagnostics], limit: int, per_family_cap: int) -> list[QueryDiagnostics]:
    selected: list[QueryDiagnostics] = []
    counts: dict[str, int] = {}
    for item in rows:
        family = str(item.row.get("job_family") or "unknown")
        current = counts.get(family, 0)
        if current >= per_family_cap:
            continue
        counts[family] = current + 1
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _select_hybrid(rows: list[QueryDiagnostics], limit: int, per_family_cap: int) -> list[QueryDiagnostics]:
    candidates = [
        item
        for item in rows
        if item.recall_at_10 < 1.0
        or item.must_have_coverage < 0.6
        or (item.first_relevant_rank is not None and item.first_relevant_rank > 3)
        or item.retrieval_stage_signal != "hybrid"
    ]
    candidates.sort(key=_hybrid_sort_key)
    return _limit_per_family(candidates, limit=limit, per_family_cap=per_family_cap)


def _select_rerank(rows: list[QueryDiagnostics], limit: int, per_family_cap: int) -> list[QueryDiagnostics]:
    candidates = [
        item
        for item in rows
        if item.first_relevant_rank is not None
        and item.first_relevant_rank <= 10
        and (not item.top1_relevant or item.ndcg_at_5 < 1.0)
        and (item.top2_gap is None or item.top2_gap <= 0.03)
    ]
    candidates.sort(key=_rerank_sort_key)
    return _limit_per_family(candidates, limit=limit, per_family_cap=per_family_cap)


def _select_agent(rows: list[QueryDiagnostics], limit: int, per_family_cap: int) -> list[QueryDiagnostics]:
    primary = [
        item
        for item in rows
        if item.top1_relevant
        and item.first_relevant_rank == 1
        and item.recall_at_10 >= 0.6
        and item.ndcg_at_5 >= 0.6
        and item.must_have_coverage >= 0.6
    ]
    primary.sort(key=_agent_sort_key)
    selected = _limit_per_family(primary, limit=limit, per_family_cap=per_family_cap)
    if len(selected) >= limit:
        return selected

    fallback = [
        item
        for item in rows
        if item not in selected
        and item.first_relevant_rank is not None
        and item.first_relevant_rank <= 2
        and item.recall_at_10 >= 0.6
        and item.must_have_coverage >= 0.6
    ]
    fallback.sort(key=_agent_sort_key)
    for item in fallback:
        if len(selected) >= limit:
            break
        family = str(item.row.get("job_family") or "unknown")
        if sum(1 for current in selected if str(current.row.get("job_family") or "unknown") == family) >= per_family_cap:
            continue
        selected.append(item)
    return selected


def _write_jsonl(path: Path, items: list[QueryDiagnostics]) -> None:
    lines = [json.dumps(item.row, ensure_ascii=False) for item in items]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_manifest(path: Path, selections: dict[str, list[QueryDiagnostics]]) -> None:
    payload = {
        mode: [
            {
                "query_id": item.row.get("query_id"),
                "job_family": item.row.get("job_family"),
                "recall_at_10": item.recall_at_10,
                "mrr": item.mrr,
                "must_have_coverage": item.must_have_coverage,
                "ndcg_at_5": item.ndcg_at_5,
                "top1_relevant": item.top1_relevant,
                "first_relevant_rank": item.first_relevant_rank,
                "top2_gap": item.top2_gap,
                "retrieval_stage_signal": item.retrieval_stage_signal,
            }
            for item in items
        ]
        for mode, items in selections.items()
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_summary(path: Path, selections: dict[str, list[QueryDiagnostics]]) -> None:
    lines = [
        "# Mode Eval Subsets",
        "",
        "Prepared subsets for shortest-path evaluation when lexical retrieval is already strong.",
        "",
    ]
    for mode, items in selections.items():
        lines.append(f"## {mode}")
        lines.append("")
        lines.append(f"- queries: `{len(items)}`")
        families: dict[str, int] = {}
        for item in items:
            family = str(item.row.get("job_family") or "unknown")
            families[family] = families.get(family, 0) + 1
        if families:
            lines.append(
                "- family_mix: "
                + ", ".join(f"`{family}`={count}" for family, count in sorted(families.items()))
            )
        for item in items:
            lines.append(
                "- `{qid}` `{family}` recall@10={r10:.2f} mrr={mrr:.2f} ndcg@5={ndcg:.2f} "
                "must_have={mh:.2f} first_rel_rank={rank} top2_gap={gap}".format(
                    qid=item.row.get("query_id"),
                    family=item.row.get("job_family"),
                    r10=item.recall_at_10,
                    mrr=item.mrr,
                    ndcg=item.ndcg_at_5,
                    mh=item.must_have_coverage,
                    rank=item.first_relevant_rank,
                    gap=item.top2_gap if item.top2_gap is not None else "-",
                )
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create mode-specific golden subsets for hybrid/rerank/agent eval.")
    parser.add_argument("--golden-set", default="src/eval/golden_set.normalized.jsonl")
    parser.add_argument("--output-dir", default="src/eval/subsets")
    parser.add_argument("--hybrid-limit", type=int, default=18)
    parser.add_argument("--rerank-limit", type=int, default=18)
    parser.add_argument("--agent-limit", type=int, default=6)
    parser.add_argument("--per-family-cap", type=int, default=4)
    parser.add_argument("--agent-family-cap", type=int, default=2)
    args = parser.parse_args()

    golden_set_path = Path(args.golden_set).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    adapter = MatchPipelineAdapter()
    rows = _load_golden_rows(golden_set_path)
    diagnostics = [_collect_diagnostics(row, adapter) for row in rows]

    hybrid_rows = _select_hybrid(diagnostics, limit=max(1, args.hybrid_limit), per_family_cap=max(1, args.per_family_cap))
    rerank_rows = _select_rerank(diagnostics, limit=max(1, args.rerank_limit), per_family_cap=max(1, args.per_family_cap))
    agent_rows = _select_agent(
        diagnostics,
        limit=max(1, args.agent_limit),
        per_family_cap=max(1, args.agent_family_cap),
    )

    selections = {
        "hybrid": hybrid_rows,
        "rerank": rerank_rows,
        "agent": agent_rows,
    }

    _write_jsonl(output_dir / "golden.hybrid.jsonl", hybrid_rows)
    _write_jsonl(output_dir / "golden.rerank.jsonl", rerank_rows)
    _write_jsonl(output_dir / "golden.agent.jsonl", agent_rows)
    _write_manifest(output_dir / "subset_manifest.json", selections)
    _write_summary(output_dir / "README.md", selections)

    for mode, items in selections.items():
        print(f"[create_mode_subsets] mode={mode} queries={len(items)} path={output_dir / f'golden.{mode}.jsonl'}")
    print(f"[create_mode_subsets] manifest={output_dir / 'subset_manifest.json'}")
    print(f"[create_mode_subsets] summary={output_dir / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
