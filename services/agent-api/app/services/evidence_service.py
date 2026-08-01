"""Evidence sufficiency scoring and persistence."""

from __future__ import annotations

import uuid
from typing import Any

from app.db.models import EvidenceSufficiencyEvent, Memory
from app.services.persistence_helpers import (
    create_row,
    default_ids,
    get_session,
    list_rows,
)


def score_growth_evidence(
    companion_id: uuid.UUID,
    evidence_memory_ids: list[uuid.UUID] | None,
    *,
    correction_strength: float = 0.0,
    recurrence: float = 0.0,
    additional_evidence_count: int = 0,
    additional_confidences: list[float] | None = None,
) -> dict[str, Any]:
    """Compute the evidence score independently from trigger scoring."""
    memory_ids = list(dict.fromkeys(evidence_memory_ids or []))
    with get_session() as session:
        memories = (
            session.query(Memory)
            .filter(
                Memory.id.in_(memory_ids),
                Memory.companion_id == companion_id,
                Memory.owner_companion_id == companion_id,
                Memory.deleted_at.is_(None),
            )
            .all()
            if memory_ids
            else []
        )

    additional_confidences = additional_confidences or []
    evidence_count = len(memories) + max(0, int(additional_evidence_count))
    memory_count_score = min(1.0, evidence_count / 3.0)
    memory_correction = max(
        (float(memory.correction_value or 0.0) for memory in memories),
        default=0.0,
    )
    correction_value = _clamp(max(correction_strength, memory_correction))
    memory_recurrence = max(
        (
            min(1.0, float(memory.repeated_topic_count or 0) / 3.0)
            for memory in memories
        ),
        default=0.0,
    )
    recurrence_value = _clamp(max(recurrence, memory_recurrence))
    confidence_values = [
        float(memory.confidence or 0.0) for memory in memories
    ] + [_clamp(value) for value in additional_confidences]
    confidence_avg = (
        sum(confidence_values) / len(confidence_values)
        if confidence_values
        else 0.0
    )
    evidence_score = _clamp(
        0.35 * memory_count_score
        + 0.25 * correction_value
        + 0.20 * recurrence_value
        + 0.20 * confidence_avg
    )
    if evidence_score >= 0.80:
        tier = "strong"
        status = "sufficient"
    elif evidence_score >= 0.55:
        tier = "review"
        status = "sufficient"
    else:
        tier = "insufficient"
        status = "needs_more_evidence"
    return {
        "evidence_score": round(evidence_score, 6),
        "tier": tier,
        "status": status,
        "is_sufficient": evidence_score >= 0.55,
        "memory_ids": [str(memory.id) for memory in memories],
        "memory_count": len(memories),
        "additional_evidence_count": max(0, int(additional_evidence_count)),
        "factors": {
            "memory_count_score": round(memory_count_score, 6),
            "correction_strength": round(correction_value, 6),
            "recurrence": round(recurrence_value, 6),
            "confidence_avg": round(confidence_avg, 6),
        },
        "weights": {
            "memory_count_score": 0.35,
            "correction_strength": 0.25,
            "recurrence": 0.20,
            "confidence_avg": 0.20,
        },
        "thresholds": {"strong": 0.80, "review": 0.55},
        "algorithm_version": "core-growth-evidence-v1",
    }


def score_growth_confidence(
    *,
    evidence_strength: float,
    user_confirmation_rate: float,
    recurrence: float,
    consistency_with_profile: float,
) -> dict[str, Any]:
    confidence = _clamp(
        0.35 * _clamp(evidence_strength)
        + 0.25 * _clamp(user_confirmation_rate)
        + 0.20 * _clamp(recurrence)
        + 0.20 * _clamp(consistency_with_profile)
    )
    return {
        "growth_confidence": round(confidence, 6),
        "factors": {
            "evidence_strength": round(_clamp(evidence_strength), 6),
            "user_confirmation_rate": round(
                _clamp(user_confirmation_rate), 6
            ),
            "recurrence": round(_clamp(recurrence), 6),
            "consistency_with_profile": round(
                _clamp(consistency_with_profile), 6
            ),
        },
        "weights": {
            "evidence_strength": 0.35,
            "user_confirmation_rate": 0.25,
            "recurrence": 0.20,
            "consistency_with_profile": 0.20,
        },
        "algorithm_version": "core-growth-confidence-v1",
    }


def create_evidence_event(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        data.setdefault("status", "needs_more_evidence")
        return create_row(session, EvidenceSufficiencyEvent, data)


def list_evidence_events(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, EvidenceSufficiencyEvent, filters, page, page_size)


def _clamp(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))
