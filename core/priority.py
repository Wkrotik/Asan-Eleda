from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


PriorityLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class PriorityResult:
    level: PriorityLevel
    confidence: float
    rationale: str


class RulesPrioritizerV1:
    def __init__(self, rules_raw: dict[str, Any]):
        self._raw = rules_raw

    def suggest(self, *, tags: list[str], text: str) -> PriorityResult:
        # Very small MVP rules: keyword matching against tags and text.
        rules = list((self._raw.get("rules") or []))
        default_raw = str(self._raw.get("default_level", "low"))
        default: PriorityLevel = default_raw if default_raw in ("low", "medium", "high") else "low"

        haystack = (" ".join(tags) + " " + text).lower()
        for r in rules:
            level_raw = str(r.get("level", "low"))
            level: PriorityLevel = level_raw if level_raw in ("low", "medium", "high") else "low"
            for kw in (r.get("keywords") or []):
                if str(kw).lower() in haystack:
                    return PriorityResult(level=level, confidence=0.70, rationale=f"Matched keyword: {kw}")

        return PriorityResult(level=default, confidence=0.55, rationale="Default priority (no rule matched).")
