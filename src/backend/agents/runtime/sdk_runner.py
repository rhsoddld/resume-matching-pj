from __future__ import annotations

import inspect
import json
import logging
import os
from typing import Any, Callable

from pydantic import BaseModel, Field

from backend.agents.contracts.culture_agent import CultureAgentOutput
from backend.agents.contracts.experience_agent import ExperienceAgentOutput
from backend.agents.contracts.skill_agent import SkillAgentOutput
from backend.agents.contracts.technical_agent import TechnicalAgentOutput
from backend.agents.contracts.weight_negotiation_agent import WeightNegotiationOutput, WeightProposal
from backend.core.settings import settings

try:
    from agents import AgentOutputSchema
except ImportError:
    class AgentOutputSchema:
        def __init__(self, cls, strict_json_schema=False):
            self.cls = cls
            
def _wrap_output(cls: Any) -> Any:
    try:
        from agents import AgentOutputSchema
        return AgentOutputSchema(cls, strict_json_schema=False)
    except ImportError:
        return cls

from .helpers import normalize_weight_payload
from .helpers import build_fallback_weight_negotiation
from .models import HandoffRunContext, NegotiationOutput, ScorePackOutput, ViewpointProposalOutput
from .prompts import PROMPTS
from .types import AgentExecutionResult

logger = logging.getLogger(__name__)
_LANGSMITH_TRACING_CONFIGURED = False


class _SdkSkillAgentOutput(BaseModel):
    score: float | None = None
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    rationale: str = ""


class _SdkExperienceAgentOutput(BaseModel):
    score: float | None = None
    experience_fit: float | None = None
    seniority_fit: float | None = None
    career_trajectory: dict = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    rationale: str = ""


class _SdkTechnicalAgentOutput(BaseModel):
    score: float | None = None
    stack_coverage: float | None = None
    depth_signal: float | None = None
    evidence: list[str] = Field(default_factory=list)
    rationale: str = ""


class _SdkCultureAgentOutput(BaseModel):
    score: float | None = None
    alignment: float | None = None
    potential_score: float | None = None
    potential_level: str = "unknown"
    risk_flags: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    potential_evidence: list[str] = Field(default_factory=list)
    rationale: str = ""


class _SdkScorePackOutput(BaseModel):
    skill_output: _SdkSkillAgentOutput | dict[str, Any] | None = None
    experience_output: _SdkExperienceAgentOutput | dict[str, Any] | None = None
    technical_output: _SdkTechnicalAgentOutput | dict[str, Any] | None = None
    culture_output: _SdkCultureAgentOutput | dict[str, Any] | None = None
    ranking_explanation: str = ""


def _maybe_enable_langsmith_tracing() -> None:
    """Attach LangSmith tracing processor for OpenAI Agents SDK when enabled."""
    global _LANGSMITH_TRACING_CONFIGURED
    if _LANGSMITH_TRACING_CONFIGURED or not settings.langsmith_tracing:
        return

    if not settings.langsmith_api_key:
        logger.info("LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is missing; skip tracing setup.")
        return

    # Keep app settings as the source of truth even when process env is not exported.
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    if settings.langsmith_endpoint:
        os.environ.setdefault("LANGSMITH_ENDPOINT", settings.langsmith_endpoint)
    if settings.langsmith_project:
        os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)

    try:
        from agents import set_trace_processors
        from langsmith.integrations.openai_agents_sdk import OpenAIAgentsTracingProcessor
    except Exception:
        logger.exception("Failed to import LangSmith OpenAI Agents tracing integration; skip tracing setup.")
        return

    try:
        set_trace_processors(
            [OpenAIAgentsTracingProcessor(project_name=settings.langsmith_project)]
        )
        _LANGSMITH_TRACING_CONFIGURED = True
    except Exception:
        logger.exception("Failed to initialize LangSmith tracing processor; skip tracing setup.")


def _build_agent(agent_cls: Any, **kwargs: Any) -> Any:
    """Construct agent instance while tolerating SDK signature differences."""
    sig = inspect.signature(agent_cls)
    accepts_var_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values()
    )
    accepted = kwargs if accepts_var_kwargs else {name: value for name, value in kwargs.items() if name in sig.parameters}
    return agent_cls(**accepted)


def _run_sync_with_context(
    runner_cls: Any,
    *,
    start_agent: Any,
    input_text: str,
    run_context: dict[str, Any],
    max_turns: int,
) -> Any:
    run_sig = inspect.signature(runner_cls.run_sync)
    kwargs: dict[str, Any] = {}
    if "context" in run_sig.parameters:
        kwargs["context"] = run_context
    elif "run_context" in run_sig.parameters:
        kwargs["run_context"] = run_context
    if "max_turns" in run_sig.parameters:
        kwargs["max_turns"] = max_turns
    return runner_cls.run_sync(start_agent, input_text, **kwargs)


def _proposal_distance(a: WeightProposal, b: WeightProposal) -> float:
    return (
        abs(a.skill - b.skill)
        + abs(a.experience - b.experience)
        + abs(a.technical - b.technical)
        + abs(a.culture - b.culture)
    ) / 4.0


def _clip_01(value: float | None, *, default: float = 0.0) -> float:
    if not isinstance(value, (int, float)):
        return round(default, 4)
    return round(max(0.0, min(1.0, float(value))), 4)


def _as_model_data(raw_output: Any) -> dict[str, Any]:
    if isinstance(raw_output, BaseModel):
        return raw_output.model_dump()
    if isinstance(raw_output, dict):
        return dict(raw_output)
    return {}


def _build_slim_payload_for_handoff(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal payload for A2A handoff to cut token cost.

    Recruiter/HM/Negotiation only need job_profile, retrieval context, and a short
    candidate summary. Excludes job_description and full candidate inputs (including
    raw_resume_text) which are the main cost drivers when sent on every handoff turn.
    """
    candidate = payload.get("candidate") or {}
    skill_input = candidate.get("skill_input") or {}
    experience_input = candidate.get("experience_input") or {}
    return {
        "job_profile": payload.get("job_profile") or {},
        "retrieval_context": payload.get("retrieval_context") or {},
        "candidate": {
            "candidate_id": skill_input.get("candidate_id") or experience_input.get("candidate_id") or "",
            "candidate_summary": (skill_input.get("candidate_summary") or experience_input.get("candidate_summary") or "")[:2000],
        },
    }


def _coerce_skill_output(raw_output: Any) -> SkillAgentOutput:
    if isinstance(raw_output, SkillAgentOutput):
        return raw_output
    data = _as_model_data(raw_output)
    matched = [str(item).strip().lower() for item in (data.get("matched_skills") or []) if str(item).strip()]
    missing = [str(item).strip().lower() for item in (data.get("missing_skills") or []) if str(item).strip()]
    total = len(set(matched).union(missing))
    inferred_score = (len(set(matched)) / float(total)) if total > 0 else (0.5 if data.get("evidence") else 0.0)
    return SkillAgentOutput.model_validate(
        {
            **data,
            "score": _clip_01(data.get("score"), default=inferred_score),
            "matched_skills": matched,
            "missing_skills": missing,
        }
    )


def _coerce_experience_output(raw_output: Any) -> ExperienceAgentOutput:
    if isinstance(raw_output, ExperienceAgentOutput):
        return raw_output
    data = _as_model_data(raw_output)
    experience_fit = _clip_01(data.get("experience_fit"), default=0.5)
    seniority_fit = _clip_01(data.get("seniority_fit"), default=0.5)
    inferred_score = round((experience_fit + seniority_fit) / 2.0, 4)
    return ExperienceAgentOutput.model_validate(
        {
            **data,
            "score": _clip_01(data.get("score"), default=inferred_score),
            "experience_fit": experience_fit,
            "seniority_fit": seniority_fit,
        }
    )


def _coerce_technical_output(raw_output: Any) -> TechnicalAgentOutput:
    if isinstance(raw_output, TechnicalAgentOutput):
        return raw_output
    data = _as_model_data(raw_output)
    stack_coverage = _clip_01(data.get("stack_coverage"), default=0.0)
    depth_signal = _clip_01(data.get("depth_signal"), default=stack_coverage)
    inferred_score = round((stack_coverage + depth_signal) / 2.0, 4)
    return TechnicalAgentOutput.model_validate(
        {
            **data,
            "score": _clip_01(data.get("score"), default=inferred_score),
            "stack_coverage": stack_coverage,
            "depth_signal": depth_signal,
        }
    )


def _coerce_culture_output(raw_output: Any) -> CultureAgentOutput:
    if isinstance(raw_output, CultureAgentOutput):
        return raw_output
    data = _as_model_data(raw_output)
    alignment = _clip_01(data.get("alignment"), default=0.5)
    potential_score = _clip_01(data.get("potential_score"), default=0.0)
    inferred_score = alignment if potential_score <= 0.0 else round((alignment + potential_score) / 2.0, 4)
    return CultureAgentOutput.model_validate(
        {
            **data,
            "score": _clip_01(data.get("score"), default=inferred_score),
            "alignment": alignment,
            "potential_score": potential_score,
        }
    )


def _coerce_weight_negotiation_output(
    *,
    raw_output: Any,
    payload: dict[str, Any],
    score_pack: ScorePackOutput,
) -> WeightNegotiationOutput:
    if isinstance(raw_output, WeightNegotiationOutput):
        return raw_output

    fallback = build_fallback_weight_negotiation(
        payload.get("job_profile", {}).get("required_experience_years"),
        list(payload.get("job_profile", {}).get("required_skills") or []),
    )
    data = _as_model_data(raw_output)

    if isinstance(raw_output, ViewpointProposalOutput) or data.get("proposal") is not None:
        proposal_data = raw_output.proposal.model_dump() if isinstance(raw_output, ViewpointProposalOutput) else data.get("proposal", {})
        proposal = WeightProposal.model_validate(normalize_weight_payload(proposal_data or {}))
        rationale = (
            (getattr(raw_output, "rationale", "") if isinstance(raw_output, ViewpointProposalOutput) else data.get("rationale", ""))
            or "Agents SDK handoff returned a single viewpoint proposal; reused it as final negotiation output."
        )
        return WeightNegotiationOutput(
            recruiter=proposal,
            hiring_manager=proposal,
            final=proposal,
            rationale=str(rationale).strip(),
            ranking_explanation=(score_pack.ranking_explanation or "").strip(),
        )

    if isinstance(raw_output, NegotiationOutput) or data.get("final") is not None:
        final_data = raw_output.final.model_dump() if isinstance(raw_output, NegotiationOutput) else data.get("final", {})
        final = WeightProposal.model_validate(normalize_weight_payload(final_data or {}))
        return WeightNegotiationOutput(
            recruiter=fallback.recruiter,
            hiring_manager=fallback.hiring_manager,
            final=final,
            rationale=str(data.get("rationale", fallback.rationale)).strip(),
            ranking_explanation=str(data.get("ranking_explanation", score_pack.ranking_explanation)).strip(),
        )

    return fallback


def _coerce_score_pack_output(
    *,
    raw_output: Any,
    skill_output: SkillAgentOutput,
    experience_output: ExperienceAgentOutput,
    technical_output: TechnicalAgentOutput,
    culture_output: CultureAgentOutput,
) -> ScorePackOutput:
    if isinstance(raw_output, ScorePackOutput):
        return raw_output

    data = _as_model_data(raw_output)
    return ScorePackOutput(
        skill_output=_coerce_skill_output(data.get("skill_output") or skill_output),
        experience_output=_coerce_experience_output(data.get("experience_output") or experience_output),
        technical_output=_coerce_technical_output(data.get("technical_output") or technical_output),
        culture_output=_coerce_culture_output(data.get("culture_output") or culture_output),
        ranking_explanation=str(data.get("ranking_explanation", "")).strip(),
    )


def run_agents_sdk(
    *,
    agent_cls: Any,
    runner_cls: Any,
    model: str,
    payload: dict[str, Any],
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> AgentExecutionResult | None:
    _maybe_enable_langsmith_tracing()
    payload_json = json.dumps(payload, ensure_ascii=False)
    prior_env_api_key = os.environ.get("OPENAI_API_KEY")
    injected_env_api_key = False

    try:
        from backend.services.hybrid_retriever import HybridRetriever
        try:
            from agents import function_tool
        except ImportError:
            def function_tool(func): return func
            
        _retriever = HybridRetriever()
        _candidate_data = payload.get("candidate", {})
        _skill_input = _candidate_data.get("skill_input", {})
        _candidate_id = _skill_input.get("candidate_id")
        
        @function_tool
        def search_candidate_evidence(query: str) -> str:
            """
            Search specific evidence (like project metrics, specific skills, architecture details) 
            deeply within the current candidate's resume when the context doesn't have enough details.
            """
            if on_event:
                on_event(
                    "thought_process",
                    {
                        "agent": "CandidateEvaluator",
                        "action": "search_candidate_evidence",
                        "query": query,
                        "message": f"Searching resume source for '{query}'.",
                    },
                )

            if not _candidate_id:
                return "Candidate ID is unknown. Cannot search."
            return _retriever.search_within_candidate(_candidate_id, query)
    except Exception as e:
        logger.warning(f"Failed to create retrieval tool: {e}")
        def _fallback_tool(query: str) -> str:
            return "Tool unavailable."
        
        search_candidate_evidence = _fallback_tool
        try:
            from agents import function_tool
            search_candidate_evidence = function_tool(_fallback_tool)
        except ImportError:
            pass

    try:
        # Agents SDK runtime resolves credentials from OPENAI_API_KEY env var.
        # Keep local Settings as source of truth and bridge it only when missing.
        if not prior_env_api_key and settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
            injected_env_api_key = True

        skill_agent = _build_agent(
            agent_cls,
            name="SkillEvalAgent",
            model=model,
            instructions=(
                PROMPTS.skill_eval + 
                "\n정말 중대한 필수 요구 스킬(Core JD Requirements)이 누락되었다고 판단될 경우에만 search_candidate_evidence 도구를 사용하여 이력서 구조화 데이터를 1회 검색하세요. "
                "그 외의 정보 부족은 명시된 요약 데이터만으로 추론하여 결론을 내리세요."
            ),
            output_type=_wrap_output(_SdkSkillAgentOutput),
            tools=[search_candidate_evidence],
        )
        experience_agent = _build_agent(
            agent_cls,
            name="ExperienceEvalAgent",
            model=model,
            instructions=(
                PROMPTS.experience_eval + 
                "\n가장 핵심적인 성과 지표나 필수 경력 기간이 불분명할 경우에만 search_candidate_evidence 도구를 1회 호출하세요. "
                "그 외의 정보 부족은 명시된 데이터와 문맥만으로 평가를 완료하세요."
            ),
            output_type=_wrap_output(_SdkExperienceAgentOutput),
            tools=[search_candidate_evidence],
        )
        technical_agent = _build_agent(
            agent_cls,
            name="TechnicalEvalAgent",
            model=model,
            instructions=(
                PROMPTS.technical_eval + 
                "\n지원 직무의 핵심 필수 기술 스택의 실제 활용 여부를 도무지 파악할 수 없을 때만 search_candidate_evidence 도구를 1회 사용하세요. "
                "그 외의 경우는 주어진 정보 내에서 최선의 판단을 내리세요."
            ),
            output_type=_wrap_output(_SdkTechnicalAgentOutput),
            tools=[search_candidate_evidence],
        )
        culture_agent = _build_agent(
            agent_cls,
            name="CultureEvalAgent",
            model=model,
            instructions=(
                PROMPTS.culture_eval + 
                "\n정성적 평가(협업/소통/문제해결 등)에 대한 단서가 아예 전무하여 심각한 감점이 예상될 때만 제한적으로 search_candidate_evidence 도구를 1회 호출하세요."
            ),
            output_type=_wrap_output(_SdkCultureAgentOutput),
            tools=[search_candidate_evidence],
        )

        def _run_agent(name: str, agent: Any, prompt_input: str) -> Any:
            try:
                result = runner_cls.run_sync(agent, prompt_input)
                logger.debug("sdk_agent_ok agent=%s", name)
                return result.final_output
            except Exception as exc:
                logger.warning("sdk_agent_failed agent=%s error=%s", name, exc)
                raise

        skill_output = _coerce_skill_output(_run_agent("SkillEvalAgent", skill_agent, payload_json))
        experience_output = _coerce_experience_output(_run_agent("ExperienceEvalAgent", experience_agent, payload_json))
        technical_output = _coerce_technical_output(_run_agent("TechnicalEvalAgent", technical_agent, payload_json))
        culture_output = _coerce_culture_output(_run_agent("CultureEvalAgent", culture_agent, payload_json))

        score_pack_agent = agent_cls(
            name="ScorePackAgent",
            model=model,
            instructions=PROMPTS.score_pack,
            output_type=_wrap_output(_SdkScorePackOutput),
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
        try:
            raw_score_pack = runner_cls.run_sync(score_pack_agent, score_pack_input).final_output
        except Exception as exc:
            logger.warning("sdk_score_pack_failed error=%s; using synthesized score pack.", exc)
            raw_score_pack = {
                "skill_output": skill_output.model_dump(),
                "experience_output": experience_output.model_dump(),
                "technical_output": technical_output.model_dump(),
                "culture_output": culture_output.model_dump(),
                "ranking_explanation": "",
            }
        score_pack = _coerce_score_pack_output(
            raw_output=raw_score_pack,
            skill_output=skill_output,
            experience_output=experience_output,
            technical_output=technical_output,
            culture_output=culture_output,
        )

        handoff_context = HandoffRunContext(payload=payload, score_pack=score_pack)

        negotiation_agent = _build_agent(
            agent_cls,
            name="WeightNegotiationAgent",
            model=model,
            instructions=PROMPTS.negotiation,
            output_type=WeightNegotiationOutput,
        )
        hiring_manager_agent = _build_agent(
            agent_cls,
            name="HiringManagerAgent",
            model=model,
            instructions=PROMPTS.hiring_manager_view,
            output_type=ViewpointProposalOutput,
            handoffs=[negotiation_agent],
        )
        recruiter_agent = _build_agent(
            agent_cls,
            name="RecruiterAgent",
            model=model,
            instructions=PROMPTS.recruiter_view,
            output_type=ViewpointProposalOutput,
            handoffs=[hiring_manager_agent],
        )

        recruit_sig = inspect.signature(agent_cls)
        accepts_var_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD for param in recruit_sig.parameters.values()
        )
        if "handoffs" not in recruit_sig.parameters and not accepts_var_kwargs:
            raise RuntimeError("Agents SDK handoffs are not supported by installed runtime.")

        # Use slim payload (no job_description, no raw_resume_text) to reduce A2A token cost.
        slim_payload = _build_slim_payload_for_handoff(payload)
        handoff_input = json.dumps(
            {
                "payload": slim_payload,
                "score_pack": score_pack.model_dump(),
                "constraints": handoff_context.constraints.model_dump(),
                "instruction": (
                    "RecruiterAgent must propose weights then hand off to HiringManagerAgent. "
                    "HiringManagerAgent must review/challenge then hand off to WeightNegotiationAgent. "
                    "WeightNegotiationAgent must return final structured output."
                ),
            },
            ensure_ascii=False,
        )
        run_context_slim = {
            "payload": slim_payload,
            "score_pack": handoff_context.score_pack.model_dump(),
            "constraints": handoff_context.constraints.model_dump(),
        }
        run_result = _run_sync_with_context(
            runner_cls,
            start_agent=recruiter_agent,
            input_text=handoff_input,
            run_context=run_context_slim,
            max_turns=handoff_context.constraints.max_turns,
        )
        raw_negotiation = getattr(run_result, "final_output", run_result)
        weight_negotiation = _coerce_weight_negotiation_output(
            raw_output=raw_negotiation,
            payload=payload,
            score_pack=score_pack,
        )

        recruiter = WeightProposal.model_validate(
            normalize_weight_payload(weight_negotiation.recruiter.model_dump())
        )
        hiring_manager = WeightProposal.model_validate(
            normalize_weight_payload(weight_negotiation.hiring_manager.model_dump())
        )
        final = WeightProposal.model_validate(normalize_weight_payload(weight_negotiation.final.model_dump()))
        weight_negotiation = WeightNegotiationOutput(
            recruiter=recruiter,
            hiring_manager=hiring_manager,
            final=final,
            rationale=(weight_negotiation.rationale or "").strip(),
            ranking_explanation=(weight_negotiation.ranking_explanation or "").strip(),
        )

        disagreement = _proposal_distance(recruiter, hiring_manager)
        if disagreement > handoff_context.constraints.disagreement_threshold:
            raise ValueError(
                "A2A negotiation disagreement exceeded threshold "
                f"({disagreement:.3f}>{handoff_context.constraints.disagreement_threshold:.3f})"
            )

        ranking_explanation = (
            (weight_negotiation.ranking_explanation or "").strip()
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
            runtime_mode="sdk_handoff",
            runtime_reason="agents_sdk_handoff_success",
        )
    except Exception:
        logger.exception("Agents SDK runtime scoring failed; fallback to legacy live/heuristic path.")
        return None
    finally:
        if injected_env_api_key:
            os.environ.pop("OPENAI_API_KEY", None)
