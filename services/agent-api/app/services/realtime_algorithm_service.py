"""Deterministic realtime state and interruption decisions."""

from __future__ import annotations

import re
from typing import Any

ALGORITHM_VERSION = "core-r13-v1"
DEFAULT_EWMA_ALPHA = 0.35
DEFAULT_INTERRUPTION_THRESHOLD = 0.55
SIGNAL_TYPES = {"text", "transcript_summary", "event", "channel", "permission"}
LATENT_FIELDS = (
    "urgency",
    "helpfulness",
    "interruption_risk",
    "user_focus",
    "sensitivity_risk",
)
_RAW_FIELD_MARKERS = (
    "raw",
    "audio",
    "video",
    "screen",
    "image_bytes",
    "api_key",
    "token",
    "secret",
)


def normalize_observed_signal(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return the summary-only signal contract accepted by the realtime baseline."""
    payload = payload or {}
    signal_type = _signal_type(payload)
    blocked_fields = sorted(key for key in payload if _is_raw_field(key))
    safe_summary = _safe_summary(payload)
    provided_feature_fields = [
        field
        for field in LATENT_FIELDS
        if (
            isinstance(payload.get("features"), dict)
            and field in payload["features"]
        )
        or field in payload
    ]
    features = {
        field: _clamp(_feature_value(payload, field))
        for field in LATENT_FIELDS
    }
    return {
        "algorithm_key": "realtime_observed_signal",
        "algorithm_version": ALGORITHM_VERSION,
        "signal_type": signal_type,
        "source": str(payload.get("source") or "realtime_graph"),
        "safe_summary": safe_summary,
        "features": features,
        "provided_feature_fields": provided_feature_fields,
        "raw_payload_included": False,
        "blocked_fields": blocked_fields,
        "real_media_enabled": False,
        "supported_signal_types": sorted(SIGNAL_TYPES),
    }


def infer_signal_features(
    signal: dict[str, Any],
    *,
    focus_active: bool = False,
    boundary_snapshot: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Fill absent feature values from safe, deterministic text/event signals."""
    boundary_snapshot = boundary_snapshot or {}
    provided = signal.get("features") or {}
    summary = str(signal.get("safe_summary") or "").lower()
    urgent = any(term in summary for term in ("urgent", "emergency", "help now", "immediate", "stop"))
    sensitive = any(term in summary for term in ("private", "secret", "sensitive", "password", "token"))
    defaults = {
        "urgency": 0.85 if urgent else 0.15,
        "helpfulness": 0.6 if summary else 0.1,
        "interruption_risk": 0.25,
        "user_focus": 1.0 if focus_active else 0.15,
        "sensitivity_risk": 0.85 if sensitive else _clamp(boundary_snapshot.get("sensitivity_risk", 0.1)),
    }
    return {
        field: _clamp(provided.get(field) if _feature_was_provided(signal, field) else defaults[field])
        for field in LATENT_FIELDS
    }


def update_realtime_latent_state(
    previous: dict[str, Any] | None,
    observed_features: dict[str, Any],
    *,
    alpha: float = DEFAULT_EWMA_ALPHA,
) -> dict[str, Any]:
    """Update a bounded EWMA state without external models or media signals."""
    previous = previous or {}
    alpha = _clamp(alpha)
    previous_count = max(0, int(previous.get("observation_count") or 0))
    values: dict[str, float] = {}
    for field in LATENT_FIELDS:
        current = _clamp(observed_features.get(field))
        if previous_count == 0:
            values[field] = current
        else:
            prior = _clamp(previous.get(field))
            values[field] = (alpha * current) + ((1.0 - alpha) * prior)
    return {
        "algorithm_key": "realtime_latent_state",
        "algorithm_version": ALGORITHM_VERSION,
        "estimator": "ewma",
        "alpha": round(alpha, 4),
        "observation_count": previous_count + 1,
        **{field: round(value, 4) for field, value in values.items()},
        "real_media_features_used": False,
    }


def decide_realtime_interruption(
    latent_state: dict[str, Any],
    *,
    permission_allowed: bool,
    boundary_allowed: bool,
    focus_active: bool = False,
    hard_stop_active: bool = False,
    revoked: bool = False,
    threshold: float = DEFAULT_INTERRUPTION_THRESHOLD,
) -> dict[str, Any]:
    """Apply highest-priority safety gates before the documented score."""
    score = (
        _clamp(latent_state.get("urgency"))
        + _clamp(latent_state.get("helpfulness"))
        - _clamp(latent_state.get("interruption_risk"))
        - _clamp(latent_state.get("user_focus"))
        - _clamp(latent_state.get("sensitivity_risk"))
    )
    threshold = float(threshold)
    reason = "threshold_not_met"
    decision = "silence"
    allowed = False
    if hard_stop_active:
        reason = "hard_stop"
        decision = "blocked"
    elif revoked:
        reason = "revoked"
        decision = "blocked"
    elif not permission_allowed:
        reason = "permission_denied"
        decision = "blocked"
    elif not boundary_allowed:
        reason = "boundary_denied"
        decision = "blocked"
    elif focus_active:
        reason = "focus_active"
    elif score >= threshold:
        reason = "threshold_met"
        decision = "proactive_insert"
        allowed = True
    return {
        "algorithm_key": "realtime_interruption",
        "algorithm_version": ALGORITHM_VERSION,
        "formula": "urgency + helpfulness - interruption_risk - user_focus - sensitivity_risk",
        "score": round(score, 4),
        "threshold": round(threshold, 4),
        "decision": decision,
        "reason": reason,
        "proactive_insert_allowed": allowed,
        "gates": {
            "hard_stop_active": hard_stop_active,
            "revoked": revoked,
            "permission_allowed": permission_allowed,
            "boundary_allowed": boundary_allowed,
            "focus_active": focus_active,
        },
        "fallback": "meaningful_silence" if not allowed else None,
        "real_media_enabled": False,
    }


def _signal_type(payload: dict[str, Any]) -> str:
    requested = str(payload.get("signal_type") or "").strip().lower()
    if requested in SIGNAL_TYPES:
        return requested
    event_type = str(payload.get("event_type") or "").lower()
    if "transcript" in event_type:
        return "transcript_summary"
    if "permission" in event_type:
        return "permission"
    if event_type:
        return "event"
    return "text" if any(key in payload for key in ("text", "summary", "safe_summary")) else "channel"


def _safe_summary(payload: dict[str, Any]) -> str:
    nested = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    candidates = (
        payload.get("safe_summary"),
        payload.get("summary"),
        nested.get("safe_summary"),
        nested.get("summary"),
        payload.get("event_type"),
    )
    value = next((str(item) for item in candidates if item not in (None, "")), None)
    if value is None:
        text_value = payload.get("text") or nested.get("text") or payload.get("preview")
        value = f"Text signal observed ({len(str(text_value))} chars)." if text_value else "Realtime event observed."
    return re.sub(r"\s+", " ", value).strip()[:500]


def _feature_value(payload: dict[str, Any], field: str) -> Any:
    features = payload.get("features")
    if isinstance(features, dict) and field in features:
        return features[field]
    return payload.get(field)


def _feature_was_provided(signal: dict[str, Any], field: str) -> bool:
    return field in (signal.get("provided_feature_fields") or [])


def _is_raw_field(key: str) -> bool:
    normalized = str(key).lower()
    return any(marker in normalized for marker in _RAW_FIELD_MARKERS)


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(float(value or 0.0), 1.0))
    except (TypeError, ValueError):
        return 0.0
