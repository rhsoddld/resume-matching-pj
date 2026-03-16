from __future__ import annotations

import importlib
import os
from typing import Any

from backend.core.settings import settings


def should_try_agents_sdk() -> bool:
    if os.getenv("RESUME_MATCHING_EVAL_MODE"):
        return False
    return settings.openai_agents_sdk_enabled


def load_agents_sdk_runtime() -> tuple[Any, Any] | None:
    try:
        mod = importlib.import_module("agents")
    except Exception:
        return None

    agent_cls = getattr(mod, "Agent", None)
    runner_cls = getattr(mod, "Runner", None)
    if agent_cls is None or runner_cls is None:
        return None
    return agent_cls, runner_cls
