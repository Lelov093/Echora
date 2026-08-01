"""Versioned contracts shared by Echora's deterministic core algorithms."""

from __future__ import annotations

import math
from typing import Any


POLICY_MODE_HEURISTIC = "heuristic"


MEMORY_CANDIDATE_CONTRACT = {
    "algorithm_key": "memory_candidate_score",
    "algorithm_version": "core-r1-v1",
    "policy_mode": POLICY_MODE_HEURISTIC,
    "weights": {
        "user_explicitness": 0.20,
        "goal_relevance": 0.18,
        "correction_value": 0.18,
        "relationship_impact": 0.12,
        "emotional_intensity": 0.10,
        "novelty": 0.08,
        "recurrence": 0.08,
        "triviality": -0.10,
        "sensitivity_risk": -0.15,
    },
    "thresholds": {
        "high_priority": 0.80,
        "candidate": 0.55,
        "working_memory": 0.35,
        "correction_force": 0.80,
    },
}

GROWTH_TRIGGER_CONTRACT = {
    "algorithm_key": "growth_trigger_score",
    "algorithm_version": "core-r1-v1",
    "policy_mode": POLICY_MODE_HEURISTIC,
    "weights": {
        "correction_signal": 0.30,
        "topic_recurrence": 0.20,
        "emotional_intensity": 0.20,
        "relationship_change": 0.15,
        "understanding_gap": 0.15,
    },
    "thresholds": {
        "candidate": 0.75,
        "reflection_queue": 0.50,
        "correction_force": 0.85,
    },
}

PRESENCE_PRIORITY_CONTRACT = {
    "algorithm_key": "presence_opportunity_priority",
    "algorithm_version": "core-r1-v1",
    "policy_mode": POLICY_MODE_HEURISTIC,
    "weights": {
        "goal_relevance": 0.22,
        "continuity_importance": 0.18,
        "user_interest_match": 0.16,
        "memory_importance": 0.14,
        "growth_relevance": 0.12,
        "time_sensitivity": 0.10,
        "relationship_fit": 0.08,
        "interruption_risk": -0.20,
        "recent_dismissal_penalty": -0.15,
        "sensitivity_penalty": -0.20,
    },
    "thresholds": {
        "hub": 0.80,
        "queue": 0.55,
        "low_priority_queue": 0.35,
    },
    "dismissal_window_days": 14,
    "dismissal_suppress_count": 2,
}

MEMORY_DECAY_CONTRACT = {
    "algorithm_key": "memory_decay_state",
    "algorithm_version": "core-r1-v1",
    "policy_mode": POLICY_MODE_HEURISTIC,
    "thresholds": {
        "active": 0.70,
        "dormant": 0.35,
        "archived": 0.15,
    },
}

MEMORY_RETRIEVAL_CONTRACT = {
    "algorithm_key": "memory_retrieval_rerank",
    "algorithm_version": "core-r1-v1",
    "policy_mode": POLICY_MODE_HEURISTIC,
    "weights": {
        "semantic_similarity": 0.40,
        "memory_strength": 0.18,
        "goal_relevance": 0.15,
        "recency_score": 0.10,
        "relationship_impact": 0.08,
        "correction_priority": 0.06,
        "mode_match": 0.03,
        "outdated_penalty": -0.20,
        "sensitivity_penalty": -0.20,
    },
}

MEMORY_REINFORCEMENT_CONTRACT = {
    "algorithm_key": "memory_reinforcement",
    "algorithm_version": "core-r1-v1",
    "policy_mode": POLICY_MODE_HEURISTIC,
    "weights": {
        "successful_recall": 0.05,
        "user_confirmed": 0.08,
        "used_in_growth": 0.06,
        "used_in_presence": 0.04,
        "repeated_topic": 0.03,
    },
}


def clamp01(value: Any, default: float = 0.0) -> float:
    """Return a finite float clamped to [0, 1]."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    if not math.isfinite(number):
        number = float(default)
    return max(0.0, min(1.0, number))


def weighted_score(factors: dict[str, Any], contract: dict[str, Any]) -> float:
    """Compute a deterministic weighted score using a versioned contract."""
    return clamp01(
        sum(
            float(weight) * clamp01(factors.get(name), 0.0)
            for name, weight in contract["weights"].items()
        )
    )


def contract_trace(
    contract: dict[str, Any],
    *,
    fallback_reason: str | None = None,
    feature_sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return stable metadata required to replay a deterministic decision."""
    return {
        "algorithm_key": contract["algorithm_key"],
        "algorithm_version": contract["algorithm_version"],
        "policy_mode": contract["policy_mode"],
        "weights": dict(contract.get("weights", {})),
        "thresholds": dict(contract.get("thresholds", {})),
        "missing_feature_default": 0.0,
        "fallback_reason": fallback_reason,
        "feature_sources": feature_sources or {},
    }
