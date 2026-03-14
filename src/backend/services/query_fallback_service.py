from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from typing import Any

from backend.core.providers import get_openai_client
from backend.core.settings import settings


logger = logging.getLogger(__name__)

_ALLOWED_STRENGTHS = {"must have", "main focus", "nice to have", "familiarity", "unknown"}


@dataclass
class QueryFallbackDraft:
    job_category: str | None = None
    roles: list[str] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)
    related_skills: list[str] = field(default_factory=list)
    skill_signals: list[dict[str, str]] = field(default_factory=list)
    capability_signals: list[dict[str, str]] = field(default_factory=list)
    seniority_hint: str | None = None
    rationale: str = ""


class QueryFallbackService:
    def extract(self, *, job_description: str) -> QueryFallbackDraft | None:
        system_prompt = (
            "You extract a structured hiring query from a job description. "
            "Return compact JSON only. "
            "Use lowercase skill/capability tokens. "
            "Allowed strength values: must have, main focus, nice to have, familiarity, unknown."
        )
        user_payload = {
            "task": "Extract role/skill/capability signals for retrieval.",
            "schema": {
                "job_category": "string|null",
                "roles": ["string"],
                "required_skills": ["string"],
                "related_skills": ["string"],
                "skill_signals": [{"name": "string", "strength": "string"}],
                "capability_signals": [{"name": "string", "strength": "string"}],
                "seniority_hint": "string|null",
                "rationale": "string",
            },
            "job_description": job_description,
        }
        try:
            client = get_openai_client()
            completion = client.chat.completions.create(
                model=settings.query_fallback_model,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
            )
            raw_content = completion.choices[0].message.content if completion.choices else None
            data = self._safe_json_load(raw_content)
            return QueryFallbackDraft(
                job_category=self._as_optional_str(data.get("job_category")),
                roles=self._as_str_list(data.get("roles")),
                required_skills=self._as_str_list(data.get("required_skills")),
                related_skills=self._as_str_list(data.get("related_skills")),
                skill_signals=self._as_signal_list(data.get("skill_signals")),
                capability_signals=self._as_signal_list(data.get("capability_signals")),
                seniority_hint=self._as_optional_str(data.get("seniority_hint")),
                rationale=self._as_optional_str(data.get("rationale")) or "",
            )
        except Exception:
            logger.exception("query_fallback_llm_failed")
            return None

    @staticmethod
    def to_deterministic_text(draft: QueryFallbackDraft) -> str:
        lines: list[str] = []
        if draft.job_category:
            lines.append(f"role: {draft.job_category}")
        if draft.roles:
            lines.append(f"roles: {', '.join(draft.roles)}")

        must_skills = [s["name"] for s in draft.skill_signals if s.get("strength") == "must have"]
        main_skills = [s["name"] for s in draft.skill_signals if s.get("strength") == "main focus"]
        nice_skills = [s["name"] for s in draft.skill_signals if s.get("strength") == "nice to have"]
        fam_skills = [s["name"] for s in draft.skill_signals if s.get("strength") == "familiarity"]
        unknown_skills = [
            s["name"] for s in draft.skill_signals if s.get("strength") in {"unknown", ""} and s.get("name")
        ]

        if must_skills:
            lines.append(f"must have: {', '.join(must_skills)}")
        if main_skills:
            lines.append(f"main focus: {', '.join(main_skills)}")
        if nice_skills:
            lines.append(f"nice to have: {', '.join(nice_skills)}")
        if fam_skills:
            lines.append(f"familiarity: {', '.join(fam_skills)}")
        if unknown_skills:
            lines.append(f"skills: {', '.join(unknown_skills)}")

        cap_parts = [f"{item['strength']}: {item['name']}" for item in draft.capability_signals if item.get("name")]
        if cap_parts:
            lines.append("capabilities: " + ", ".join(cap_parts))
        if draft.related_skills:
            lines.append("related skills: " + ", ".join(draft.related_skills))
        if draft.seniority_hint:
            lines.append("seniority: " + draft.seniority_hint)
        return ". ".join(part.strip() for part in lines if part.strip())

    @staticmethod
    def _safe_json_load(raw_content: Any) -> dict[str, Any]:
        if isinstance(raw_content, str):
            content = raw_content.strip()
            if not content:
                return {}
            try:
                payload = json.loads(content)
                return payload if isinstance(payload, dict) else {}
            except Exception:
                logger.warning("query_fallback_json_parse_failed")
                return {}
        if isinstance(raw_content, dict):
            return raw_content
        return {}

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        token = value.strip().lower()
        return token or None

    @staticmethod
    def _as_str_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                continue
            token = item.strip().lower()
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
        return out

    @staticmethod
    def _as_signal_list(value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            strength = item.get("strength")
            if not isinstance(name, str):
                continue
            token = name.strip().lower()
            if not token or token in seen:
                continue
            seen.add(token)
            normalized_strength = str(strength).strip().lower() if isinstance(strength, str) else "unknown"
            if normalized_strength not in _ALLOWED_STRENGTHS:
                normalized_strength = "unknown"
            out.append({"name": token, "strength": normalized_strength})
        return out


query_fallback_service = QueryFallbackService()
