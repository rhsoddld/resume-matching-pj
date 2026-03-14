from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.agents.contracts.culture_agent import CultureAgentInput, CultureAgentOutput
from backend.agents.contracts.experience_agent import ExperienceAgentInput, ExperienceAgentOutput
from backend.agents.contracts.skill_agent import SkillAgentInput, SkillAgentOutput
from backend.agents.contracts.technical_agent import TechnicalAgentInput, TechnicalAgentOutput
from backend.agents.contracts.weight_negotiation_agent import WeightNegotiationOutput


@dataclass(frozen=True)
class CandidateInputBundle:
    candidate_id: str
    parsed: dict[str, Any]
    skill_input: SkillAgentInput
    experience_input: ExperienceAgentInput
    technical_input: TechnicalAgentInput
    culture_input: CultureAgentInput


@dataclass(frozen=True)
class AgentExecutionResult:
    skill_output: SkillAgentOutput
    experience_output: ExperienceAgentOutput
    technical_output: TechnicalAgentOutput
    culture_output: CultureAgentOutput
    weight_negotiation: WeightNegotiationOutput
    ranking_explanation: str
