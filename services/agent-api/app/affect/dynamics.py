"""Bounded, explainable Companion affect dynamics.

The runtime uses a deterministic mean-reverting core-affect state. Provider
appraisals are observations only; all state transitions are computed here.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


ALGORITHM_VERSION = "affect-mean-reversion.v1"
APPRAISAL_DIMENSIONS = (
    "pleasantness", "goal_congruence", "controllability", "novelty", "certainty",
)


def decay_state(state: dict[str, Any], at: datetime | None = None) -> dict[str, float]:
    at = _utc(at or datetime.now(timezone.utc))
    last = _utc(_as_datetime(state.get("last_transition_at")) or at)
    elapsed_hours = max(0.0, (at - last).total_seconds() / 3600.0)
    half_life = max(0.25, float(state.get("half_life_hours", 18.0)))
    retention = math.exp(-math.log(2.0) * elapsed_hours / half_life)
    return {
        "valence": _signed(float(state.get("home_valence", 0.08)) + (float(state.get("valence", 0.08)) - float(state.get("home_valence", 0.08))) * retention),
        "arousal": _signed(float(state.get("home_arousal", -0.08)) + (float(state.get("arousal", -0.08)) - float(state.get("home_arousal", -0.08))) * retention),
        "retention": round(retention, 6),
        "elapsed_hours": round(elapsed_hours, 4),
    }


def apply_appraisal(
    state: dict[str, Any], appraisal: dict[str, Any], *, at: datetime | None = None,
) -> dict[str, Any]:
    at = _utc(at or datetime.now(timezone.utc))
    decayed = decay_state(state, at)
    values = {key: _signed(appraisal.get(key, 0.0)) for key in APPRAISAL_DIMENSIONS}
    confidence = _unit(appraisal.get("confidence", 0.0))
    evidence = _unit(appraisal.get("evidence_score", 0.0))
    gain = min(0.22, 0.22 * confidence * evidence)
    # Pleasantness and goal congruence drive valence; novelty and low certainty
    # increase activation. Controllability tempers activation without changing
    # the event's semantic direction.
    valence_signal = 0.58 * values["pleasantness"] + 0.42 * values["goal_congruence"]
    arousal_signal = 0.46 * abs(values["novelty"]) + 0.34 * (1.0 - (values["certainty"] + 1.0) / 2.0) + 0.20 * max(0.0, -values["controllability"])
    arousal_direction = -1.0 if values["pleasantness"] > 0.45 and values["controllability"] > 0.35 else 1.0
    impulse = {
        "valence": round(gain * valence_signal, 6),
        "arousal": round(gain * arousal_signal * arousal_direction, 6),
    }
    after = {
        "valence": _signed(decayed["valence"] + impulse["valence"]),
        "arousal": _signed(decayed["arousal"] + impulse["arousal"]),
    }
    return {
        "before": {"valence": decayed["valence"], "arousal": decayed["arousal"]},
        "after": after,
        "impulse": impulse,
        "decay": {"retention": decayed["retention"], "elapsed_hours": decayed["elapsed_hours"]},
        "expression": expression_projection(after["valence"], after["arousal"]),
        "algorithm_version": ALGORITHM_VERSION,
        "at": at,
    }


def expression_projection(valence: float, arousal: float) -> dict[str, str]:
    if abs(valence) < 0.14 and abs(arousal) < 0.18:
        return {"label": "平稳", "tone": "steady", "focus": "balanced"}
    if valence >= 0.18 and arousal >= 0.18:
        return {"label": "明亮而投入", "tone": "bright", "focus": "engaged"}
    if valence >= 0.18:
        return {"label": "温和舒展", "tone": "warm", "focus": "reassuring"}
    if valence <= -0.18 and arousal >= 0.18:
        return {"label": "谨慎关注", "tone": "careful", "focus": "clarify"}
    if valence <= -0.18:
        return {"label": "安静审慎", "tone": "subdued", "focus": "reflective"}
    return {"label": "专注", "tone": "focused", "focus": "current_task"}


def validate_appraisal(values: dict[str, Any]) -> dict[str, float]:
    if set(values) != set(APPRAISAL_DIMENSIONS):
        raise ValueError("appraisal dimensions do not match contract")
    return {key: _signed(values[key]) for key in APPRAISAL_DIMENSIONS}


def _unit(value: Any) -> float:
    return max(0.0, min(1.0, float(value)))


def _signed(value: Any) -> float:
    return round(max(-1.0, min(1.0, float(value))), 6)


def _as_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
