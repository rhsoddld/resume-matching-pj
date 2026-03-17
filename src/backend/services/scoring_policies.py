from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeterministicScoringPolicy:
    """
    Versioned, repo-managed scoring weights for deterministic match scoring.

    NOTE: These are intentionally NOT env-configurable to preserve reproducibility.
    """

    version: str
    semantic_weight: float
    skill_overlap_weight: float
    experience_weight: float
    seniority_weight: float
    category_bonus: float


DEFAULT_DETERMINISTIC_POLICY_VERSION = "v1"


_DETERMINISTIC_POLICIES: dict[str, DeterministicScoringPolicy] = {
    # Baseline: weights sum to 1.0; category_bonus is added (then clipped to [0,1]).
    "v1": DeterministicScoringPolicy(
        version="v1",
        semantic_weight=0.42,
        skill_overlap_weight=0.33,
        experience_weight=0.18,
        seniority_weight=0.07,
        category_bonus=0.03,
    ),
}


def get_deterministic_scoring_policy(version: str | None = None) -> DeterministicScoringPolicy:
    v = (version or DEFAULT_DETERMINISTIC_POLICY_VERSION).strip()
    policy = _DETERMINISTIC_POLICIES.get(v)
    if policy is None:
        known = ", ".join(sorted(_DETERMINISTIC_POLICIES.keys()))
        raise ValueError(f"Unknown deterministic scoring policy version='{v}'. Known: {known}")
    return policy

