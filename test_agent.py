import json
import logging
import os
import sys

# ADD local paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.runtime.sdk_runtime import load_agents_sdk_runtime
from backend.core.settings import settings

logging.basicConfig(level=logging.DEBUG)

from agents import function_tool

@function_tool
def search_candidate_evidence(query: str) -> str:
    """Search specific evidence."""
    return "Dummy data"

try:
    runtime = load_agents_sdk_runtime()
    agent_cls, runner_cls = runtime
    agent = agent_cls(
        name="TestAgent",
        model=settings.openai_agent_model,
        instructions="Test",
        tools=[search_candidate_evidence]
    )
    res = runner_cls.run_sync(agent, "test")
    print("SUCCESS", res)
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"FAILED: {e}")
