from __future__ import annotations

from dataclasses import dataclass

from backend.core.settings import settings


@dataclass(frozen=True)
class ModelSelection:
    model: str
    version: str
    route: str


def resolve_rerank_model(*, high_quality: bool) -> ModelSelection:
    if high_quality:
        return ModelSelection(
            model=(settings.rerank_model_high_quality or settings.rerank_model).strip(),
            version=(settings.rerank_model_high_quality_version or "unknown").strip(),
            route="high_quality",
        )
    return ModelSelection(
        model=(settings.rerank_model_default or settings.rerank_model).strip(),
        version=(settings.rerank_model_default_version or "unknown").strip(),
        route="default",
    )


def resolve_eval_judge_model() -> ModelSelection:
    return ModelSelection(
        model=(settings.eval_judge_model or settings.openai_model).strip(),
        version=(settings.eval_judge_model_version or "unknown").strip(),
        route="judge",
    )
