from __future__ import annotations

import json
import logging
from typing import Any

from backend.agents.contracts.culture_agent import CultureAgentOutput
from backend.agents.contracts.experience_agent import ExperienceAgentOutput
from backend.agents.contracts.skill_agent import SkillAgentOutput
from backend.agents.contracts.technical_agent import TechnicalAgentOutput
from backend.agents.contracts.weight_negotiation_agent import WeightNegotiationOutput, WeightProposal

from .helpers import normalize_weight_payload
from .models import NegotiationOutput, ScorePackOutput, ViewpointProposalOutput
from .prompts import PROMPTS
from .types import AgentExecutionResult

logger = logging.getLogger(__name__)


def run_agents_sdk(
    *,
    agent_cls: Any,
    runner_cls: Any,
    model: str,
    payload: dict[str, Any],
) -> AgentExecutionResult | None:
    payload_json = json.dumps(payload, ensure_ascii=False)

    try:
        skill_agent = agent_cls(
            name="SkillEvalAgent",
            model=model,
            instructions=PROMPTS.skill_eval,
            output_type=SkillAgentOutput,
        )
        experience_agent = agent_cls(
            name="ExperienceEvalAgent",
            model=model,
            instructions=PROMPTS.experience_eval,
            output_type=ExperienceAgentOutput,
        )
        technical_agent = agent_cls(
            name="TechnicalEvalAgent",
            model=model,
            instructions=PROMPTS.technical_eval,
            output_type=TechnicalAgentOutput,
        )
        culture_agent = agent_cls(
            name="CultureEvalAgent",
            model=model,
            instructions=PROMPTS.culture_eval,
            output_type=CultureAgentOutput,
        )

        skill_output = runner_cls.run_sync(skill_agent, payload_json).final_output
        experience_output = runner_cls.run_sync(experience_agent, payload_json).final_output
        technical_output = runner_cls.run_sync(technical_agent, payload_json).final_output
        culture_output = runner_cls.run_sync(culture_agent, payload_json).final_output

        score_pack_agent = agent_cls(
            name="ScorePackAgent",
            model=model,
            instructions=PROMPTS.score_pack,
            output_type=ScorePackOutput,
        )
        score_pack_input = json.dumps(
            {
                "payload": payload,
                "skill_output": skill_output.model_dump(),
                "experience_output": experience_output.model_dump(),
                "technical_output": technical_output.model_dump(),
                "culture_output": culture_output.model_dump(),
            },
            ensure_ascii=False,
        )
        score_pack = runner_cls.run_sync(score_pack_agent, score_pack_input).final_output

        recruiter_agent = agent_cls(
            name="RecruiterAgent",
            model=model,
            instructions=PROMPTS.recruiter_view,
            output_type=ViewpointProposalOutput,
        )
        hiring_manager_agent = agent_cls(
            name="HiringManagerAgent",
            model=model,
            instructions=PROMPTS.hiring_manager_view,
            output_type=ViewpointProposalOutput,
        )
        viewpoint_input = json.dumps(
            {"payload": payload, "score_pack": score_pack.model_dump()},
            ensure_ascii=False,
        )
        recruiter_view = runner_cls.run_sync(recruiter_agent, viewpoint_input).final_output
        hiring_manager_view = runner_cls.run_sync(hiring_manager_agent, viewpoint_input).final_output

        negotiation_agent = agent_cls(
            name="WeightNegotiationAgent",
            model=model,
            instructions=PROMPTS.negotiation,
            output_type=NegotiationOutput,
        )
        negotiation_input = json.dumps(
            {
                "payload": payload,
                "score_pack": score_pack.model_dump(),
                "recruiter": recruiter_view.model_dump(),
                "hiring_manager": hiring_manager_view.model_dump(),
            },
            ensure_ascii=False,
        )
        negotiation = runner_cls.run_sync(negotiation_agent, negotiation_input).final_output

        recruiter = WeightProposal.model_validate(
            normalize_weight_payload(recruiter_view.proposal.model_dump())
        )
        hiring_manager = WeightProposal.model_validate(
            normalize_weight_payload(hiring_manager_view.proposal.model_dump())
        )
        final = WeightProposal.model_validate(normalize_weight_payload(negotiation.final.model_dump()))
        weight_negotiation = WeightNegotiationOutput(
            recruiter=recruiter,
            hiring_manager=hiring_manager,
            final=final,
            rationale=(negotiation.rationale or "").strip(),
        )

        ranking_explanation = (
            (negotiation.ranking_explanation or "").strip()
            or (score_pack.ranking_explanation or "").strip()
            or "Agent weighted ranking from negotiated A2A policy."
        )
        return AgentExecutionResult(
            skill_output=score_pack.skill_output,
            experience_output=score_pack.experience_output,
            technical_output=score_pack.technical_output,
            culture_output=score_pack.culture_output,
            weight_negotiation=weight_negotiation,
            ranking_explanation=ranking_explanation,
        )
    except Exception:
        logger.exception("Agents SDK runtime scoring failed; fallback to legacy live/heuristic path.")
        return None
