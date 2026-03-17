from __future__ import annotations

from typing import Any
import logging
import concurrent.futures

try:
    from langsmith import get_current_run_tree
except ImportError:
    get_current_run_tree = None

from backend.core.model_routing import resolve_rerank_model
from backend.core.observability import traceable_op
from backend.core.providers import get_skill_ontology
from backend.core.settings import settings
from backend.services.hybrid_retriever import HybridRetriever
from backend.schemas.job import FairnessAudit, JobMatchCandidate, JobMatchResponse, QueryUnderstandingProfile
from backend.agents import agent_orchestration_service
from backend.services.candidate_enricher import enrich_hits
from backend.services.cross_encoder_rerank_service import cross_encoder_rerank_service
from backend.services.job_profile_extractor import JobProfile, build_job_profile
from backend.services.matching.cache import ResponseLRUCache
from backend.services.matching.fairness import is_agent_evaluated, run_fairness_guardrails
from backend.services.matching.evaluation import (
    run_scoped_candidate_evaluation,
    select_agent_eval_indices,
)
from backend.services.matching.profile import merge_job_profiles, should_use_query_fallback
from backend.services.matching.rerank_policy import (
    is_rerank_runtime_enabled,
    resolve_agent_eval_top_n,
    resolve_rerank_pool_n,
    resolve_retrieval_top_n,
    should_apply_rerank,
)
from backend.services.match_result_builder import build_match_candidate
from backend.services.query_fallback_service import query_fallback_service


logger = logging.getLogger(__name__)


class MatchingService:
    def __init__(self) -> None:
        self.hybrid_retriever = HybridRetriever()
        self.rerank_service = cross_encoder_rerank_service
        self._cache = ResponseLRUCache(
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
            cache_key = self._cache.make_key(
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

        retrieval_top_n = resolve_retrieval_top_n(top_k)
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

        response = self._build_match_response(
            job_profile=job_profile,
            matches=results,
            fairness_audit=fairness_audit,
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
        from backend.repositories.session_repo import create_jd_session
        
        event_queue = queue.Queue()

        # --- Token cache lookup (R2.5) ---
        cache_key: str | None = None
        if settings.token_cache_enabled:
            cache_key = self._cache.make_key(
                job_description=job_description,
                top_k=top_k,
                category=category,
                min_experience_years=min_experience_years,
                education=education,
                region=region,
                industry=industry,
            )
            cached = self._cache.get(cache_key)
            if isinstance(cached, JobMatchResponse):
                logger.info("token_cache_hit key=%s source=stream", cache_key)
                profile_payload = {
                    "job_category": cached.query_profile.job_category,
                    "roles": cached.query_profile.roles,
                    "required_skills": cached.query_profile.required_skills,
                    "confidence": cached.query_profile.confidence,
                }
                yield f"event: profile\ndata: {json.dumps(profile_payload, ensure_ascii=False)}\n\n"
                try:
                    session_id = create_jd_session(
                        job_description=job_description,
                        query_profile=profile_payload,
                    )
                    yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"
                except Exception as _session_exc:
                    logger.warning("stream: Failed to create JD session (non-fatal): %s", _session_exc)

                for candidate in cached.matches:
                    yield f"event: candidate\ndata: {candidate.model_dump_json()}\n\n"
                yield f"event: fairness\ndata: {cached.fairness.model_dump_json()}\n\n"
                yield "event: done\ndata: {}\n\n"
                return
            if cached is not None:
                logger.warning("token_cache_unexpected_type key=%s source=stream", cache_key)
            logger.info("token_cache_miss key=%s source=stream", cache_key)
        
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

        retrieval_top_n = resolve_retrieval_top_n(top_k)
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

        if not shortlisted_hits:
            fairness_audit = self._run_fairness_guardrails(
                job_description=job_description,
                job_profile=job_profile,
                matches=[],
                top_k=top_k,
            )
            if settings.token_cache_enabled and cache_key is not None:
                response = self._build_match_response(
                    job_profile=job_profile,
                    matches=[],
                    fairness_audit=fairness_audit,
                )
                self._cache.set(cache_key, response)
            yield f"event: fairness\ndata: {fairness_audit.model_dump_json()}\n\n"
            yield "event: done\ndata: {}\n\n"
            return
        
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

        _, eval_index_set = select_agent_eval_indices(prelim_results, agent_eval_top_n)

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
            
            return self._build_deterministic_candidate(
                hit=hit,
                candidate_doc=candidate_doc,
                job_profile=job_profile,
                category=category,
                reason=f"outside_agent_eval_top_n({agent_eval_top_n})",
            )

        finished_candidates = []
        active_futures = set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(10, len(shortlisted_hits)))) as executor:
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
                done, _ = concurrent.futures.wait(
                    active_futures, 
                    timeout=0.1, 
                    return_when=concurrent.futures.FIRST_COMPLETED
                )
                
                for future in done:
                    active_futures.remove(future)
                    idx = future_to_idx[future]
                    hit, candidate_doc = shortlisted_hits[idx]
                    try:
                        candidate_result = future.result()
                        finished_candidates.append(candidate_result)
                        # Put candidate result into the queue to maintain ordering
                        event_queue.put(f"event: candidate\ndata: {candidate_result.model_dump_json()}\n\n")
                    except Exception as exc:
                        logger.exception("Failed streaming candidate evaluation. idx=%s", idx)
                        fallback_candidate = self._build_deterministic_candidate(
                            hit=hit,
                            candidate_doc=candidate_doc,
                            job_profile=job_profile,
                            category=category,
                            reason=f"agent_evaluation_failed({exc.__class__.__name__})",
                        )
                        finished_candidates.append(fallback_candidate)
                        event_queue.put(f"event: candidate\ndata: {fallback_candidate.model_dump_json()}\n\n")
            
            # Final drain of the queue after all futures complete
            while not event_queue.empty():
                yield event_queue.get_nowait()

        # Finally, yield fairness audit
        finished_candidates.sort(
            key=lambda item: (
                0 if is_agent_evaluated(item) else 1,
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

        # --- Token cache store (R2.5) ---
        if settings.token_cache_enabled and cache_key is not None:
            response = self._build_match_response(
                job_profile=job_profile,
                matches=finished_candidates,
                fairness_audit=fairness_audit,
            )
            self._cache.set(cache_key, response)
        
        # End stream
        yield "event: done\ndata: {}\n\n"


    def _build_match_response(
        self,
        *,
        job_profile: JobProfile,
        matches: list[JobMatchCandidate],
        fairness_audit: FairnessAudit,
    ) -> JobMatchResponse:
        return JobMatchResponse(
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
            matches=matches,
            fairness=fairness_audit,
        )


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
        should_fallback, fallback_reason, fallback_trigger = should_use_query_fallback(deterministic_profile)
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
                job_profile = merge_job_profiles(primary=deterministic_profile, fallback=fallback_profile)
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
        if not shortlisted_hits:
            return []

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

        selected_indices, eval_index_set = select_agent_eval_indices(prelim_results, agent_eval_top_n)
        logger.info(
            "agent_eval_selection selected=%s candidate_ids=%s",
            len(eval_index_set),
            [prelim_results[idx].candidate_id for idx in selected_indices],
        )

        outside_scope_reason = f"outside_agent_eval_top_n({agent_eval_top_n})"
        results = run_scoped_candidate_evaluation(
            shortlisted_hits=shortlisted_hits,
            eval_index_set=eval_index_set,
            evaluate_with_agent=lambda hit, candidate_doc: build_match_candidate(
                hit=hit,
                candidate_doc=candidate_doc,
                job_profile=job_profile,
                category=category,
                agent_result=agent_orchestration_service.run_for_candidate(
                    job_description=job_description,
                    job_profile=job_profile,
                    hit=hit,
                    candidate_doc=candidate_doc,
                    category_filter=category,
                ),
                agent_evaluation_applied=True,
            ),
            build_deterministic=lambda hit, candidate_doc, reason: self._build_deterministic_candidate(
                hit=hit,
                candidate_doc=candidate_doc,
                job_profile=job_profile,
                category=category,
                reason=reason,
            ),
            outside_scope_reason=outside_scope_reason,
            logger=logger,
        )
        results.sort(
            key=lambda item: (
                0 if is_agent_evaluated(item) else 1,
                -item.score,
            )
        )
        return results

    def _build_deterministic_candidate(
        self,
        *,
        hit: dict[str, Any],
        candidate_doc: dict[str, Any],
        job_profile: JobProfile,
        category: str | None,
        reason: str,
    ) -> JobMatchCandidate:
        return build_match_candidate(
            hit=hit,
            candidate_doc=candidate_doc,
            job_profile=job_profile,
            category=category,
            agent_result=None,
            agent_evaluation_applied=False,
            agent_evaluation_reason=reason,
        )

    @traceable_op(name="matching.fairness_guardrails", run_type="tool", tags=["matching", "fairness"])
    def _run_fairness_guardrails(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        matches: list[JobMatchCandidate],
        top_k: int,
    ) -> FairnessAudit:
        return run_fairness_guardrails(
            job_description=job_description,
            job_profile=job_profile,
            matches=matches,
            top_k=top_k,
            logger=logger,
        )

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
        rerank_enabled, rerank_reason = is_rerank_runtime_enabled()
        if not rerank_enabled:
            logger.info("rerank_skipped reason=%s top_k=%s pool=%s", rerank_reason, top_k, len(enriched_hits))
            return enriched_hits[:top_k]

        should_apply, reason = should_apply_rerank(
            job_profile=job_profile,
            enriched_hits=enriched_hits,
            top_k=top_k,
        )
        if not should_apply:
            logger.info("rerank_skipped reason=%s top_k=%s pool=%s", reason, top_k, len(enriched_hits))
            return enriched_hits[:top_k]

        pool_n = resolve_rerank_pool_n(top_k)
        rerank_pool = enriched_hits[:pool_n]
        # Route to a higher-quality rerank model only when the query profile is ambiguous.
        # (Aligns with rerank gate logic: low confidence or high unknown_ratio.)
        unknown_ratio = float(job_profile.signal_quality.get("unknown_ratio", 0.0))
        ambiguous_query = (
            float(job_profile.confidence) < float(settings.rerank_gate_confidence_threshold)
            or unknown_ratio > float(settings.rerank_gate_unknown_ratio_threshold)
        )
        rerank_selection = resolve_rerank_model(high_quality=ambiguous_query)

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

    def _resolve_agent_eval_top_n(self, top_k: int) -> int:
        requested = max(0, int(settings.agent_eval_top_n))
        capped = min(top_k, requested)
        if not settings.token_budget_enabled:
            return capped

        adjusted = resolve_agent_eval_top_n(top_k)
        if adjusted != capped:
            budget = max(0, int(settings.token_budget_per_request))
            cost_per_candidate = max(1, int(settings.token_estimated_per_agent_call))
            available_for_agents = int(budget * 0.70)
            budget_cap = max(0, available_for_agents // cost_per_candidate)
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

    @traceable_op(name="matching.evaluate_candidate_on_demand", run_type="chain", tags=["matching", "agents"])
    def evaluate_candidate_on_demand(
        self,
        *,
        job_description: str,
        candidate_id: str,
        top_k: int = 100,
        category: str | None = None,
        min_experience_years: float | None = None,
        education: str | None = None,
        region: str | None = None,
        industry: str | None = None,
    ) -> JobMatchCandidate:
        """
        Run agent evaluation for a single candidate (e.g. one marked Deterministic only).
        Retrieves shortlist with top_k, finds the candidate, runs agent, returns updated match.
        """
        job_profile = self._build_query_profile(
            job_description=job_description,
            category_override=category,
            min_experience_years=min_experience_years,
            education_override=education,
            region_override=region,
            industry_override=industry,
        )
        retrieval_top_n = resolve_retrieval_top_n(top_k)
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
        candidate_id_str = str(candidate_id).strip()
        for hit, candidate_doc in shortlisted_hits:
            if str(hit.get("candidate_id", "")).strip() == candidate_id_str:
                agent_result = agent_orchestration_service.run_for_candidate(
                    job_description=job_description,
                    job_profile=job_profile,
                    hit=hit,
                    candidate_doc=candidate_doc,
                    category_filter=category,
                )
                return build_match_candidate(
                    hit=hit,
                    candidate_doc=candidate_doc,
                    job_profile=job_profile,
                    category=category,
                    agent_result=agent_result,
                    agent_evaluation_applied=True,
                )
        raise ValueError(
            f"Candidate {candidate_id_str!r} not found in top_{top_k} results for this job. "
            "Run a match first and open a candidate from the list to evaluate."
        )


matching_service = MatchingService()
