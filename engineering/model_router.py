"""Model-selection policy. It does not call providers; it only returns a choice."""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class ModelChoice:
    provider: str
    model: str
    tier: str
    reason: str


def choose(task: str, configured_model: str = "gemini-flash-latest", configured_provider: str = "gemini", risk: str = "standard") -> ModelChoice:
    text = (task or "").lower()
    reasoning_terms = ("architecture", "migration", "security", "root cause", "complex", "redesign", "self-development")
    fast_terms = ("classify", "summarize", "extract", "list", "inventory")
    if any(term in text for term in reasoning_terms) or risk == "high":
        tier = "reasoning"
        reason = "high-complexity or high-risk engineering task"
    elif any(term in text for term in fast_terms):
        tier = "fast"
        reason = "lightweight information task"
    else:
        tier = "standard"
        reason = "routine engineering task"
    return ModelChoice(configured_provider, configured_model, tier, reason)
