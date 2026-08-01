"""Personalized, bounded, and auditable memory lifecycle maintenance."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Memory, MemoryUsageEvent
from app.memory.decay import (
    MEMORY_LIFECYCLE_VERSION,
    calculate_personalized_half_life,
    compute_memory_strength,
    determine_state_from_strength,
)
from app.memory.reinforcement import (
    apply_reinforcement,
    compute_beta_confidence,
    compute_negative_feedback_penalty,
)
from app.services import memory_lifecycle_service
from app.services.memory_service import get_session


def record_lifecycle_event(memory_id: str, event_type: str, data: dict | None = None) -> dict:
    payload = {"memory_id": memory_id, "event_type": event_type}
    if data:
        payload.update(data)
    if not payload.get("user_id") or not payload.get("companion_id"):
        with get_session() as session:
            memory = session.get(Memory, uuid.UUID(memory_id))
            if memory is None:
                raise ValueError("memory not found")
            payload.setdefault("user_id", str(memory.user_id))
            payload.setdefault("companion_id", str(memory.companion_id))
    return memory_lifecycle_service.create_memory_lifecycle_event(payload)


def _snapshot(memory: Memory) -> dict:
    return {
        "state": memory.state,
        "memory_strength": round(float(memory.memory_strength or 0.0), 6),
        "confidence": round(float(memory.confidence or 0.0), 6),
        "confidence_prior_alpha": round(float(memory.confidence_prior_alpha or 2.0), 6),
        "confidence_prior_beta": round(float(memory.confidence_prior_beta or 2.0), 6),
        "confidence_alpha": round(float(memory.confidence_alpha or 2.0), 6),
        "confidence_beta": round(float(memory.confidence_beta or 2.0), 6),
        "half_life_days": round(float(memory.half_life_days or 0.0), 4),
        "base_half_life_days": round(float(memory.base_half_life_days or 0.0), 4),
        "reactivation_count": int(memory.reactivation_count or 0),
        "successful_recall_count": int(memory.successful_recall_count or 0),
        "growth_use_count": int(memory.growth_use_count or 0),
        "presence_use_count": int(memory.presence_use_count or 0),
        "repeated_topic_count": int(memory.repeated_topic_count or 0),
    }


def _usage_signals(events: list[MemoryUsageEvent]) -> dict:
    recall_events = [event for event in events if event.used_in_response]
    growth_events = [event for event in events if event.used_in_growth]
    presence_events = [event for event in events if event.used_in_presence]
    repeated_events = [
        event
        for event in events
        if bool((event.usage_context or {}).get("repeated_topic"))
    ]
    latest_recall = max(
        (event.created_at for event in recall_events if event.created_at),
        default=None,
    )
    return {
        "successful_recall_count": len(recall_events),
        "growth_use_count": len(growth_events),
        "presence_use_count": len(presence_events),
        "repeated_topic_count": len(repeated_events),
        "latest_recall_at": latest_recall,
    }


def preview_memory_lifecycle(
    memory: Memory,
    usage_events: list[MemoryUsageEvent],
    *,
    as_of: datetime,
) -> dict:
    before = _snapshot(memory)
    usage = _usage_signals(usage_events)
    new_recall = max(0, usage["successful_recall_count"] - (memory.successful_recall_count or 0))
    new_growth = max(0, usage["growth_use_count"] - (memory.growth_use_count or 0))
    new_presence = max(0, usage["presence_use_count"] - (memory.presence_use_count or 0))
    new_repeated = max(0, usage["repeated_topic_count"] - (memory.repeated_topic_count or 0))
    new_positive = max(0, (memory.positive_confirmations or 0) - (memory.calibrated_positive_count or 0))
    new_helpful = max(0, (memory.helpful_count or 0) - (memory.calibrated_helpful_count or 0))
    new_irrelevant = max(0, (memory.irrelevant_count or 0) - (memory.calibrated_irrelevant_count or 0))
    new_outdated = max(0, (memory.outdated_count or 0) - (memory.calibrated_outdated_count or 0))
    new_wrong = max(0, (memory.wrong_count or 0) - (memory.calibrated_wrong_count or 0))

    projected_reactivations = (memory.reactivation_count or 0) + new_recall
    half_life = calculate_personalized_half_life(
        memory.type,
        importance=memory.importance or 0.0,
        user_confirmed=(
            memory.consent_status == "user_confirmed"
            or (memory.positive_confirmations or 0) > 0
        ),
        reactivation_count=projected_reactivations,
        goal_relevance=memory.goal_relevance or 0.0,
        relationship_impact=memory.relationship_impact or 0.0,
        base_half_life_days=memory.base_half_life_days,
    )
    anchor = (
        memory.strength_anchor_at
        or memory.last_reactivated_at
        or memory.updated_at
        or memory.created_at
        or as_of
    )
    decay = compute_memory_strength(
        memory.memory_strength or 0.0,
        half_life["half_life_days"],
        anchor,
        as_of=as_of,
    )
    reinforcement = apply_reinforcement(
        decay["memory_strength"],
        successful_recall=new_recall > 0,
        user_confirmed=(new_positive + new_helpful) > 0,
        used_in_growth=new_growth > 0,
        used_in_presence=new_presence > 0,
        repeated_topic=new_repeated > 0,
    )
    penalty = compute_negative_feedback_penalty(
        new_irrelevant=new_irrelevant,
        new_outdated=new_outdated,
        new_wrong=new_wrong,
    )
    strength = max(0.0, reinforcement["new_strength"] - penalty["strength_penalty"])
    beta = compute_beta_confidence(
        positive_confirmations=memory.positive_confirmations or 0,
        helpful_count=memory.helpful_count or 0,
        accepted_count=memory.accepted_count or 0,
        irrelevant_count=memory.irrelevant_count or 0,
        outdated_count=memory.outdated_count or 0,
        wrong_count=memory.wrong_count or 0,
        rejected_count=memory.rejected_count or 0,
        prior_alpha=memory.confidence_prior_alpha or 2.0,
        prior_beta=memory.confidence_prior_beta or 2.0,
    )

    has_positive_reactivation = (new_recall + new_positive + new_helpful) > 0
    if new_wrong > 0:
        next_state = "suppressed"
    elif memory.state == "archived" and not has_positive_reactivation:
        next_state = "archived"
    else:
        next_state = determine_state_from_strength(strength, memory.state, memory.type)
    after = {
        **before,
        "state": next_state,
        "memory_strength": round(strength, 6),
        "confidence": beta["confidence"],
        "confidence_alpha": beta["alpha"],
        "confidence_beta": beta["beta"],
        "half_life_days": half_life["half_life_days"],
        "base_half_life_days": half_life["base_half_life_days"],
        "reactivation_count": projected_reactivations,
        "successful_recall_count": usage["successful_recall_count"],
        "growth_use_count": usage["growth_use_count"],
        "presence_use_count": usage["presence_use_count"],
        "repeated_topic_count": usage["repeated_topic_count"],
    }
    changed = any(
        before[key] != after[key]
        for key in (
            "state",
            "memory_strength",
            "confidence",
            "confidence_alpha",
            "confidence_beta",
            "half_life_days",
            "base_half_life_days",
            "reactivation_count",
            "successful_recall_count",
            "growth_use_count",
            "presence_use_count",
            "repeated_topic_count",
        )
    )
    return {
        "memory_id": str(memory.id),
        "companion_id": str(memory.companion_id),
        "dry_run": True,
        "changed": changed,
        "before": before,
        "after": after,
        "signals": {
            "new_successful_recall": new_recall,
            "new_growth_use": new_growth,
            "new_presence_use": new_presence,
            "new_repeated_topic": new_repeated,
            "new_positive": new_positive,
            "new_helpful": new_helpful,
            "new_irrelevant": new_irrelevant,
            "new_outdated": new_outdated,
            "new_wrong": new_wrong,
        },
        "latest_recall_at": usage["latest_recall_at"],
        "score_json": {
            "half_life": half_life,
            "decay": decay,
            "reinforcement": reinforcement,
            "negative_feedback": penalty,
            "beta_confidence": beta,
            "algorithm_version": MEMORY_LIFECYCLE_VERSION,
        },
    }


def _event_type(preview: dict) -> str:
    before = preview["before"]
    after = preview["after"]
    if before["state"] != after["state"]:
        if after["state"] == "suppressed":
            return "suppressed"
        if after["state"] == "archived":
            return "archived"
        if after["state"] == "active":
            return "reactivated"
        return "weakened"
    if after["memory_strength"] > before["memory_strength"]:
        return "strengthened"
    if after["memory_strength"] < before["memory_strength"]:
        return "weakened"
    if after["confidence"] != before["confidence"]:
        return "confidence_updated"
    return "half_life_updated"


def _apply_preview(session, memory: Memory, preview: dict, as_of: datetime) -> None:
    after = preview["after"]
    memory.state = after["state"]
    memory.memory_strength = after["memory_strength"]
    memory.confidence = after["confidence"]
    memory.confidence_alpha = after["confidence_alpha"]
    memory.confidence_beta = after["confidence_beta"]
    memory.base_half_life_days = after["base_half_life_days"]
    memory.half_life_days = after["half_life_days"]
    memory.reactivation_count = after["reactivation_count"]
    memory.successful_recall_count = after["successful_recall_count"]
    memory.growth_use_count = after["growth_use_count"]
    memory.presence_use_count = after["presence_use_count"]
    memory.repeated_topic_count = after["repeated_topic_count"]
    memory.calibrated_positive_count = memory.positive_confirmations or 0
    memory.calibrated_helpful_count = memory.helpful_count or 0
    memory.calibrated_irrelevant_count = memory.irrelevant_count or 0
    memory.calibrated_outdated_count = memory.outdated_count or 0
    memory.calibrated_wrong_count = memory.wrong_count or 0
    memory.last_reactivated_at = preview["latest_recall_at"] or memory.last_reactivated_at
    memory.strength_anchor_at = as_of
    memory.last_maintenance_at = as_of
    memory.lifecycle_algorithm_version = MEMORY_LIFECYCLE_VERSION
    memory.lifecycle_summary = {
        "last_maintenance_at": as_of.isoformat(),
        "algorithm_version": MEMORY_LIFECYCLE_VERSION,
        "signals": preview["signals"],
    }
    memory.updated_at = as_of
    if preview["changed"]:
        memory_lifecycle_service.record_memory_change(
            session,
            memory,
            event_type=_event_type(preview),
            reason="Personalized memory lifecycle maintenance",
            before=preview["before"],
            after=preview["after"],
            score_json=preview["score_json"],
        )


def run_memory_maintenance(
    *,
    companion_id: uuid.UUID | None = None,
    dry_run: bool = True,
    limit: int = 100,
    as_of: datetime | None = None,
) -> dict:
    bounded_limit = min(max(int(limit), 1), 500)
    timestamp = as_of or datetime.now(timezone.utc)
    results = []
    failures = []

    with get_session() as session:
        stmt = select(Memory).where(
            Memory.deleted_at.is_(None),
            Memory.state != "deleted",
        )
        if companion_id:
            stmt = stmt.where(Memory.companion_id == companion_id)
        memories = session.execute(
            stmt.order_by(Memory.updated_at.asc(), Memory.id.asc()).limit(bounded_limit)
        ).scalars().all()

        for memory in memories:
            try:
                usage_events = session.execute(
                    select(MemoryUsageEvent).where(
                        MemoryUsageEvent.memory_id == memory.id,
                        MemoryUsageEvent.companion_id == memory.companion_id,
                    )
                ).scalars().all()
                preview = preview_memory_lifecycle(memory, usage_events, as_of=timestamp)
                preview["dry_run"] = dry_run
                results.append(preview)
                if not dry_run:
                    _apply_preview(session, memory, preview, timestamp)
                    session.commit()
            except Exception as exc:
                session.rollback()
                failures.append({"memory_id": str(memory.id), "error": type(exc).__name__})

    return {
        "dry_run": dry_run,
        "limit": bounded_limit,
        "processed": len(results),
        "changed": sum(1 for result in results if result["changed"]),
        "failed": len(failures),
        "failures": failures,
        "items": results,
        "algorithm_version": MEMORY_LIFECYCLE_VERSION,
    }
