from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from backend.agents.contracts.culture_agent import CultureAgentOutput
from backend.agents.contracts.experience_agent import ExperienceAgentOutput
from backend.agents.contracts.skill_agent import SkillAgentOutput
from backend.agents.contracts.technical_agent import TechnicalAgentOutput
from backend.agents.contracts.weight_negotiation_agent import WeightNegotiationOutput, WeightProposal

from .helpers import normalize_weight_payload, safe_json_load
from .prompts import PROMPTS
from .types import AgentExecutionResult
from backend.core.observability import traceable_op

logger = logging.getLogger(__name__)


LIVE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "skill_output": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "matched_skills": {"type": "array", "items": {"type": "string"}},
                "missing_skills": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"},
            },
            "required": ["score", "matched_skills", "missing_skills", "evidence", "rationale"],
        },
        "experience_output": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "experience_fit": {"type": "number"},
                "seniority_fit": {"type": "number"},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"},
            },
            "required": ["score", "experience_fit", "seniority_fit", "evidence", "rationale"],
        },
        "technical_output": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "stack_coverage": {"type": "number"},
                "depth_signal": {"type": "number"},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"},
            },
            "required": ["score", "stack_coverage", "depth_signal", "evidence", "rationale"],
        },
        "culture_output": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "alignment": {"type": "number"},
                "risk_flags": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"},
            },
            "required": ["score", "alignment", "risk_flags", "evidence", "rationale"],
        },
        "weight_negotiation": {
            "type": "object",
            "properties": {
                "recruiter": {
                    "type": "object",
                    "properties": {
                        "skill": {"type": "number"},
                        "experience": {"type": "number"},
                        "technical": {"type": "number"},
                        "culture": {"type": "number"},
                    },
                    "required": ["skill", "experience", "technical", "culture"],
                },
                "hiring_manager": {
                    "type": "object",
                    "properties": {
                        "skill": {"type": "number"},
                        "experience": {"type": "number"},
                        "technical": {"type": "number"},
                        "culture": {"type": "number"},
                    },
                    "required": ["skill", "experience", "technical", "culture"],
                },
                "final": {
                    "type": "object",
                    "properties": {
                        "skill": {"type": "number"},
                        "experience": {"type": "number"},
                        "technical": {"type": "number"},
                        "culture": {"type": "number"},
                    },
                    "required": ["skill", "experience", "technical", "culture"],
                },
                "rationale": {"type": "string"},
            },
            "required": ["recruiter", "hiring_manager", "final", "rationale"],
        },
        "ranking_explanation": {"type": "string"},
    },
    "required": [
        "skill_output",
        "experience_output",
        "technical_output",
        "culture_output",
        "weight_negotiation",
        "ranking_explanation",
    ],
}


@traceable_op(name="agents.live_runner", run_type="chain", tags=["agents", "live_json"])
def run_live_agents(
    *,
    client: OpenAI,
    model: str,
    payload: dict[str, Any],
) -> AgentExecutionResult | None:
    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PROMPTS.live_orchestrator_system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": "Produce outputs matching this JSON schema exactly.",
                            "json_schema": LIVE_OUTPUT_SCHEMA,
                            "payload": payload,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        raw_content = completion.choices[0].message.content if completion.choices else None
        data = safe_json_load(raw_content)

        skill_output = SkillAgentOutput.model_validate(data.get("skill_output", {}))
        experience_output = ExperienceAgentOutput.model_validate(data.get("experience_output", {}))
        technical_output = TechnicalAgentOutput.model_validate(data.get("technical_output", {}))
        culture_output = CultureAgentOutput.model_validate(data.get("culture_output", {}))

        raw_negotiation = data.get("weight_negotiation", {})
        recruiter = WeightProposal.model_validate(
            normalize_weight_payload(raw_negotiation.get("recruiter", {}))
        )
        hiring_manager = WeightProposal.model_validate(
            normalize_weight_payload(raw_negotiation.get("hiring_manager", {}))
        )
        final = WeightProposal.model_validate(normalize_weight_payload(raw_negotiation.get("final", {})))
        ranking_explanation = str(data.get("ranking_explanation", ""))
        ranking_explanation = ranking_explanation or "Agent weighted ranking from negotiated A2A policy."
        weight_negotiation = WeightNegotiationOutput(
            recruiter=recruiter,
            hiring_manager=hiring_manager,
            final=final,
            rationale=str(raw_negotiation.get("rationale", "")),
            ranking_explanation=ranking_explanation,
        )

        return AgentExecutionResult(
            skill_output=skill_output,
            experience_output=experience_output,
            technical_output=technical_output,
            culture_output=culture_output,
            weight_negotiation=weight_negotiation,
            ranking_explanation=ranking_explanation,
            runtime_mode="live_json",
            runtime_reason="live_json_success",
        )
    except Exception:
        logger.exception("Live agent scoring failed; fallback heuristics will be used.")
        return None
