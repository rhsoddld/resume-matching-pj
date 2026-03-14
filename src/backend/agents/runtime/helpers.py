from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any

from backend.agents.contracts.ranking_agent import AgentWeights, RankingAgentInput
from backend.agents.contracts.weight_negotiation_agent import WeightNegotiationOutput, WeightProposal


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def normalize_weight_payload(payload: dict[str, Any]) -> dict[str, float]:
    skill = float(payload.get("skill", 0.0))
    experience = float(payload.get("experience", 0.0))
    technical = float(payload.get("technical", 0.0))
    culture = float(payload.get("culture", 0.0))
    total = skill + experience + technical + culture
    if total <= 0.0:
        return {"skill": 0.35, "experience": 0.30, "technical": 0.20, "culture": 0.15}
    return {
        "skill": round(skill / total, 4),
        "experience": round(experience / total, 4),
        "technical": round(technical / total, 4),
        "culture": round(culture / total, 4),
    }


def build_fallback_weight_negotiation(required_experience_years: float | None, required_skills: list[str]) -> WeightNegotiationOutput:
    recruiter = {"skill": 0.30, "experience": 0.35, "technical": 0.20, "culture": 0.15}
    hiring_manager = {"skill": 0.40, "experience": 0.20, "technical": 0.30, "culture": 0.10}

    if required_experience_years and required_experience_years >= 5.0:
        recruiter["experience"] += 0.10
        recruiter["technical"] -= 0.05
        recruiter["culture"] -= 0.05

    if len(required_skills) >= 6:
        hiring_manager["technical"] += 0.10
        hiring_manager["experience"] -= 0.05
        hiring_manager["culture"] -= 0.05

    recruiter = normalize_weight_payload(recruiter)
    hiring_manager = normalize_weight_payload(hiring_manager)
    final = normalize_weight_payload(
        {
            "skill": (recruiter["skill"] + hiring_manager["skill"]) / 2.0,
            "experience": (recruiter["experience"] + hiring_manager["experience"]) / 2.0,
            "technical": (recruiter["technical"] + hiring_manager["technical"]) / 2.0,
            "culture": (recruiter["culture"] + hiring_manager["culture"]) / 2.0,
        }
    )

    return WeightNegotiationOutput(
        recruiter=WeightProposal.model_validate(recruiter),
        hiring_manager=WeightProposal.model_validate(hiring_manager),
        final=WeightProposal.model_validate(final),
        rationale=(
            "Fallback A2A negotiation: recruiter biases experience/culture, "
            "hiring manager biases skill/technical, final is normalized midpoint."
        ),
    )


def safe_json_load(content: Any) -> dict[str, Any]:
    if not content or not isinstance(content, str):
        return {}
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json", "", 1).strip()
    data = json.loads(text)
    return data if isinstance(data, dict) else {}


def extract_evidence_sentences(*, text: str, terms: list[str], limit: int = 4) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    normalized_terms = [term.strip().lower() for term in terms if isinstance(term, str) and term.strip()]
    if not normalized_terms:
        return []

    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s and s.strip()]
    scored: list[tuple[int, str]] = []
    for sentence in sentences:
        lowered = sentence.lower()
        hits = sum(1 for term in normalized_terms if term in lowered)
        if hits <= 0 or len(sentence) < 25:
            continue
        scored.append((hits, sentence[:220]))
    scored.sort(key=lambda item: item[0], reverse=True)

    out: list[str] = []
    seen: set[str] = set()
    for _, sentence in scored:
        if sentence in seen:
            continue
        seen.add(sentence)
        out.append(sentence)
        if len(out) >= limit:
            break
    return out


def parse_date_token(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    token = value.strip().lower()
    if token in {"present", "current", "now"}:
        return datetime.utcnow()
    for fmt in ("%Y-%m", "%Y/%m", "%Y"):
        try:
            return datetime.strptime(token, fmt)
        except ValueError:
            continue
    return None


def compute_skill_score(required_skills: list[str], candidate_skills: list[str]) -> float:
    required = {item.strip().lower() for item in required_skills if item}
    if not required:
        return 0.0
    candidate = {item.strip().lower() for item in candidate_skills if item}
    return round(len(required.intersection(candidate)) / len(required), 4)


def compute_experience_fit(*, required_experience_years: float | None, candidate_experience_years: float | None) -> float:
    if required_experience_years is None:
        return 0.5
    if candidate_experience_years is None:
        return 0.0
    if required_experience_years <= 0:
        return 1.0
    return round(min(1.0, candidate_experience_years / required_experience_years), 4)


def compute_seniority_fit(*, preferred_seniority: str | None, candidate_seniority: str | None) -> float:
    if preferred_seniority is None:
        return 0.5
    if candidate_seniority is None:
        return 0.0
    return 1.0 if preferred_seniority.strip().lower() == candidate_seniority.strip().lower() else 0.4


def compute_weighted_score(ranking_input: RankingAgentInput) -> float:
    weights: AgentWeights = ranking_input.weights
    weighted = (
        ranking_input.skill_score * weights.skill
        + ranking_input.experience_score * weights.experience
        + ranking_input.technical_score * weights.technical
        + ranking_input.culture_score * weights.culture
    )
    return round(min(1.0, max(0.0, weighted)), 4)
