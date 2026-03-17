from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from backend.agents.runtime.prompts import PROMPT_VERSION
from backend.core.model_routing import resolve_eval_judge_model
from backend.core.providers import get_openai_client
from backend.services.eval_adapter import MatchPipelineAdapter
from eval.metrics import (
    dimension_consistency_heuristic,
    explanation_groundedness_heuristic,
    normalize_skill_set,
)


logger = logging.getLogger(__name__)
JUDGE_PROMPT_VERSION = "llm-judge-v2"


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError("judge response did not contain a JSON object")
    return json.loads(text[start : end + 1])


def _overlap_score(tokens: set[str], explanation: str | None) -> float:
    text = str(explanation or "").strip().lower()
    if not text or not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token and token in text)
    return round(hits / float(len(tokens)), 4)


def _heuristic_explanation_quality(
    *,
    expected_skills: list[str],
    candidate_skills: list[str],
    explanation: str | None,
    agent_scores: dict[str, Any],
    final_score: float | None,
) -> dict[str, Any]:
    expected = normalize_skill_set(expected_skills)
    candidate = normalize_skill_set(candidate_skills)
    groundedness = explanation_groundedness_heuristic(
        explanation=explanation,
        expected_skills=expected_skills,
        candidate_skills=candidate_skills,
    )
    required_coverage = _overlap_score(expected, explanation)
    evidence_coverage = _overlap_score(candidate, explanation)
    consistency = dimension_consistency_heuristic(agent_scores=agent_scores, final_score=final_score)
    overall = round(
        min(
            1.0,
            0.40 * groundedness + 0.20 * required_coverage + 0.20 * evidence_coverage + 0.20 * consistency,
        ),
        4,
    )
    return {
        "overall_score": overall,
        "groundedness_score": groundedness,
        "coverage_score": required_coverage,
        "specificity_score": evidence_coverage,
        "consistency_score": consistency,
        "pass": overall >= 0.6,
        "rationale": (
            "bootstrap heuristic using literal token overlap and dimension consistency; "
            "replace with live LLM judge where available."
        ),
    }


def _build_judge_messages(
    *,
    row: dict[str, Any],
    top_match: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are ResumeJudge. Evaluate the top-ranked candidate and explanation for a resume-matching system. "
                "Use only the provided job description, expected skills, candidate summary, candidate skills, and explanation. "
                "Return strict JSON only. "
                "Scoring rules: generic evidence should not score above 0.74 overall. "
                "High scores require literal skill/evidence tokens and explanation grounded in the candidate snapshot."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "Judge the current top1 candidate for relevance and explanation quality.",
                    "output_schema": {
                        "top1_is_relevant": "boolean",
                        "relevance_rationale": "short string",
                        "explanation_quality": {
                            "overall_score": "0..1 float",
                            "groundedness_score": "0..1 float",
                            "coverage_score": "0..1 float",
                            "specificity_score": "0..1 float",
                            "pass": "boolean",
                            "rationale": "short string",
                        },
                    },
                    "job": {
                        "query_id": row.get("query_id"),
                        "job_family": row.get("job_family"),
                        "job_description": row.get("job_description"),
                        "expected_role": row.get("expected_role"),
                        "expected_skills": row.get("expected_skills") or [],
                        "expected_optional_skills": row.get("expected_optional_skills") or [],
                    },
                    "candidate": {
                        "candidate_id": top_match.get("candidate_id"),
                        "score": top_match.get("score"),
                        "summary": top_match.get("summary"),
                        "experience_years": top_match.get("experience_years"),
                        "seniority_level": top_match.get("seniority_level"),
                        "skills": top_match.get("skills") or [],
                        "agent_explanation": top_match.get("agent_explanation") or "",
                        "agent_scores": top_match.get("agent_scores") or {},
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]


def _run_live_llm_judge(*, row: dict[str, Any], top_match: dict[str, Any]) -> dict[str, Any]:
    selection = resolve_eval_judge_model()
    client = get_openai_client()
    completion = client.chat.completions.create(
        model=selection.model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=_build_judge_messages(row=row, top_match=top_match),
    )
    content = completion.choices[0].message.content if completion.choices else ""
    payload = _extract_json_object(content or "")
    explanation_quality = payload.get("explanation_quality") if isinstance(payload.get("explanation_quality"), dict) else {}
    return {
        "top1_is_relevant": bool(payload.get("top1_is_relevant", False)),
        "relevance_rationale": str(payload.get("relevance_rationale") or "").strip(),
        "explanation_quality": {
            "overall_score": round(float(explanation_quality.get("overall_score", 0.0)), 4),
            "groundedness_score": round(float(explanation_quality.get("groundedness_score", 0.0)), 4),
            "coverage_score": round(float(explanation_quality.get("coverage_score", 0.0)), 4),
            "specificity_score": round(float(explanation_quality.get("specificity_score", 0.0)), 4),
            "pass": bool(explanation_quality.get("pass", False)),
            "rationale": str(explanation_quality.get("rationale") or "").strip(),
        },
        "judge_source": "live_llm",
        "judge_model": selection.model,
        "judge_model_version": selection.version,
    }


def _build_annotation_record(
    *,
    row: dict[str, Any],
    top_match: dict[str, Any],
    judge_payload: dict[str, Any],
    golden_top1_is_relevant: bool,
    run_id: str,
) -> dict[str, Any]:
    return {
        "query_id": str(row.get("query_id") or "").strip(),
        "candidate_id": str(top_match.get("candidate_id") or "").strip(),
        "stage": "agent_top1",
        "top1_is_relevant": bool(judge_payload.get("top1_is_relevant", False)),
        "golden_top1_is_relevant": golden_top1_is_relevant,
        "judge_source": str(judge_payload.get("judge_source") or "bootstrap_heuristic"),
        "judge_model": str(judge_payload.get("judge_model") or "bootstrap_heuristic"),
        "judge_model_version": str(judge_payload.get("judge_model_version") or "bootstrap-v1"),
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "agent_prompt_version": PROMPT_VERSION,
        "generated_at_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "generator_run_id": run_id,
        "job_family": row.get("job_family"),
        "expected_role": row.get("expected_role"),
        "expected_skills": row.get("expected_skills") or [],
        "expected_optional_skills": row.get("expected_optional_skills") or [],
        "relevance_rationale": str(judge_payload.get("relevance_rationale") or "").strip(),
        "explanation_quality": judge_payload.get("explanation_quality") or {},
        "top1_snapshot": {
            "candidate_id": top_match.get("candidate_id"),
            "score": top_match.get("score"),
            "summary": top_match.get("summary"),
            "experience_years": top_match.get("experience_years"),
            "seniority_level": top_match.get("seniority_level"),
            "skills": top_match.get("skills") or [],
            "agent_scores": top_match.get("agent_scores") or {},
            "agent_explanation": top_match.get("agent_explanation") or "",
        },
    }


def main() -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Generate LLM-as-Judge annotations for the current golden subset.")
    parser.add_argument("--golden-set", default="src/eval/subsets/golden.agent.jsonl")
    parser.add_argument("--output", default="src/eval/llm_judge_annotations.jsonl")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--judge-mode", choices=["llm", "bootstrap"], default="llm")
    args = parser.parse_args()

    os.environ.setdefault("RESUME_MATCHING_EVAL_MODE", "agent")

    golden_path = Path(args.golden_set)
    output_path = Path(args.output)
    rows = _load_jsonl(golden_path)
    if args.limit > 0:
        rows = rows[: args.limit]

    adapter = MatchPipelineAdapter()
    run_id = f"judge-{dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    annotations: list[dict[str, Any]] = []
    live_success = 0
    bootstrap_count = 0

    for row in rows:
        query_id = str(row.get("query_id") or "").strip()
        logger.info("judge_annotation_start query_id=%s", query_id)
        agent_res = adapter.agent_evaluate(job_description=str(row.get("job_description") or ""), top_k=max(1, int(args.top_k)))
        matches = list(agent_res.get("matches") or [])
        if not matches:
            logger.warning("judge_annotation_skipped_no_matches query_id=%s", query_id)
            continue
        top_match = matches[0]
        candidate_id = str(top_match.get("candidate_id") or "").strip()
        expected_ids = {
            str(item.get("candidate_id"))
            for item in (row.get("relevant_candidates") or [])
            if item.get("candidate_id")
        }
        golden_top1_is_relevant = candidate_id in expected_ids

        judge_payload: dict[str, Any]
        if args.judge_mode == "llm":
            try:
                judge_payload = _run_live_llm_judge(row=row, top_match=top_match)
                live_success += 1
            except Exception as exc:
                logger.warning("live_llm_judge_failed query_id=%s error=%s", query_id, exc)
                judge_payload = {
                    "top1_is_relevant": golden_top1_is_relevant,
                    "relevance_rationale": "fallback to golden relevance because live judge was unavailable.",
                    "explanation_quality": _heuristic_explanation_quality(
                        expected_skills=list(row.get("expected_skills") or []),
                        candidate_skills=list(top_match.get("skills") or []),
                        explanation=top_match.get("agent_explanation"),
                        agent_scores=dict(top_match.get("agent_scores") or {}),
                        final_score=float(top_match.get("score")) if top_match.get("score") is not None else None,
                    ),
                    "judge_source": "bootstrap_heuristic",
                    "judge_model": "bootstrap_heuristic",
                    "judge_model_version": "bootstrap-v1",
                }
                bootstrap_count += 1
        else:
            judge_payload = {
                "top1_is_relevant": golden_top1_is_relevant,
                "relevance_rationale": "bootstrap from golden relevance labels.",
                "explanation_quality": _heuristic_explanation_quality(
                    expected_skills=list(row.get("expected_skills") or []),
                    candidate_skills=list(top_match.get("skills") or []),
                    explanation=top_match.get("agent_explanation"),
                    agent_scores=dict(top_match.get("agent_scores") or {}),
                    final_score=float(top_match.get("score")) if top_match.get("score") is not None else None,
                ),
                "judge_source": "bootstrap_heuristic",
                "judge_model": "bootstrap_heuristic",
                "judge_model_version": "bootstrap-v1",
            }
            bootstrap_count += 1

        annotations.append(
            _build_annotation_record(
                row=row,
                top_match=top_match,
                judge_payload=judge_payload,
                golden_top1_is_relevant=golden_top1_is_relevant,
                run_id=run_id,
            )
        )

    _write_jsonl(output_path, annotations)
    logger.info(
        "run_id=%s golden_set=%s output=%s records=%s live_llm_success_count=%s bootstrap_count=%s",
        run_id,
        str(golden_path),
        str(output_path),
        len(annotations),
        live_success,
        bootstrap_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
