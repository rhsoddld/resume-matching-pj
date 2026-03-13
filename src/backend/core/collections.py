from __future__ import annotations

from typing import Iterable, TypeVar


T = TypeVar("T")


def dedupe_preserve(values: Iterable[T]) -> list[T]:
    out: list[T] = []
    seen: set[T] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
