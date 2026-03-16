from __future__ import annotations

import time
from typing import Any

from eval.metrics import estimate_tokens_from_text

from backend.repositories.mongo_repo import get_candidates_by_ids
from backend.services.hybrid_retriever import HybridRetriever
from backend.services.job_profile_extractor import build_job_profile
from backend.services.candidate_enricher import enrich_hits
from backend.services.cross_encoder_rerank_service import cross_encoder_rerank_service
from backend.services.matching_service import matching_service


class MatchPipelineAdapter:
    """Production-facing adapter over query understanding, retrieval, rerank, and agent evaluation."""

    def query_understanding(self, *, job_description: str) -> dict[str, Any]:
        started = time.perf_counter()
        profile = build_job_profile(job_description, None)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "roles": list(profile.roles),
            "required_skills": list(profile.required_skills),
            "unknown_ratio": float(profile.signal_quality.get("unknown_ratio", 1.0)),
            "fallback_used": bool(profile.fallback_used),
            "latency_ms": latency_ms,
        }

    def retrieve(self, *, job_description: str, top_k: int) -> dict[str, Any]:
        started = time.perf_counter()
        profile = build_job_profile(job_description, None)
        retriever = HybridRetriever()
        hits = retriever.search_candidates(
            job_description=job_description,
            job_profile=profile,
            top_k=top_k,
            category=None,
            min_experience_years=None,
        )
        ranked_ids = [str(hit.get("candidate_id")) for hit in hits if hit.get("candidate_id")]

        docs_by_id = get_candidates_by_ids(ranked_ids)
        candidate_skills: dict[str, list[str]] = {}
        for cid in ranked_ids:
            doc = docs_by_id.get(cid) or {}
            parsed = doc.get("parsed") if isinstance(doc.get("parsed"), dict) else {}
            skills = (
                parsed.get("normalized_skills")
                or parsed.get("skills")
                or parsed.get("core_skills")
                or []
            )
            if not isinstance(skills, list):
                skills = []
            candidate_skills[cid] = [str(skill).strip().lower() for skill in skills if str(skill).strip()]

        latency_ms = (time.perf_counter() - started) * 1000.0
        input_tokens = estimate_tokens_from_text(job_description)
        output_tokens = max(0, int(len(ranked_ids) * 12))
        fallback_triggered = any(bool(hit.get("retrieval_fallback_triggered", False)) for hit in hits)
        retrieval_stage_signal = "unknown"
        if hits:
            retrieval_stage_signal = str(hits[0].get("retrieval_stage_signal") or "unknown")
        return {
            "ranked_ids": ranked_ids,
            "hits": hits,
            "candidate_skills": candidate_skills,
            "latency_ms": latency_ms,
            "fallback_triggered": fallback_triggered,
            "retrieval_stage_signal": retrieval_stage_signal,
            "token_usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    def rerank(self, *, job_description: str, baseline_hits: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
        started = time.perf_counter()
        enriched_hits = enrich_hits(
            baseline_hits,
            min_experience_years=None,
            education=None,
            region=None,
            industry=None,
        )
        reranked = cross_encoder_rerank_service.rerank(
            job_description=job_description,
            enriched_hits=enriched_hits,
            top_k=top_k,
        )
        ranked_ids = [str(hit.get("candidate_id")) for hit, _ in reranked if hit.get("candidate_id")]
        latency_ms = (time.perf_counter() - started) * 1000.0
        input_tokens = estimate_tokens_from_text(job_description) + max(0, int(len(baseline_hits) * 16))
        output_tokens = max(0, int(len(ranked_ids) * 6))
        return {
            "ranked_ids": ranked_ids,
            "latency_ms": latency_ms,
            "token_usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    def agent_evaluate(self, *, job_description: str, top_k: int) -> dict[str, Any]:
        started = time.perf_counter()
        response = matching_service.match_jobs(job_description=job_description, top_k=top_k)
        latency_ms = (time.perf_counter() - started) * 1000.0

        rows: list[dict[str, Any]] = []
        runtime_fallback_count = 0
        runtime_error_count = 0
        for match in response.matches:
            agent_scores = dict(match.agent_scores or {})
            runtime_mode = str(agent_scores.get("runtime_mode", "")).strip().lower()
            runtime_reason = str(agent_scores.get("runtime_reason", "")).strip().lower()
            runtime_fallback_used = bool(agent_scores.get("runtime_fallback_used", False)) or runtime_mode == "heuristic"
            if runtime_fallback_used:
                runtime_fallback_count += 1
            if runtime_reason and any(
                token in runtime_reason for token in ("failed", "error", "timeout", "unavailable", "fallback")
            ):
                runtime_error_count += 1
            rows.append(
                {
                    "candidate_id": match.candidate_id,
                    "score": float(match.score),
                    "skills": list(match.normalized_skills or match.skills or []),
                    "agent_scores": agent_scores,
                    "agent_explanation": match.agent_explanation,
                }
            )

        input_tokens = estimate_tokens_from_text(job_description) + max(0, int(len(rows) * 24))
        output_tokens = estimate_tokens_from_text(" ".join(str(r.get("agent_explanation") or "") for r in rows))
        fallback_used = bool(response.query_profile.fallback_used) or runtime_fallback_count > 0
        return {
            "matches": rows,
            "latency_ms": latency_ms,
            "token_usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "fallback_used": fallback_used,
            "agent_runtime_fallback_count": runtime_fallback_count,
            "agent_runtime_error_count": runtime_error_count,
        }


__all__ = ["MatchPipelineAdapter"]

