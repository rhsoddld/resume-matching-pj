from __future__ import annotations

from functools import lru_cache
import logging
import os
from pathlib import Path

from openai import OpenAI

from backend.core.settings import settings
from backend.services.skill_ontology import RuntimeSkillOntology


logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config"


def _maybe_wrap_openai_for_langsmith(client: OpenAI) -> OpenAI:
    """Wrap OpenAI client with LangSmith tracing when enabled/configured."""
    if not settings.langsmith_tracing:
        return client
    if not settings.langsmith_api_key:
        return client

    # Keep settings as source of truth even when process env is not exported.
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    if settings.langsmith_endpoint:
        os.environ.setdefault("LANGSMITH_ENDPOINT", settings.langsmith_endpoint)
    if settings.langsmith_project:
        os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)

    try:
        from langsmith.wrappers import wrap_openai
    except Exception:
        logger.exception("LangSmith wrapper import failed; using plain OpenAI client.")
        return client

    try:
        return wrap_openai(client)
    except Exception:
        logger.exception("LangSmith OpenAI wrapper setup failed; using plain OpenAI client.")
        return client


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    return _maybe_wrap_openai_for_langsmith(OpenAI(api_key=settings.openai_api_key))


@lru_cache(maxsize=1)
def get_skill_ontology() -> RuntimeSkillOntology | None:
    try:
        return RuntimeSkillOntology.load_from_config(CONFIG_DIR)
    except Exception:
        logger.exception("Skill ontology load failed; fallback JD skill extraction will be used.")
        return None
