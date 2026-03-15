from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.agents.runtime.sdk_runner import run_agents_sdk
from backend.core.settings import settings


def test_run_agents_sdk_bridges_settings_api_key_to_env(monkeypatch):
    observed: list[str | None] = []

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeRunResult:
        final_output = None

    class FakeRunner:
        @staticmethod
        def run_sync(*args, **kwargs):
            observed.append(os.environ.get("OPENAI_API_KEY"))
            raise RuntimeError("stop after env observation")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "test-settings-key")

    out = run_agents_sdk(
        agent_cls=FakeAgent,
        runner_cls=FakeRunner,
        model="gpt-4.1-mini",
        payload={"job": "x"},
    )

    assert out is None
    assert observed and observed[0] == "test-settings-key"
    assert os.environ.get("OPENAI_API_KEY") is None

