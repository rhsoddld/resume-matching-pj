from __future__ import annotations

from typing import TypeVar

SignalT = TypeVar("SignalT")

_STRENGTH_PRIORITY = {
    "must have": 4,
    "main focus": 3,
    "nice to have": 2,
    "familiarity": 1,
    "unknown": 0,
}


def dedupe_signals(signals: list[SignalT]) -> list[SignalT]:
    by_name: dict[str, SignalT] = {}
    for signal in signals:
        name = str(getattr(signal, "name", "")).strip().lower()
        if not name:
            continue
        existing = by_name.get(name)
        if existing is None:
            by_name[name] = signal
            continue
        signal_strength = str(getattr(signal, "strength", "unknown"))
        existing_strength = str(getattr(existing, "strength", "unknown"))
        if _STRENGTH_PRIORITY.get(signal_strength, 0) > _STRENGTH_PRIORITY.get(existing_strength, 0):
            by_name[name] = signal
    return list(by_name.values())


def compute_signal_quality(skill_signals: list[object], capability_signals: list[object]) -> dict[str, float | int]:
    all_signals = [*skill_signals, *capability_signals]
    total = len(all_signals)
    unknown = sum(1 for signal in all_signals if str(getattr(signal, "strength", "")) == "unknown")
    must_have = sum(1 for signal in all_signals if str(getattr(signal, "strength", "")) == "must have")
    familiarity = sum(1 for signal in all_signals if str(getattr(signal, "strength", "")) == "familiarity")
    unknown_ratio = round((unknown / total), 4) if total > 0 else 0.0
    return {
        "total_signals": total,
        "unknown_signals": unknown,
        "must_have_signals": must_have,
        "familiarity_signals": familiarity,
        "unknown_ratio": unknown_ratio,
    }
