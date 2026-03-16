from __future__ import annotations

from collections import Counter, OrderedDict
import hashlib
import logging
import re
import time
import concurrent.futures

try:
    from langsmith import get_current_run_tree
except ImportError:
    get_current_run_tree = None

from backend.core.collections import dedupe_preserve
from backend.core.model_routing import resolve_rerank_model
from backend.core.observability import traceable_op
from backend.core.providers import get_skill_ontology
from backend.core.settings import settings
from backend.repositories.hybrid_retriever import HybridRetriever
from backend.schemas.job import FairnessAudit, FairnessWarning, JobMatchCandidate, JobMatchResponse, QueryUnderstandingProfile
from backend.agents import agent_orchestration_service
from backend.services.candidate_enricher import enrich_hits
from backend.services.cross_encoder_rerank_service import cross_encoder_rerank_service
from backend.services.job_profile_extractor import JobProfile, QuerySignal, build_job_profile
from backend.services.match_result_builder import build_match_candidate
from backend.services.query_fallback_service import query_fallback_service


logger = logging.getLogger(__name__)
_STRENGTH_PRIORITY = {
    "must have": 4,
    "main focus": 3,
    "nice to have": 2,
    "familiarity": 1,
    "unknown": 0,
}
_SENSITIVE_TERMS = (
    "young",
    "old",
    "male",
    "female",
    "man",
    "woman",
    "boy",
    "girl",
    "pregnant",
    "maternity",
    "married",
    "single",
    "christian",
    "muslim",
    "hindu",
    "buddhist",
    "jewish",
    "white",
    "black",
    "asian",
    "latino",
    "native",
    "disability",
    "disabled",
)
_SENSITIVE_TERM_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in _SENSITIVE_TERMS) + r")\b",
    flags=re.IGNORECASE,
)


class _LRUCache:
    """Simple LRU cache for match_jobs responses (R2.5 token cache)."""

    def __init__(self, max_size: int = 128, ttl_sec: int = 300) -> None:
        self._store: OrderedDict[str, tuple[object, float]] = OrderedDict()
        self._max_size = max(1, max_size)
        self._ttl = float(ttl_sec)

    def _make_key(self, **kwargs: object) -> str:
        raw = "|".join(f"{k}={v}" for k, v in sorted([(str(k), str(v)) for k, v in kwargs.items()]))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, key: str) -> object | None:
        if key not in self._store:
            return None
        response, ts = self._store[key]  # type: ignore[misc]
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return response

    def set(self, key: str, response: object) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (response, time.monotonic())
        if len(self._store) > self._max_size:
            self._store.popitem(last=False)


class MatchingService:
    def __init__(self) -> None:
        self.hybrid_retriever = HybridRetriever()
        self.rerank_service = cross_encoder_rerank_service
        self._cache = _LRUCache(
            max_size=settings.token_cache_max_size,
            ttl_sec=settings.token_cache_ttl_sec,
        )

    @traceable_op(name="matching.match_jobs", run_type="chain", tags=["matching", "pipeline"])
    def match_jobs(
        self,
        *,
        job_description: str,
        top_k: int = 10,
        category: str | None = None,
        min_experience_years: float | None = None,
        education: str | None = None,
        region: str | None = None,
        industry: str | None = None,
    ) -> JobMatchResponse:
        # --- Token cache lookup (R2.5) ---
        cache_key: str | None = None
        if settings.token_cache_enabled:
            cache_key = self._cache._make_key(
                job_description=job_description,
                top_k=top_k,
                category=category,
                min_experience_years=min_experience_years,
                education=education,
                region=region,
                industry=industry,
            )
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.info("token_cache_hit key=%s", cache_key)
                return cached
            logger.info("token_cache_miss key=%s", cache_key)

        job_profile = self._build_query_profile(
            job_description=job_description,
            category_override=category,
            min_experience_years=min_experience_years,
            education_override=education,
            region_override=region,
            industry_override=industry,
        )

        retrieval_top_n = self._resolve_retrieval_top_n(top_k)
        hits = self._retrieve_candidates(
            job_description=job_description,
            job_profile=job_profile,
            top_k=retrieval_top_n,
            category=category,
            min_experience_years=min_experience_years,
        )
        enriched_hits = self._enrich_candidates(
            hits=hits,
            min_experience_years=min_experience_years,
            education=education,
            region=region,
            industry=industry,
        )
        shortlisted_hits = self._shortlist_candidates(
            job_description=job_description,
            job_profile=job_profile,
            enriched_hits=enriched_hits,
            top_k=top_k,
        )
        results = self._score_candidates(
            job_description=job_description,
            job_profile=job_profile,
            shortlisted_hits=shortlisted_hits,
            top_k=top_k,
            category=category,
        )
        fairness_audit = self._run_fairness_guardrails(
            job_description=job_description,
            job_profile=job_profile,
            matches=results,
            top_k=top_k,
        )

        if get_current_run_tree is not None:
            run_tree = get_current_run_tree()
            if run_tree:
                run_tree.add_metadata({
                    "job_category": job_profile.job_category,
                    "industry": industry or "unknown",
                    "fairness_enabled": fairness_audit.enabled,
                    "fairness_warnings_count": len(fairness_audit.warnings),
                })
                if fairness_audit.warnings:
                    run_tree.add_tags(["fairness_warnings_detected"])
                if job_profile.job_category:
                    run_tree.add_tags([f"category:{job_profile.job_category}"])

        response = JobMatchResponse(
            query_profile=QueryUnderstandingProfile(
                job_category=job_profile.job_category,
                roles=job_profile.roles,
                required_skills=job_profile.required_skills,
                related_skills=job_profile.related_skills,
                skill_signals=[
                    QueryUnderstandingProfile.Signal(
                        name=signal.name,
                        strength=signal.strength,
                        signal_type=signal.signal_type,
                    )
                    for signal in job_profile.skill_signals
                ],
                capability_signals=[
                    QueryUnderstandingProfile.Signal(
                        name=signal.name,
                        strength=signal.strength,
                        signal_type=signal.signal_type,
                    )
                    for signal in job_profile.capability_signals
                ],
                seniority_hint=job_profile.preferred_seniority,
                filters=job_profile.filters,
                metadata_filters=job_profile.metadata_filters,
                transferable_skill_score=job_profile.transferable_skill_score,
                transferable_skill_evidence=job_profile.transferable_skill_evidence,
                signal_quality=job_profile.signal_quality,
                lexical_query=job_profile.lexical_query,
                semantic_query_expansion=job_profile.semantic_query_expansion,
                query_text_for_embedding=job_profile.query_text_for_embedding,
                confidence=job_profile.confidence,
                fallback_used=job_profile.fallback_used,
                fallback_reason=job_profile.fallback_reason,
                fallback_rationale=job_profile.fallback_rationale,
                fallback_trigger=job_profile.fallback_trigger,
            ),
            matches=results,
            fairness=fairness_audit,
        )
        # --- Token cache store (R2.5) ---
        if settings.token_cache_enabled and cache_key is not None:
            self._cache.set(cache_key, response)
        return response

    @traceable_op(name="matching.stream_match_jobs", run_type="chain", tags=["matching", "pipeline", "stream"])
    def stream_match_jobs(
        self,
        *,
        job_description: str,
        top_k: int = 10,
        category: str | None = None,
        min_experience_years: float | None = None,
        education: str | None = None,
        region: str | None = None,
        industry: str | None = None,
    ):
        """Yields matching results as Server-Sent Events (SSE) for streaming UI rendering."""
        import json
        import queue
        import threading
        from backend.repositories.session_repo import create_jd_session
        
        event_queue = queue.Queue()
        
        job_profile = self._build_query_profile(
            job_description=job_description,
            category_override=category,
            min_experience_years=min_experience_years,
            education_override=education,
            region_override=region,
            industry_override=industry,
        )

        # Yield query understanding profile first
        profile_dict = {
            "job_category": job_profile.job_category,
            "roles": job_profile.roles,
            "required_skills": job_profile.required_skills,
            "confidence": job_profile.confidence,
        }
        event_queue.put(f"event: profile\ndata: {json.dumps(profile_dict, ensure_ascii=False)}\n\n")

        # Create JD session and emit session_id for AHI.2 / AHI.4 (non-fatal)
        try:
            session_id = create_jd_session(
                job_description=job_description,
                query_profile=profile_dict,
            )
            event_queue.put(f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n")
        except Exception as _session_exc:
            logger.warning("stream: Failed to create JD session (non-fatal): %s", _session_exc)

        retrieval_top_n = self._resolve_retrieval_top_n(top_k)
        hits = self._retrieve_candidates(
            job_description=job_description,
            job_profile=job_profile,
            top_k=retrieval_top_n,
            category=category,
            min_experience_years=min_experience_years,
        )
        
        enriched_hits = self._enrich_candidates(
            hits=hits,
            min_experience_years=min_experience_years,
            education=education,
            region=region,
            industry=industry,
        )
        
        shortlisted_hits = self._shortlist_candidates(
            job_description=job_description,
            job_profile=job_profile,
            enriched_hits=enriched_hits,
            top_k=top_k,
        )
        
        # Drain the queue initially
        while not event_queue.empty():
            yield event_queue.get_nowait()
        
        # We manually process candidates here to yield them one by one
        agent_eval_top_n = self._resolve_agent_eval_top_n(top_k)
        
        prelim_results: list[JobMatchCandidate] = []
        for hit, candidate_doc in shortlisted_hits:
            prelim_results.append(
                build_match_candidate(
                    hit=hit,
                    candidate_doc=candidate_doc,
                    job_profile=job_profile,
                    category=category,
                    agent_result=None,
                )
            )

        sorted_indices = sorted(range(len(prelim_results)), key=lambda idx: prelim_results[idx].score, reverse=True)
        eval_index_set = set(sorted_indices[:agent_eval_top_n])

        def _on_agent_event(event_type: str, data: dict[str, Any]):
            event_queue.put(f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n")

        def _evaluate_candidate(
            idx: int, 
            hit: dict[str, Any], 
            candidate_doc: dict[str, Any]
        ) -> JobMatchCandidate:
            if idx in eval_index_set:
                agent_result = agent_orchestration_service.run_for_candidate(
                    job_description=job_description,
                    job_profile=job_profile,
                    hit=hit,
                    candidate_doc=candidate_doc,
                    category_filter=category,
                    on_event=_on_agent_event,
                )
                return build_match_candidate(
                    hit=hit,
                    candidate_doc=candidate_doc,
                    job_profile=job_profile,
                    category=category,
                    agent_result=agent_result,
                    agent_evaluation_applied=True,
                )
            
            return build_match_candidate(
                hit=hit,
                candidate_doc=candidate_doc,
                job_profile=job_profile,
                category=category,
                agent_result=None,
                agent_evaluation_applied=False,
                agent_evaluation_reason=f"outside_agent_eval_top_n({agent_eval_top_n})",
            )

        finished_candidates = []
        active_futures = set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(shortlisted_hits))) as executor:
            future_to_idx = {
                executor.submit(_evaluate_candidate, idx, hit, candidate_doc): idx
                for idx, (hit, candidate_doc) in enumerate(shortlisted_hits)
            }
            active_futures.update(future_to_idx.keys())
            
            while active_futures:
                # Yield any pending thought process events
                while not event_queue.empty():
                    yield event_queue.get_nowait()

                # Wait for at least one future to complete, with a small timeout
                # to allow draining the event queue frequently.
                done, not_done = concurrent.futures.wait(
                    active_futures, 
                    timeout=0.1, 
                    return_when=concurrent.futures.FIRST_COMPLETED
                )
                
                for future in done:
                    active_futures.remove(future)
                    try:
                        candidate_result = future.result()
                        finished_candidates.append(candidate_result)
                        # Put candidate result into the queue to maintain ordering
                        event_queue.put(f"event: candidate\ndata: {candidate_result.model_dump_json()}\n\n")
                    except Exception as exc:
                        logger.exception("Failed streaming candidate evaluation.")
            
            # Final drain of the queue after all futures complete
            while not event_queue.empty():
                yield event_queue.get_nowait()

        # Finally, yield fairness audit
        finished_candidates.sort(
            key=lambda item: (
                0 if self._is_agent_evaluated(item) else 1,
                -item.score,
            )
        )
        fairness_audit = self._run_fairness_guardrails(
            job_description=job_description,
            job_profile=job_profile,
            matches=finished_candidates,
            top_k=top_k,
        )
        yield f"event: fairness\ndata: {fairness_audit.model_dump_json()}\n\n"
        
        # End stream
        yield "event: done\ndata: {}\n\n"


    def _build_query_profile(
        self,
        *,
        job_description: str,
        category_override: str | None,
        min_experience_years: float | None,
        education_override: str | None,
        region_override: str | None,
        industry_override: str | None,
    ) -> JobProfile:
        ontology = get_skill_ontology()
        deterministic_profile = build_job_profile(
            job_description=job_description,
            ontology=ontology,
            category_override=category_override,
            min_experience_years=min_experience_years,
            education_override=education_override,
            region_override=region_override,
            industry_override=industry_override,
        )
        job_profile = deterministic_profile
        should_fallback, fallback_reason, fallback_trigger = self._should_use_query_fallback(deterministic_profile)
        if should_fallback:
            fallback_draft = query_fallback_service.extract(job_description=job_description)
            if fallback_draft is not None:
                fallback_text = query_fallback_service.to_deterministic_text(fallback_draft)
                fallback_profile = build_job_profile(
                    job_description=fallback_text or job_description,
                    ontology=ontology,
                    category_override=category_override,
                    min_experience_years=min_experience_years,
                    education_override=education_override,
                    region_override=region_override,
                    industry_override=industry_override,
                )
                job_profile = self._merge_profiles(primary=deterministic_profile, fallback=fallback_profile)
                job_profile.fallback_used = True
                job_profile.fallback_reason = fallback_reason
                job_profile.fallback_rationale = fallback_draft.rationale
                job_profile.fallback_trigger = {
                    **fallback_trigger,
                    "llm_model": settings.query_fallback_model,
                }
                logger.info(
                    "query_fallback_applied reason=%s confidence=%.3f unknown_ratio=%.3f",
                    fallback_reason,
                    job_profile.confidence,
                    float(job_profile.signal_quality.get("unknown_ratio", 0.0)),
                )
            else:
                logger.warning(
                    "query_fallback_skipped reason=%s deterministic_confidence=%.3f deterministic_unknown_ratio=%.3f",
                    fallback_reason,
                    deterministic_profile.confidence,
                    float(deterministic_profile.signal_quality.get("unknown_ratio", 0.0)),
                )
        logger.info(
            "query_profile_built category=%s confidence=%.3f unknown_ratio=%.3f total_signals=%s fallback_used=%s",
            job_profile.job_category,
            job_profile.confidence,
            float(job_profile.signal_quality.get("unknown_ratio", 0.0)),
            job_profile.signal_quality.get("total_signals", 0),
            job_profile.fallback_used,
        )
        return job_profile

    @traceable_op(name="matching.retrieve_candidates", run_type="retriever", tags=["matching", "retrieval"])
    def _retrieve_candidates(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        top_k: int,
        category: str | None,
        min_experience_years: float | None,
    ) -> list[dict[str, object]]:
        return self.hybrid_retriever.search_candidates(
            job_description=job_description,
            job_profile=job_profile,
            top_k=top_k,
            category=category,
            min_experience_years=min_experience_years,
        )

    @traceable_op(name="matching.enrich_candidates", run_type="tool", tags=["matching", "mongo"])
    def _enrich_candidates(
        self,
        hits: list[dict[str, object]],
        *,
        min_experience_years: float | None,
        education: str | None,
        region: str | None,
        industry: str | None,
    ) -> list[tuple[dict[str, object], dict[str, object]]]:
        return enrich_hits(
            hits,
            min_experience_years=min_experience_years,
            education=education,
            region=region,
            industry=industry,
        )

    @traceable_op(name="matching.score_candidates", run_type="chain", tags=["matching", "ranking"])
    def _score_candidates(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        shortlisted_hits: list[tuple[dict[str, object], dict[str, object]]],
        top_k: int,
        category: str | None,
    ) -> list[JobMatchCandidate]:
        agent_eval_top_n = self._resolve_agent_eval_top_n(top_k)
        logger.info(
            "agent_eval_scope top_k=%s agent_eval_top_n=%s shortlisted=%s",
            top_k,
            agent_eval_top_n,
            len(shortlisted_hits),
        )

        prelim_results: list[JobMatchCandidate] = []
        for hit, candidate_doc in shortlisted_hits:
            prelim_results.append(
                build_match_candidate(
                    hit=hit,
                    candidate_doc=candidate_doc,
                    job_profile=job_profile,
                    category=category,
                    agent_result=None,
                )
            )

        sorted_indices = sorted(range(len(prelim_results)), key=lambda idx: prelim_results[idx].score, reverse=True)
        eval_index_set = set(sorted_indices[:agent_eval_top_n])
        logger.info(
            "agent_eval_selection selected=%s candidate_ids=%s",
            len(eval_index_set),
            [prelim_results[idx].candidate_id for idx in sorted_indices[:agent_eval_top_n]],
        )

        results: list[JobMatchCandidate] = []
        
        def _evaluate_candidate(
            idx: int, 
            hit: dict[str, Any], 
            candidate_doc: dict[str, Any]
        ) -> tuple[int, JobMatchCandidate]:
            if idx in eval_index_set:
                agent_result = agent_orchestration_service.run_for_candidate(
                    job_description=job_description,
                    job_profile=job_profile,
                    hit=hit,
                    candidate_doc=candidate_doc,
                    category_filter=category,
                )
                return idx, build_match_candidate(
                    hit=hit,
                    candidate_doc=candidate_doc,
                    job_profile=job_profile,
                    category=category,
                    agent_result=agent_result,
                    agent_evaluation_applied=True,
                )
            
            return idx, build_match_candidate(
                hit=hit,
                candidate_doc=candidate_doc,
                job_profile=job_profile,
                category=category,
                agent_result=None,
                agent_evaluation_applied=False,
                agent_evaluation_reason=f"outside_agent_eval_top_n({agent_eval_top_n})",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(shortlisted_hits))) as executor:
            future_to_idx = {
                executor.submit(_evaluate_candidate, idx, hit, candidate_doc): idx
                for idx, (hit, candidate_doc) in enumerate(shortlisted_hits)
            }
            
            for future in concurrent.futures.as_completed(future_to_idx):
                idx, candidate_result = future.result()
                results.append(candidate_result)
        results.sort(
            key=lambda item: (
                0 if self._is_agent_evaluated(item) else 1,
                -item.score,
            )
        )
        return results

    @traceable_op(name="matching.fairness_guardrails", run_type="tool", tags=["matching", "fairness"])
    def _run_fairness_guardrails(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        matches: list[JobMatchCandidate],
        top_k: int,
    ) -> FairnessAudit:
        checks_run = [
            "sensitive_term_scan",
            "culture_weight_cap",
            "must_have_vs_culture_gate",
            "topk_seniority_distribution",
        ]
        if not settings.fairness_guardrails_enabled:
            return FairnessAudit(
                enabled=False,
                policy_version=settings.fairness_policy_version,
                checks_run=checks_run,
                warnings=[],
            )

        warnings: list[FairnessWarning] = []
        sensitive_terms_in_query = self._extract_sensitive_terms(job_description) if settings.fairness_sensitive_term_enabled else []
        if sensitive_terms_in_query:
            warnings.append(
                FairnessWarning(
                    code="sensitive_term_in_query",
                    severity="critical",
                    message=(
                        "Potentially sensitive attributes were detected in job input. "
                        "Use job-relevant requirements only."
                    ),
                    candidate_ids=[],
                    metrics={"terms": sensitive_terms_in_query},
                )
            )

        for candidate in matches:
            candidate_warnings: list[str] = list(candidate.bias_warnings)
            candidate_ids = [candidate.candidate_id]
            sensitive_terms = []
            if settings.fairness_sensitive_term_enabled:
                sensitive_terms = self._extract_sensitive_terms(
                    " ".join([candidate.summary or "", candidate.agent_explanation or ""])
                )
            if sensitive_terms:
                message = (
                    "Profile summary/explanation contains sensitive-attribute wording. "
                    "Review evidence for job relevance."
                )
                candidate_warnings.append(message)
                warnings.append(
                    FairnessWarning(
                        code="sensitive_term_in_candidate_explanation",
                        severity="warning",
                        message=message,
                        candidate_ids=candidate_ids,
                        metrics={"terms": sensitive_terms},
                    )
                )

            culture_weight = self._get_culture_weight(candidate)
            if culture_weight is not None and culture_weight > float(settings.fairness_max_culture_weight):
                message = (
                    "Culture weight exceeded fairness cap. Skill and technical evidence should remain dominant."
                )
                candidate_warnings.append(message)
                warnings.append(
                    FairnessWarning(
                        code="culture_weight_over_cap",
                        severity="warning",
                        message=message,
                        candidate_ids=candidate_ids,
                        metrics={
                            "culture_weight": round(culture_weight, 4),
                            "max_culture_weight": float(settings.fairness_max_culture_weight),
                        },
                    )
                )

            must_have_match_rate = candidate.score_detail.must_have_match_rate
            culture_confidence = self._get_culture_confidence(candidate)
            if (
                must_have_match_rate is not None
                and culture_confidence is not None
                and must_have_match_rate < float(settings.fairness_min_must_have_match_rate)
                and culture_confidence > float(settings.fairness_high_culture_confidence)
                and candidate.score >= float(settings.fairness_rank_score_floor)
            ):
                message = (
                    "High-ranked profile has low must-have coverage with high culture confidence. "
                    "Validate job-critical requirements before progressing."
                )
                candidate_warnings.append(message)
                warnings.append(
                    FairnessWarning(
                        code="must_have_underfit_high_culture",
                        severity="warning",
                        message=message,
                        candidate_ids=candidate_ids,
                        metrics={
                            "must_have_match_rate": round(float(must_have_match_rate), 4),
                            "culture_confidence": round(float(culture_confidence), 4),
                            "score": round(float(candidate.score), 4),
                        },
                    )
                )
            candidate.bias_warnings = dedupe_preserve(candidate_warnings)

        top_results = matches[: max(0, top_k)]
        min_distribution_size = max(2, int(settings.fairness_topk_distribution_min))
        if len(top_results) >= min_distribution_size and not job_profile.preferred_seniority:
            normalized_seniority = [self._normalize_seniority(candidate.seniority_level) for candidate in top_results]
            known_seniority = [token for token in normalized_seniority if token != "unknown"]
            if known_seniority:
                counts = Counter(known_seniority)
                dominant, dominant_count = counts.most_common(1)[0]
                dominant_ratio = dominant_count / float(len(known_seniority))
                if dominant_ratio >= float(settings.fairness_seniority_concentration_threshold):
                    warnings.append(
                        FairnessWarning(
                            code="seniority_concentration_topk",
                            severity="warning",
                            message=(
                                "Top-ranked candidates are concentrated in one seniority band without a JD seniority constraint."
                            ),
                            candidate_ids=[candidate.candidate_id for candidate in top_results if self._normalize_seniority(candidate.seniority_level) == dominant],
                            metrics={
                                "dominant_seniority": dominant,
                                "dominant_ratio": round(dominant_ratio, 4),
                                "top_k": len(top_results),
                            },
                        )
                    )

        for warning in warnings:
            logger.warning(
                "fairness_guardrail_triggered code=%s severity=%s candidates=%s metrics=%s",
                warning.code,
                warning.severity,
                ",".join(warning.candidate_ids) if warning.candidate_ids else "none",
                warning.metrics,
            )

        return FairnessAudit(
            enabled=True,
            policy_version=settings.fairness_policy_version,
            checks_run=checks_run,
            warnings=warnings,
        )

    @staticmethod
    def _extract_sensitive_terms(text: str | None) -> list[str]:
        if not text or not text.strip():
            return []
        hits = [match.group(1).lower() for match in _SENSITIVE_TERM_PATTERN.finditer(text)]
        return dedupe_preserve(hits)

    @staticmethod
    def _get_culture_weight(candidate: JobMatchCandidate) -> float | None:
        weights = candidate.agent_scores.get("weights")
        if not isinstance(weights, dict):
            return None
        value = weights.get("culture")
        if not isinstance(value, (int, float)):
            return None
        return float(value)

    @staticmethod
    def _get_culture_confidence(candidate: JobMatchCandidate) -> float | None:
        confidence = candidate.agent_scores.get("confidence")
        if not isinstance(confidence, dict):
            return None
        value = confidence.get("culture")
        if not isinstance(value, (int, float)):
            return None
        return float(value)

    @staticmethod
    def _normalize_seniority(value: str | None) -> str:
        if not value:
            return "unknown"
        token = value.strip().lower()
        if not token:
            return "unknown"
        if "principal" in token or "staff" in token:
            return "principal"
        if "lead" in token:
            return "lead"
        if "senior" in token:
            return "senior"
        if "junior" in token or "entry" in token or "intern" in token:
            return "junior"
        if "mid" in token:
            return "mid"
        return token

    @staticmethod
    def _is_agent_evaluated(candidate: JobMatchCandidate) -> bool:
        value = candidate.agent_scores.get("agent_evaluation_applied")
        if isinstance(value, bool):
            return value
        return candidate.agent_scores.get("runtime_mode") != "deterministic_only"

    def _resolve_retrieval_top_n(self, top_k: int) -> int:
        if not settings.rerank_enabled:
            return top_k
        rerank_pool_n = self._resolve_rerank_pool_n(top_k)
        return max(top_k, rerank_pool_n)

    @traceable_op(name="matching.shortlist_candidates", run_type="retriever", tags=["matching", "rerank"])
    def _shortlist_candidates(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        enriched_hits: list[tuple[dict[str, object], dict[str, object]]],
        top_k: int,
    ) -> list[tuple[dict[str, object], dict[str, object]]]:
        if not enriched_hits:
            return []
        if not settings.rerank_enabled:
            return enriched_hits[:top_k]

        should_apply, reason = self._should_apply_rerank(
            job_profile=job_profile,
            enriched_hits=enriched_hits,
            top_k=top_k,
        )
        if not should_apply:
            logger.info("rerank_skipped reason=%s top_k=%s pool=%s", reason, top_k, len(enriched_hits))
            return enriched_hits[:top_k]

        pool_n = self._resolve_rerank_pool_n(top_k)
        rerank_pool = enriched_hits[:pool_n]
        rerank_selection = resolve_rerank_model(high_quality=(reason == "ambiguous_query_profile"))

        reranked = self.rerank_service.rerank(
            job_description=job_description,
            enriched_hits=rerank_pool,
            top_k=top_k,
            model_override=rerank_selection.model,
        )
        logger.info(
            "rerank_applied mode=%s model=%s model_version=%s model_route=%s top_n=%s top_k=%s input=%s output=%s reason=%s",
            settings.rerank_mode,
            rerank_selection.model,
            rerank_selection.version,
            rerank_selection.route,
            pool_n,
            top_k,
            len(rerank_pool),
            len(reranked),
            reason,
        )
        return reranked

    def _resolve_rerank_pool_n(self, top_k: int) -> int:
        max_pool = max(1, int(settings.rerank_gate_max_top_n))
        requested = max(1, int(settings.rerank_top_n))
        return max(top_k, min(requested, max_pool))

    def _resolve_agent_eval_top_n(self, top_k: int) -> int:
        requested = max(0, int(settings.agent_eval_top_n))
        capped = min(top_k, requested)
        if not settings.token_budget_enabled:
            return capped
        # Dynamic token budget adjustment (R2.5):
        # estimate how many agent evals fit within the per-request token budget
        budget = max(0, int(settings.token_budget_per_request))
        cost_per_candidate = max(1, int(settings.token_estimated_per_agent_call))
        # Reserve 30% of budget for retrieval/query understanding
        available_for_agents = int(budget * 0.70)
        budget_cap = max(0, available_for_agents // cost_per_candidate)
        adjusted = min(capped, budget_cap)
        if adjusted != capped:
            logger.info(
                "token_budget_agent_eval_adjusted original=%s budget_cap=%s adjusted=%s "
                "budget=%s cost_per_candidate=%s",
                capped,
                budget_cap,
                adjusted,
                budget,
                cost_per_candidate,
            )
        return adjusted

    def _should_apply_rerank(
        self,
        *,
        job_profile: JobProfile,
        enriched_hits: list[tuple[dict[str, object], dict[str, object]]],
        top_k: int,
    ) -> tuple[bool, str]:
        if len(enriched_hits) < 2:
            return False, "insufficient_candidates"

        pool_n = min(len(enriched_hits), self._resolve_rerank_pool_n(top_k))
        if pool_n < 2:
            return False, "insufficient_pool"

        score_rows: list[float] = []
        for hit, _ in enriched_hits[:pool_n]:
            score = hit.get("fusion_score", hit.get("score", 0.0))
            if isinstance(score, (int, float)):
                score_rows.append(float(score))
        if len(score_rows) < 2:
            return False, "score_missing"

        score_rows.sort(reverse=True)
        top_gap = score_rows[0] - score_rows[1]
        tie_like = top_gap <= float(settings.rerank_gate_top2_gap_threshold)

        unknown_ratio = float(job_profile.signal_quality.get("unknown_ratio", 0.0))
        low_confidence = float(job_profile.confidence) < float(settings.rerank_gate_confidence_threshold)
        noisy_query = unknown_ratio > float(settings.rerank_gate_unknown_ratio_threshold)
        ambiguous_query = low_confidence or noisy_query

        if tie_like:
            return True, "tight_top_scores"
        if ambiguous_query:
            return True, "ambiguous_query_profile"
        return False, "clear_top_scores_and_confident_query"

    @staticmethod
    def _should_use_query_fallback(job_profile: JobProfile) -> tuple[bool, str | None, dict[str, float]]:
        if not settings.query_fallback_enabled:
            return False, None, {}
        confidence = float(job_profile.confidence)
        unknown_ratio = float(job_profile.signal_quality.get("unknown_ratio", 0.0))
        if confidence < float(settings.query_fallback_confidence_threshold):
            return True, "low_confidence", {"confidence": confidence, "unknown_ratio": unknown_ratio}
        if unknown_ratio > float(settings.query_fallback_unknown_ratio_threshold):
            return True, "high_unknown_ratio", {"confidence": confidence, "unknown_ratio": unknown_ratio}
        return False, None, {"confidence": confidence, "unknown_ratio": unknown_ratio}

    @staticmethod
    def _dedupe_signals(signals: list[QuerySignal]) -> list[QuerySignal]:
        by_name: dict[str, QuerySignal] = {}
        for signal in signals:
            key = signal.name.strip().lower()
            if not key:
                continue
            existing = by_name.get(key)
            if existing is None:
                by_name[key] = signal
                continue
            if _STRENGTH_PRIORITY.get(signal.strength, 0) > _STRENGTH_PRIORITY.get(existing.strength, 0):
                by_name[key] = signal
        return list(by_name.values())

    @staticmethod
    def _compute_signal_quality(skill_signals: list[QuerySignal], capability_signals: list[QuerySignal]) -> dict[str, float | int]:
        all_signals = [*skill_signals, *capability_signals]
        total = len(all_signals)
        unknown = sum(1 for s in all_signals if s.strength == "unknown")
        must_have = sum(1 for s in all_signals if s.strength == "must have")
        familiarity = sum(1 for s in all_signals if s.strength == "familiarity")
        unknown_ratio = round((unknown / total), 4) if total > 0 else 0.0
        return {
            "total_signals": total,
            "unknown_signals": unknown,
            "must_have_signals": must_have,
            "familiarity_signals": familiarity,
            "unknown_ratio": unknown_ratio,
        }

    def _merge_profiles(self, *, primary: JobProfile, fallback: JobProfile) -> JobProfile:
        required_skills = dedupe_preserve([*fallback.required_skills, *primary.required_skills])
        expanded_skills = dedupe_preserve([*fallback.expanded_skills, *primary.expanded_skills])
        related_skills = [skill for skill in expanded_skills if skill not in set(required_skills)]
        roles = dedupe_preserve([*fallback.roles, *primary.roles])
        skill_signals = self._dedupe_signals([*fallback.skill_signals, *primary.skill_signals])
        capability_signals = self._dedupe_signals([*fallback.capability_signals, *primary.capability_signals])
        signal_quality = self._compute_signal_quality(skill_signals, capability_signals)
        semantic_query_expansion = dedupe_preserve(
            [*fallback.semantic_query_expansion, *primary.semantic_query_expansion]
        )
        return JobProfile(
            required_skills=required_skills,
            expanded_skills=expanded_skills,
            required_experience_years=primary.required_experience_years or fallback.required_experience_years,
            preferred_seniority=fallback.preferred_seniority or primary.preferred_seniority,
            job_category=fallback.job_category or primary.job_category,
            related_skills=related_skills,
            filters=primary.filters,
            query_text_for_embedding=fallback.query_text_for_embedding or primary.query_text_for_embedding,
            confidence=max(primary.confidence, fallback.confidence),
            roles=roles,
            skill_signals=skill_signals,
            capability_signals=capability_signals,
            lexical_query=fallback.lexical_query or primary.lexical_query,
            semantic_query_expansion=semantic_query_expansion,
            metadata_filters=primary.metadata_filters,
            transferable_skill_score=max(primary.transferable_skill_score, fallback.transferable_skill_score),
            transferable_skill_evidence=dedupe_preserve(
                [*fallback.transferable_skill_evidence, *primary.transferable_skill_evidence]
            )[:8],
            signal_quality=signal_quality,
        )


matching_service = MatchingService()
