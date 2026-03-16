from __future__ import annotations

from backend.core.collections import dedupe_preserve
from backend.core.settings import settings
from backend.services.job_profile.signals import compute_signal_quality, dedupe_signals
from backend.services.job_profile_extractor import JobProfile


def should_use_query_fallback(job_profile: JobProfile) -> tuple[bool, str | None, dict[str, float]]:
    if not settings.query_fallback_enabled:
        return False, None, {}
    confidence = float(job_profile.confidence)
    unknown_ratio = float(job_profile.signal_quality.get("unknown_ratio", 0.0))
    if confidence < float(settings.query_fallback_confidence_threshold):
        return True, "low_confidence", {"confidence": confidence, "unknown_ratio": unknown_ratio}
    if unknown_ratio > float(settings.query_fallback_unknown_ratio_threshold):
        return True, "high_unknown_ratio", {"confidence": confidence, "unknown_ratio": unknown_ratio}
    return False, None, {"confidence": confidence, "unknown_ratio": unknown_ratio}

def merge_job_profiles(*, primary: JobProfile, fallback: JobProfile) -> JobProfile:
    required_skills = dedupe_preserve([*fallback.required_skills, *primary.required_skills])
    expanded_skills = dedupe_preserve([*fallback.expanded_skills, *primary.expanded_skills])
    related_skills = [skill for skill in expanded_skills if skill not in set(required_skills)]
    roles = dedupe_preserve([*fallback.roles, *primary.roles])
    skill_signals = dedupe_signals([*fallback.skill_signals, *primary.skill_signals])
    capability_signals = dedupe_signals([*fallback.capability_signals, *primary.capability_signals])
    signal_quality = compute_signal_quality(skill_signals, capability_signals)
    semantic_query_expansion = dedupe_preserve([*fallback.semantic_query_expansion, *primary.semantic_query_expansion])
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
