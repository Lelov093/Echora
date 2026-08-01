"""Personalized half-life memory decay."""

import math
from datetime import datetime, timezone

from app.core.algorithm_contract import MEMORY_DECAY_CONTRACT, clamp01, contract_trace


MEMORY_LIFECYCLE_VERSION = "core-memory-lifecycle-v1"
TYPE_BASE_HALF_LIFE_DAYS = {
    "correction": 365.0,
    "goal": 240.0,
    "preference": 180.0,
    "relationship": 210.0,
    "emotional": 90.0,
    "project": 120.0,
    "creative": 90.0,
    "episodic": 45.0,
    "fact": 90.0,
    "self": 180.0,
    "system": 30.0,
}


def calculate_personalized_half_life(
    memory_type: str,
    *,
    importance: float = 0.5,
    user_confirmed: bool = False,
    reactivation_count: int = 0,
    goal_relevance: float = 0.0,
    relationship_impact: float = 0.0,
    base_half_life_days: float | None = None,
) -> dict:
    base = max(1.0, float(base_half_life_days or TYPE_BASE_HALF_LIFE_DAYS.get(memory_type, 75.0)))
    factors = {
        "importance": 1.5 * clamp01(importance),
        "user_confirmed": 1.0 if user_confirmed else 0.0,
        "reactivation": 0.12 * min(max(int(reactivation_count), 0), 10),
        "goal_relevance": 0.8 * clamp01(goal_relevance),
        "relationship_impact": 0.8 * clamp01(relationship_impact),
    }
    multiplier = 1.0 + sum(factors.values())
    half_life = min(1095.0, max(1.0, base * multiplier))
    return {
        "base_half_life_days": round(base, 4),
        "half_life_days": round(half_life, 4),
        "multiplier": round(multiplier, 4),
        "factors": {key: round(value, 4) for key, value in factors.items()},
        "algorithm_version": MEMORY_LIFECYCLE_VERSION,
    }


def compute_memory_strength(
    initial_strength: float,
    half_life_days: float,
    last_activated_at: datetime | None,
    *,
    as_of: datetime | None = None,
) -> dict:
    """Compute S(t) = S0 * 2^(-delta_days / half_life_days)."""
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if last_activated_at is None:
        days = 0.0
    else:
        anchor = last_activated_at
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        days = max(0.0, (now - anchor).total_seconds() / 86400.0)

    normalized_half_life = max(0.001, float(half_life_days))
    strength = clamp01(initial_strength) * math.pow(2.0, -days / normalized_half_life)
    strength = clamp01(strength)
    return {
        "memory_strength": round(strength, 6),
        "days_since_activation": round(days, 6),
        "half_life_days": round(normalized_half_life, 4),
        "decay_applied": days > 0,
        "computed_at": now.isoformat(),
        "formula": "S0 * 2^(-delta_days / half_life_days)",
        "algorithm": contract_trace(MEMORY_DECAY_CONTRACT),
        "algorithm_version": MEMORY_LIFECYCLE_VERSION,
    }


def determine_state_from_strength(
    strength: float,
    current_state: str,
    memory_type: str | None = None,
) -> str:
    if current_state in {"deleted", "suppressed"}:
        return current_state

    thresholds = MEMORY_DECAY_CONTRACT["thresholds"]
    normalized = clamp01(strength)
    if normalized >= thresholds["active"]:
        return "active"
    if normalized >= thresholds["dormant"]:
        return "dormant"
    # Decay never deletes memories, including correction and long-term goals.
    return "archived"


def get_type_decay_rate(memory_type: str) -> float:
    """Compatibility helper for callers that still display the historical rate."""
    rates = {
        "correction": 0.005,
        "goal": 0.01,
        "preference": 0.02,
        "relationship": 0.015,
        "emotional": 0.025,
        "project": 0.04,
        "creative": 0.04,
        "episodic": 0.06,
        "fact": 0.05,
        "self": 0.02,
        "system": 0.08,
    }
    return rates.get(memory_type, 0.05)
