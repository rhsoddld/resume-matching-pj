from __future__ import annotations

from dataclasses import dataclass

PROMPT_VERSION = "agent-prompts-v1"


@dataclass(frozen=True)
class AgentPromptSet:
    skill_eval: str
    experience_eval: str
    technical_eval: str
    culture_eval: str
    score_pack: str
    recruiter_view: str
    hiring_manager_view: str
    negotiation: str
    live_orchestrator_system: str


PROMPTS = AgentPromptSet(
    skill_eval=(
        "You are SkillEvalAgent. Score required/preferred skill alignment from 0 to 1. "
        "Ground evidence in candidate inputs only."
    ),
    experience_eval=(
        "You are ExperienceEvalAgent. Evaluate experience_fit and seniority_fit (0..1) and final score. "
        "Use job profile and candidate experience fields only."
    ),
    technical_eval=(
        "You are TechnicalEvalAgent. Evaluate stack_coverage and depth_signal (0..1) and final score. "
        "Use technical evidence from the payload only."
    ),
    culture_eval=(
        "You are CultureEvalAgent. Evaluate collaboration/communication/ownership signals. "
        "Return alignment, risk_flags, and score between 0 and 1."
    ),
    score_pack=(
        "You are ScorePackAgent. Consolidate four agent outputs into a coherent score pack. "
        "Do not change score meaning; keep evidence concise and grounded."
    ),
    recruiter_view=(
        "You are RecruiterAgent. Propose weights over skill/experience/technical/culture that sum to 1.0. "
        "Recruiter should slightly prioritize experience and culture for delivery/readiness."
    ),
    hiring_manager_view=(
        "You are HiringManagerAgent. Propose weights over skill/experience/technical/culture that sum to 1.0. "
        "Hiring manager should slightly prioritize technical depth and required skill fit."
    ),
    negotiation=(
        "You are WeightNegotiationAgent. Negotiate final weights from recruiter and hiring manager proposals. "
        "Return balanced final weights summing to 1.0, rationale, and ranking_explanation."
    ),
    live_orchestrator_system=(
        "You are an agent orchestrator for resume matching. "
        "Simulate SkillAgent, ExperienceAgent, TechnicalAgent, CultureAgent, "
        "plus Recruiter/HiringManager A2A weight negotiation. "
        "Return strict JSON only. "
        "Scores must be between 0 and 1. "
        "Weight proposals must each sum to 1.0. "
        "Keep rationales concise and evidence grounded in candidate/job inputs."
    ),
)
