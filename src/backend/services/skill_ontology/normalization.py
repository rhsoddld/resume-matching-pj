from __future__ import annotations

import re
from typing import Any, Iterable

from .constants import LEGACY_LEXICAL_NORMALIZATION


def clean_token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip().lower()
    if not token:
        return None
    token = re.sub(r"\s+", " ", token)
    token = token.replace("&", " and ")
    token = re.sub(r"\s+", " ", token).strip(" ,;:/|")
    if not token:
        return None
    return LEGACY_LEXICAL_NORMALIZATION.get(token, token)


def dedupe_preserve(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
