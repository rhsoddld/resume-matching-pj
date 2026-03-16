"""Evaluation runner configuration.

README-style quick start:
- Entry point: `python3 -m eval.eval_runner --golden-set src/eval/golden_set.jsonl`
- Default outputs dir: `src/eval/outputs/`
- Main runner module: `src/eval/eval_runner.py`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EvalOutputPaths:
    retrieval_eval_json: Path
    rerank_eval_json: Path
    agent_eval_json: Path
    performance_eval_json: Path
    final_eval_report_md: Path
    rerank_gate_state_json: Path


@dataclass(frozen=True)
class EvalConfig:
    golden_set_path: Path
    outputs_dir: Path
    human_annotations_path: Path | None = None
    llm_judge_path: Path | None = None
    retrieval_top_k: tuple[int, int] = (10, 20)
    rerank_eval_k: int = 5
    rerank_pool_k: int = 20
    final_match_top_k: int = 10
    enable_query_understanding: bool = True
    enable_rerank_eval: bool = True
    rerank_auto_bypass_on_negative_delta: bool = True
    enable_agent_eval: bool = True
    enable_performance_eval: bool = True
    enable_human_agreement: bool = True
    enable_llm_judge_agreement: bool = True
    est_price_per_1k_input_usd: float = 0.0005
    est_price_per_1k_output_usd: float = 0.0015
    run_label: str = "default"
    output_paths: EvalOutputPaths = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "output_paths",
            EvalOutputPaths(
                retrieval_eval_json=self.outputs_dir / "retrieval_eval.json",
                rerank_eval_json=self.outputs_dir / "rerank_eval.json",
                agent_eval_json=self.outputs_dir / "agent_eval.json",
                performance_eval_json=self.outputs_dir / "performance_eval.json",
                final_eval_report_md=self.outputs_dir / "final_eval_report.md",
                rerank_gate_state_json=self.outputs_dir / "rerank_gate_state.json",
            ),
        )


def build_default_config(
    *,
    root_dir: Path,
    golden_set_path: Path | None = None,
    outputs_dir: Path | None = None,
    human_annotations_path: Path | None = None,
    llm_judge_path: Path | None = None,
    run_label: str = "default",
    eval_mode: str = "full",
) -> EvalConfig:
    """Build EvalConfig with sensible defaults and optional stage mode.

    eval_mode:
      - "full"   : all stages enabled (existing default behaviour)
      - "hybrid" : focus on retrieval/query-understanding only
      - "rerank" : retrieval + rerank metrics, agent eval disabled
      - "agent"  : agent evaluation + performance focus
    """
    resolved_golden = golden_set_path or (root_dir / "src" / "eval" / "golden_set.jsonl")
    resolved_outputs = outputs_dir or (root_dir / "src" / "eval" / "outputs")

    # Base defaults (equivalent to previous behaviour)
    base_kwargs: dict[str, object] = {
        "golden_set_path": resolved_golden,
        "outputs_dir": resolved_outputs,
        "human_annotations_path": human_annotations_path or (root_dir / "src" / "eval" / "human_annotations.jsonl"),
        "llm_judge_path": llm_judge_path or (root_dir / "src" / "eval" / "llm_judge_annotations.jsonl"),
        "run_label": run_label,
    }

    mode = (eval_mode or "full").strip().lower()

    if mode == "hybrid":
        # Retrieval + query understanding only
        return EvalConfig(
            **base_kwargs,  # type: ignore[arg-type]
            enable_query_understanding=True,
            enable_rerank_eval=False,
            rerank_auto_bypass_on_negative_delta=False,
            enable_agent_eval=False,
            enable_performance_eval=True,
            enable_human_agreement=False,
            enable_llm_judge_agreement=False,
        )
    if mode == "rerank":
        # Retrieval + rerank deltas, no agent eval
        return EvalConfig(
            **base_kwargs,  # type: ignore[arg-type]
            enable_query_understanding=True,
            enable_rerank_eval=True,
            rerank_auto_bypass_on_negative_delta=True,
            enable_agent_eval=False,
            enable_performance_eval=True,
            enable_human_agreement=False,
            enable_llm_judge_agreement=False,
        )
    if mode == "agent":
        # Agent evaluation quality + latency, no rerank-specific metrics
        return EvalConfig(
            **base_kwargs,  # type: ignore[arg-type]
            enable_query_understanding=True,
            enable_rerank_eval=False,
            rerank_auto_bypass_on_negative_delta=False,
            enable_agent_eval=True,
            enable_performance_eval=True,
            enable_human_agreement=True,
            enable_llm_judge_agreement=True,
        )

    # Fallback: full pipeline (backwards compatible)
    return EvalConfig(**base_kwargs)  # type: ignore[arg-type]
