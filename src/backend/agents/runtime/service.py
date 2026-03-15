from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Any

from backend.agents.contracts.orchestrator import CandidateAgentResult
from backend.agents.contracts.ranking_agent import RankingAgentInput, RankingAgentOutput, RankingBreakdown

from backend.core.observability import traceable_op
from backend.core.providers import get_openai_client
from backend.core.settings import settings
from backend.services.job_profile_extractor import JobProfile
from backend.core.jd_guardrails import wrap_untrusted_jd
from typing import Callable

from .candidate_mapper import build_candidate_input_bundle, build_runtime_payload
from .helpers import compute_weighted_score
from .heuristics import run_heuristic_agents
from .live_runner import run_live_agents
from .prompts import PROMPT_VERSION
from .sdk_runner import run_agents_sdk
from .sdk_runtime import load_agents_sdk_runtime, should_try_agents_sdk
from .types import CandidateInputBundle

logger = logging.getLogger(__name__)


@dataclass
class AgentOrchestrationService:
    """
    Production adapter:
    - runs OpenAI-based scoring (Agents SDK or Live JSON mode)
    - negotiates Recruiter/HiringManager weights (A2A)
    - falls back to deterministic heuristics on API/runtime errors
    """

    @traceable_op(name="agents.run_for_candidate", run_type="chain", tags=["agents", "ranking"])
    def run_for_candidate(
        self,
        *,
        job_description: str,
        job_profile: JobProfile,
        hit: dict[str, Any],
        candidate_doc: dict[str, Any],
        category_filter: str | None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> CandidateAgentResult:
        safe_jd = wrap_untrusted_jd(job_description)
        bundle = build_candidate_input_bundle(
            job_description=safe_jd,
            job_profile=job_profile,
            hit=hit,
            candidate_doc=candidate_doc,
        )
        payload = build_runtime_payload(
            job_description=safe_jd,
            job_profile=job_profile,
            hit=hit,
            category_filter=category_filter,
            bundle=bundle,
        )

        execution = self._execute(
            payload=payload,
            bundle=bundle,
            hit=hit,
            job_profile=job_profile,
            category_filter=category_filter,
            on_event=on_event,
        )

        ranking_input = RankingAgentInput(
            candidate_id=bundle.candidate_id,
            skill_score=execution.skill_output.score,
            experience_score=execution.experience_output.score,
            technical_score=execution.technical_output.score,
            culture_score=execution.culture_output.score,
            vector_score=round(float(hit.get("score", 0.0)), 4),
            deterministic_score=None,
            weights=execution.weight_negotiation.final.as_agent_weights(),
        )
        weighted_score = compute_weighted_score(ranking_input)
        ranking_output = RankingAgentOutput(
            final_score=weighted_score,
            breakdown=RankingBreakdown(
                skill=ranking_input.skill_score,
                experience=ranking_input.experience_score,
                technical=ranking_input.technical_score,
                culture=ranking_input.culture_score,
                weighted_score=weighted_score,
            ),
            explanation=(
                f"{execution.ranking_explanation} [prompt_version={PROMPT_VERSION}]"
            ),
        )

        return CandidateAgentResult(
            candidate_id=bundle.candidate_id,
            skill_output=execution.skill_output,
            experience_output=execution.experience_output,
            technical_output=execution.technical_output,
            culture_output=execution.culture_output,
            ranking_input=ranking_input,
            ranking_output=ranking_output,
            weight_negotiation=execution.weight_negotiation,
            runtime_mode=execution.runtime_mode,
            runtime_reason=execution.runtime_reason,
        )

    @traceable_op(name="agents.execute_runtime", run_type="chain", tags=["agents", "runtime"])
    def _execute(
        self,
        *,
        payload: dict[str, Any],
        bundle: CandidateInputBundle,
        hit: dict[str, Any],
        job_profile: JobProfile,
        category_filter: str | None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        live_enabled, live_reason = self._live_gate_status()
        fallback_reason = live_reason

        if live_enabled and should_try_agents_sdk():
            runtime = load_agents_sdk_runtime()
            if runtime is not None:
                agent_cls, runner_cls = runtime
                sdk_result = run_agents_sdk(
                    agent_cls=agent_cls,
                    runner_cls=runner_cls,
                    model=settings.openai_agent_model,
                    payload=payload,
                    on_event=on_event,
                )
                if sdk_result is not None:
                    return sdk_result
                fallback_reason = "agents_sdk_failed"
            else:
                fallback_reason = "agents_sdk_unavailable"
        elif live_enabled and not should_try_agents_sdk():
            fallback_reason = "agents_sdk_disabled"

        if live_enabled:
            live_result = run_live_agents(
                client=get_openai_client(),
                model=settings.openai_agent_model,
                payload=payload,
            )
            if live_result is not None:
                return live_result
            fallback_reason = "live_json_failed"

        return run_heuristic_agents(
            bundle=bundle,
            hit=hit,
            job_profile=job_profile,
            category_filter=category_filter,
            runtime_reason=fallback_reason,
        )

    @staticmethod
    def _live_gate_status() -> tuple[bool, str]:
        if not settings.openai_agent_live_mode:
            return False, "openai_agent_live_mode_false"
        if os.getenv("PYTEST_CURRENT_TEST"):
            return False, "pytest_context"
        if not settings.openai_api_key:
            return False, "openai_api_key_missing"
        return True, "live_calls_enabled"


agent_orchestration_service = AgentOrchestrationService()
