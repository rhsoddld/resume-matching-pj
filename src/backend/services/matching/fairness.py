from __future__ import annotations

from collections import Counter
import logging
import re

from backend.core.collections import dedupe_preserve
from backend.core.settings import settings
from backend.schemas.job import FairnessAudit, FairnessWarning, JobMatchCandidate
from backend.services.job_profile_extractor import JobProfile


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
_FAIRNESS_CHECKS = [
    "sensitive_term_scan",
    "culture_weight_cap",
    "must_have_vs_culture_gate",
    "topk_seniority_distribution",
]


def extract_sensitive_terms(text: str | None) -> list[str]:
    if not text or not text.strip():
        return []
    hits = [match.group(1).lower() for match in _SENSITIVE_TERM_PATTERN.finditer(text)]
    return dedupe_preserve(hits)


def get_culture_weight(candidate: JobMatchCandidate) -> float | None:
    weights = candidate.agent_scores.get("weights")
    if not isinstance(weights, dict):
        return None
    value = weights.get("culture")
    if not isinstance(value, (int, float)):
        return None
    return float(value)


def get_culture_confidence(candidate: JobMatchCandidate) -> float | None:
    confidence = candidate.agent_scores.get("confidence")
    if not isinstance(confidence, dict):
        return None
    value = confidence.get("culture")
    if not isinstance(value, (int, float)):
        return None
    return float(value)


def normalize_seniority(value: str | None) -> str:
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


def is_agent_evaluated(candidate: JobMatchCandidate) -> bool:
    value = candidate.agent_scores.get("agent_evaluation_applied")
    if isinstance(value, bool):
        return value
    return candidate.agent_scores.get("runtime_mode") != "deterministic_only"


def run_fairness_guardrails(
    *,
    job_description: str,
    job_profile: JobProfile,
    matches: list[JobMatchCandidate],
    top_k: int,
    logger: logging.Logger,
) -> FairnessAudit:
    if not settings.fairness_guardrails_enabled:
        return FairnessAudit(
            enabled=False,
            policy_version=settings.fairness_policy_version,
            checks_run=_FAIRNESS_CHECKS,
            warnings=[],
        )

    warnings: list[FairnessWarning] = []
    sensitive_terms_in_query = extract_sensitive_terms(job_description) if settings.fairness_sensitive_term_enabled else []
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
            sensitive_terms = extract_sensitive_terms(" ".join([candidate.summary or "", candidate.agent_explanation or ""]))
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

        culture_weight = get_culture_weight(candidate)
        if culture_weight is not None and culture_weight > float(settings.fairness_max_culture_weight):
            message = "Culture weight exceeded fairness cap. Skill and technical evidence should remain dominant."
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
        culture_confidence = get_culture_confidence(candidate)
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
        normalized_seniority = [normalize_seniority(candidate.seniority_level) for candidate in top_results]
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
                        candidate_ids=[
                            candidate.candidate_id
                            for candidate in top_results
                            if normalize_seniority(candidate.seniority_level) == dominant
                        ],
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
        checks_run=_FAIRNESS_CHECKS,
        warnings=warnings,
    )

