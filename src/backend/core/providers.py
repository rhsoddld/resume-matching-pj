from __future__ import annotations

from functools import lru_cache
import logging
from pathlib import Path

from openai import OpenAI

from backend.core.settings import settings
from backend.services.skill_ontology import RuntimeSkillOntology


logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config"


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


@lru_cache(maxsize=1)
def get_skill_ontology() -> RuntimeSkillOntology | None:
    try:
        return RuntimeSkillOntology.load_from_config(CONFIG_DIR)
    except Exception:
        logger.exception("Skill ontology load failed; fallback JD skill extraction will be used.")
        return None
