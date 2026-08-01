"""Bounded Bayesian belief updates for reviewed Relationship evidence."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


ALGORITHM_VERSION = "relationship-belief-beta.v1"
DIMENSIONS = (
    "familiarity",
    "understanding",
    "collaboration",
    "trust",
    "emotional_closeness",
    "boundary_awareness",
    "continuity",
)

_PRIORS = {
    "familiarity": (1.0, 5.0, 120.0),
    "understanding": (1.0, 3.0, 90.0),
    "collaboration": (1.0, 3.0, 90.0),
    "trust": (2.0, 2.0, 180.0),
    "emotional_closeness": (1.0, 7.0, 180.0),
    "boundary_awareness": (4.0, 1.0, 240.0),
    "continuity": (1.0, 4.0, 120.0),
}


class RelationshipBeliefError(ValueError):
    pass


def initial_beliefs(now: datetime | None = None) -> dict[str, dict[str, Any]]:
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    return {
        dimension: {
            "alpha": alpha,
            "beta": beta,
            "half_life_days": half_life,
            "last_evidence_at": timestamp,
        }
        for dimension, (alpha, beta, half_life) in _PRIORS.items()
    }


def summarize_beliefs(beliefs: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {dimension: belief_stats(beliefs[dimension]) for dimension in DIMENSIONS}


def belief_stats(belief: dict[str, Any]) -> dict[str, float]:
    alpha = max(float(belief["alpha"]), 1e-6)
    beta = max(float(belief["beta"]), 1e-6)
    total = alpha + beta
    mean = alpha / total
    variance = alpha * beta / (total * total * (total + 1.0))
    radius = 1.96 * math.sqrt(variance)
    return {
        "mean": round(mean, 8),
        "variance": round(variance, 10),
        "effective_evidence": round(total, 8),
        "interval_low": round(max(0.0, mean - radius), 8),
        "interval_high": round(min(1.0, mean + radius), 8),
    }


def evidence_weight(signal: dict[str, Any]) -> float:
    """Compute a capped, deterministic fractional evidence weight."""
    explicitness = _unit(signal.get("explicitness"))
    source_diversity = _unit(signal.get("source_diversity"))
    recurrence = _unit(signal.get("recurrence"))
    memory_support = _unit(signal.get("memory_support"))
    interaction_outcome = _unit(signal.get("interaction_outcome"))
    boundary_risk = _unit(signal.get("boundary_risk"))
    raw = (
        0.30 * explicitness
        + 0.20 * source_diversity
        + 0.20 * recurrence
        + 0.15 * memory_support
        + 0.15 * interaction_outcome
    )
    # A single turn remains deliberately weak even when emotionally intense.
    weight = min(1.25, max(0.10, raw * (1.0 - 0.55 * boundary_risk)))
    if int(signal.get("independent_source_count") or 1) <= 1:
        weight = min(weight, 0.55)
    return round(weight, 8)


def update_belief(
    belief: dict[str, Any],
    signal: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, float]]:
    direction = signal.get("direction")
    if direction not in {"increase", "decrease"}:
        raise RelationshipBeliefError("Relationship signal direction must be increase or decrease.")
    timestamp = now or datetime.now(timezone.utc)
    alpha, beta = _decayed_counts(belief, timestamp)
    weight = evidence_weight(signal)
    observation = 1.0 if direction == "increase" else 0.0
    alpha += weight * observation
    beta += weight * (1.0 - observation)
    updated = {
        "alpha": round(alpha, 10),
        "beta": round(beta, 10),
        "half_life_days": float(belief.get("half_life_days") or 120.0),
        "last_evidence_at": timestamp.isoformat(),
    }
    return updated, {**belief_stats(updated), "weight": weight, "observation": observation}


def validate_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not signals:
        raise RelationshipBeliefError("At least one Relationship dimension signal is required.")
    if len(signals) > 3:
        raise RelationshipBeliefError("One candidate may affect at most three Relationship dimensions.")
    seen: set[str] = set()
    normalized = []
    for signal in signals:
        dimension = str(signal.get("dimension") or "")
        direction = str(signal.get("direction") or "")
        if dimension not in DIMENSIONS or dimension in seen:
            raise RelationshipBeliefError("Relationship dimensions must be valid and unique.")
        if direction not in {"increase", "decrease"}:
            raise RelationshipBeliefError("Relationship direction must be increase or decrease.")
        seen.add(dimension)
        normalized.append({
            **signal,
            "dimension": dimension,
            "direction": direction,
            "independent_source_count": max(1, int(signal.get("independent_source_count") or 1)),
            **{
                key: _unit(signal.get(key))
                for key in (
                    "explicitness", "source_diversity", "recurrence",
                    "memory_support", "interaction_outcome", "boundary_risk",
                )
            },
        })
    return normalized


def _decayed_counts(belief: dict[str, Any], now: datetime) -> tuple[float, float]:
    alpha = max(float(belief["alpha"]), 1e-6)
    beta = max(float(belief["beta"]), 1e-6)
    mean = alpha / (alpha + beta)
    last_at = _datetime(belief.get("last_evidence_at")) or now
    days = max(0.0, (now - last_at).total_seconds() / 86400.0)
    half_life = max(1.0, float(belief.get("half_life_days") or 120.0))
    rho = 2.0 ** (-days / half_life)
    effective = max(2.0, rho * (alpha + beta))
    return mean * effective, (1.0 - mean) * effective


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _unit(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))
