"""Durable, boundary-first Presence proactive Presence scheduling."""

from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session

from app.agents.providers.base import LLMProviderError
from app.agents.providers.openai_compatible import OpenAICompatibleProvider
from app.core.config import settings
from app.db.models import (
    Companion,
    CompanionBoundaryProfile,
    CompanionIdentityProfile,
    CompanionPersonaProfile,
    CompanionRelationshipContract,
    Conversation,
    Message,
    PresenceOpportunity,
    PresenceSchedule,
    PresenceScheduleOccurrence,
)
from app.services import presence_service

_engine = None


class PresenceScheduleError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def get_schedule(user_id: uuid.UUID, companion_id: uuid.UUID) -> PresenceSchedule | None:
    with get_session() as session:
        return session.execute(
            select(PresenceSchedule).where(
                PresenceSchedule.user_id == user_id,
                PresenceSchedule.companion_id == companion_id,
            )
        ).scalar_one_or_none()


def upsert_schedule(user_id: uuid.UUID, companion_id: uuid.UUID, payload: dict) -> PresenceSchedule:
    with get_session() as session:
        schedule = upsert_schedule_in_session(session, user_id, companion_id, payload)
        session.commit()
        session.refresh(schedule)
        return schedule


def upsert_schedule_in_session(
    session: Session,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    payload: dict,
    *,
    now: datetime | None = None,
) -> PresenceSchedule:
    """Update a schedule inside the caller's transaction.

    The composite Presence configuration service uses this entry point so the
    schedule, runtime policy and profile projection either commit together or
    roll back together. The public schedule API keeps its existing behavior by
    wrapping this function in its own transaction above.
    """
    now = now or datetime.now(timezone.utc)
    data = dict(payload)
    companion = session.get(Companion, companion_id)
    if companion is None or companion.deleted_at is not None or companion.user_id != user_id:
        raise PresenceScheduleError("COMPANION_NOT_FOUND", "Companion not found for this owner.")
    schedule = session.execute(
        select(PresenceSchedule)
        .where(PresenceSchedule.user_id == user_id, PresenceSchedule.companion_id == companion_id)
        .with_for_update()
    ).scalar_one_or_none()
    expected = data.pop("expected_revision", None)
    if schedule is None:
        if expected is not None:
            raise PresenceScheduleError("PRESENCE_SCHEDULE_REVISION_CONFLICT", "The schedule has not been created yet.")
        schedule = PresenceSchedule(user_id=user_id, companion_id=companion_id)
        session.add(schedule)
        session.flush()
    elif expected != schedule.revision:
        raise PresenceScheduleError(
            "PRESENCE_SCHEDULE_REVISION_CONFLICT",
            "The Presence schedule changed elsewhere. Refresh before saving.",
            {"expected_revision": expected, "current_revision": schedule.revision},
        )

    _validate_timezone(data["timezone"])
    if data["destination_mode"] == "bound_conversation" and data.get("bound_conversation_id") is not None:
        _require_active_bound_conversation(
            session, data.get("bound_conversation_id"), user_id, companion_id
        )
    elif data["status"] == "active" and data["destination_mode"] == "bound_conversation":
        raise PresenceScheduleError(
            "PRESENCE_BOUND_CONVERSATION_REQUIRED",
            "Choose or create a Conversation before enabling proactive greetings.",
        )

    schedule_changed = any(getattr(schedule, key) != value for key, value in data.items())
    if not schedule_changed:
        return schedule

    previous_revision = schedule.revision
    for key, value in data.items():
        setattr(schedule, key, value)
    schedule.revision = previous_revision + (1 if expected is not None else 0)
    schedule.pause_reason = None if schedule.status == "active" else "paused_by_user"
    schedule.next_occurrence_at = None
    schedule.updated_at = now
    pending = list(session.execute(
        select(PresenceScheduleOccurrence)
        .where(
            PresenceScheduleOccurrence.schedule_id == schedule.id,
            PresenceScheduleOccurrence.status.in_(["scheduled", "retry_wait"]),
        )
        .with_for_update()
    ).scalars().all())
    for occurrence in pending:
        occurrence.status = "cancelled"
        occurrence.error_code = "schedule_reconfigured"
    if schedule.status == "active":
        _plan_next_locked(session, schedule, now=now, reset=True)
    return schedule


def trigger_now(user_id: uuid.UUID, companion_id: uuid.UUID, expected_revision: int) -> dict:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        schedule = session.execute(
            select(PresenceSchedule)
            .where(PresenceSchedule.user_id == user_id, PresenceSchedule.companion_id == companion_id)
            .with_for_update()
        ).scalar_one_or_none()
        if schedule is None:
            raise PresenceScheduleError("PRESENCE_SCHEDULE_NOT_FOUND", "Create the Presence schedule first.")
        if schedule.revision != expected_revision:
            raise PresenceScheduleError("PRESENCE_SCHEDULE_REVISION_CONFLICT", "Refresh before triggering.")
        if schedule.status != "active":
            raise PresenceScheduleError("PRESENCE_SCHEDULE_PAUSED", "Enable the schedule before triggering a greeting.")
        occurrence = _new_occurrence(session, schedule, now, {"source": "manual_trigger", "entropy": "os_csprng"})
        session.commit()
        occurrence_id = occurrence.id
    try:
        process_occurrence(occurrence_id)
    except Exception as exc:
        _retry_or_fail(occurrence_id, "PRESENCE_DELIVERY_RUNTIME_ERROR", type(exc).__name__)
    return get_occurrence(occurrence_id) or {"id": str(occurrence_id), "status": "unknown"}


def list_occurrences(user_id: uuid.UUID, companion_id: uuid.UUID, limit: int = 20) -> list[dict]:
    with get_session() as session:
        rows = session.execute(
            select(PresenceScheduleOccurrence)
            .where(
                PresenceScheduleOccurrence.user_id == user_id,
                PresenceScheduleOccurrence.companion_id == companion_id,
            )
            .order_by(PresenceScheduleOccurrence.created_at.desc())
            .limit(limit)
        ).scalars().all()
        return [_occurrence_dict(row) for row in rows]


def get_occurrence(occurrence_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(PresenceScheduleOccurrence, occurrence_id)
        return _occurrence_dict(row) if row else None


def run_scheduler_tick(*, now: datetime | None = None, limit: int = 10) -> int:
    now = now or datetime.now(timezone.utc)
    claimed: list[uuid.UUID] = []
    with get_session() as session:
        rows = session.execute(
            select(PresenceScheduleOccurrence)
            .where(
                PresenceScheduleOccurrence.status.in_(["scheduled", "retry_wait", "claimed"]),
                func.coalesce(
                    PresenceScheduleOccurrence.next_attempt_at,
                    PresenceScheduleOccurrence.scheduled_for,
                ) <= now,
                or_(
                    PresenceScheduleOccurrence.status != "claimed",
                    PresenceScheduleOccurrence.lease_expires_at.is_(None),
                    PresenceScheduleOccurrence.lease_expires_at <= now,
                ),
            )
            .order_by(
                func.coalesce(
                    PresenceScheduleOccurrence.next_attempt_at,
                    PresenceScheduleOccurrence.scheduled_for,
                ).asc()
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        ).scalars().all()
        for row in rows:
            row.status = "claimed"
            row.claimed_at = now
            row.lease_expires_at = now + timedelta(seconds=settings.PRESENCE_SCHEDULER_LEASE_SECONDS)
            row.attempt_count += 1
            claimed.append(row.id)
        session.commit()
    for occurrence_id in claimed:
        try:
            process_occurrence(occurrence_id)
        except Exception as exc:
            # Isolate every durable job: one bad occurrence must not strand the batch.
            _retry_or_fail(occurrence_id, "PRESENCE_DELIVERY_RUNTIME_ERROR", type(exc).__name__)
    return len(claimed)


def process_occurrence(occurrence_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        occurrence = session.get(PresenceScheduleOccurrence, occurrence_id)
        if occurrence is None or occurrence.status not in {"scheduled", "claimed", "retry_wait"}:
            return
        schedule = session.get(PresenceSchedule, occurrence.schedule_id)
        if schedule is None or schedule.status != "active" or schedule.revision != occurrence.schedule_revision:
            _finish_locked(session, occurrence, schedule, "cancelled", "schedule_inactive_or_changed", now)
            session.commit()
            return
        try:
            conversation = _resolve_conversation(session, schedule)
        except PresenceScheduleError as exc:
            schedule.status = "paused"
            schedule.pause_reason = exc.code
            schedule.next_occurrence_at = None
            _finish_locked(session, occurrence, schedule, "suppressed", exc.code, now)
            session.commit()
            return
        conversation_id = conversation.id if conversation else None
        user_id, companion_id = schedule.user_id, schedule.companion_id

    suppression = presence_service.evaluate_presence_suppression(
        user_id, companion_id, "check_in", min_interval_seconds=0, now=now
    )
    if suppression.get("suppress"):
        _finish_occurrence(occurrence_id, "suppressed", str(suppression.get("reason") or "boundary"), suppression)
        return

    try:
        generated = _generate_greeting(user_id, companion_id, conversation_id)
    except LLMProviderError as exc:
        _retry_or_fail(occurrence_id, exc.code, str(exc))
        return
    except Exception as exc:
        _retry_or_fail(occurrence_id, "PRESENCE_PROVIDER_FAILURE", type(exc).__name__)
        return

    final_suppression = presence_service.evaluate_presence_suppression(
        user_id, companion_id, "check_in", min_interval_seconds=0, now=datetime.now(timezone.utc)
    )
    if final_suppression.get("suppress"):
        _finish_occurrence(
            occurrence_id,
            "suppressed",
            str(final_suppression.get("reason") or "boundary_changed"),
            final_suppression,
        )
        return
    _persist_delivery(occurrence_id, generated)


def _persist_delivery(occurrence_id: uuid.UUID, generated: dict) -> None:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        occurrence = session.execute(
            select(PresenceScheduleOccurrence).where(PresenceScheduleOccurrence.id == occurrence_id).with_for_update()
        ).scalar_one_or_none()
        if occurrence is None or occurrence.status not in {"scheduled", "claimed", "retry_wait"}:
            return
        schedule = session.get(PresenceSchedule, occurrence.schedule_id)
        if schedule is None or schedule.status != "active" or schedule.revision != occurrence.schedule_revision:
            _finish_locked(session, occurrence, schedule, "cancelled", "schedule_inactive_or_changed", now)
            session.commit()
            return
        try:
            conversation = _resolve_conversation(session, schedule, create_if_needed=True)
        except PresenceScheduleError as exc:
            schedule.status = "paused"
            schedule.pause_reason = exc.code
            _finish_locked(session, occurrence, schedule, "suppressed", exc.code, now)
            session.commit()
            return
        content = str(generated.get("content") or "").strip()
        if not content:
            _finish_locked(session, occurrence, schedule, "failed", "empty_provider_response", now)
            session.commit()
            return
        message = Message(
            user_id=schedule.user_id,
            companion_id=schedule.companion_id,
            conversation_id=conversation.id,
            role="assistant",
            content=content,
            content_format="text",
            source_modality="text",
            model_provider=generated.get("provider"),
            model_name=generated.get("model"),
            metadata_={"origin": "scheduled_presence", "schedule_id": str(schedule.id), "occurrence_id": str(occurrence.id)},
        )
        session.add(message)
        session.flush()
        opportunity = PresenceOpportunity(
            user_id=schedule.user_id,
            companion_id=schedule.companion_id,
            conversation_id=conversation.id,
            type="check_in",
            title="伙伴主动问候",
            message=content,
            reason="scheduled_presence",
            evidence_message_ids=[message.id],
            priority=0.5,
            urgency=0.2,
            sensitivity=0.0,
            interruption_risk=0.2,
            recommended_surface="inline",
            status="accepted",
            user_action="scheduled_delivery",
            accepted_at=now,
            score_json={"policy_mode": "configured_schedule", "bandit_policy_mode": "shadow"},
            calibration_json={"schedule_id": str(schedule.id), "occurrence_id": str(occurrence.id)},
            metadata_={"origin": "scheduled_presence"},
        )
        session.add(opportunity)
        session.flush()
        conversation.updated_at = now
        if conversation.title == "New Conversation":
            conversation.title = "伙伴的主动问候"
        schedule.latest_created_conversation_id = (
            conversation.id if schedule.destination_mode == "new_conversation_per_delivery" else schedule.latest_created_conversation_id
        )
        schedule.last_delivered_at = now
        occurrence.conversation_id = conversation.id
        occurrence.message_id = message.id
        occurrence.presence_opportunity_id = opportunity.id
        occurrence.delivered_at = now
        occurrence.status = "delivered"
        occurrence.next_attempt_at = None
        occurrence.lease_expires_at = None
        occurrence.error_code = None
        occurrence.delivery_evidence_json = {
            "provider": generated.get("provider"),
            "model": generated.get("model"),
            "finish_reason": generated.get("finish_reason"),
            "final_boundary_recheck": "eligible",
        }
        _plan_next_locked(session, schedule, now=now)
        session.commit()


def _generate_greeting(user_id: uuid.UUID, companion_id: uuid.UUID, conversation_id: uuid.UUID | None) -> dict:
    with get_session() as session:
        companion = session.get(Companion, companion_id)
        identity = session.execute(select(CompanionIdentityProfile).where(CompanionIdentityProfile.companion_id == companion_id)).scalar_one_or_none()
        persona = session.execute(select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion_id)).scalar_one_or_none()
        relationship = session.execute(select(CompanionRelationshipContract).where(CompanionRelationshipContract.companion_id == companion_id)).scalar_one_or_none()
        boundary = session.execute(select(CompanionBoundaryProfile).where(CompanionBoundaryProfile.companion_id == companion_id)).scalar_one_or_none()
        recent: list[Message] = []
        if conversation_id:
            recent = list(session.execute(
                select(Message).where(Message.conversation_id == conversation_id, Message.deleted_at.is_(None))
                .order_by(Message.created_at.desc()).limit(8)
            ).scalars().all())
    name = (identity.display_name if identity else None) or (companion.name if companion else "伙伴")
    system_prompt = "\n".join([
        f"你是用户的长期伙伴 {name}。请生成一条自然、简短、低打扰的主动问候。",
        "不得声称看到用户当前未提供的活动，不制造紧急性，不要求立即回复。",
        "遵守 hard stop、安静时段和用户边界；只输出问候正文，不输出标题或解释。",
        f"身份：{identity.identity_summary if identity else ''}",
        f"表达风格：{persona.communication_style_summary if persona else ''}",
        f"关系约定：{relationship.contract_summary if relationship else ''}",
        f"主动表达边界：{boundary.presence_interrupt_policy if boundary else 'respect_existing_boundary'}",
    ])
    history = "\n".join(f"{item.role}: {item.content[:500]}" for item in reversed(recent))
    user_prompt = "请基于以下同一伙伴、同一会话的近期上下文自然问候；若没有上下文，做中性温和问候。\n" + (history or "（暂无近期上下文）")
    return OpenAICompatibleProvider().generate(system_prompt, user_prompt, {"temperature": 0.75, "max_tokens": 220})


def _resolve_conversation(
    session: Session, schedule: PresenceSchedule, *, create_if_needed: bool = False
) -> Conversation | None:
    if schedule.destination_mode == "bound_conversation":
        return _require_active_bound_conversation(
            session, schedule.bound_conversation_id, schedule.user_id, schedule.companion_id
        )
    if not create_if_needed:
        return None
    conversation = Conversation(
        user_id=schedule.user_id,
        companion_id=schedule.companion_id,
        title="伙伴的主动问候",
        mode_key="companion",
        status="active",
        retention_mode="standard",
        cross_session_memory_enabled=True,
        history_visible=True,
        metadata_={"origin": "scheduled_presence", "schedule_id": str(schedule.id)},
    )
    session.add(conversation)
    session.flush()
    return conversation


def _require_active_bound_conversation(
    session: Session,
    conversation_id: uuid.UUID | None,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> Conversation:
    conversation = session.get(Conversation, conversation_id) if conversation_id else None
    if (
        conversation is None
        or conversation.deleted_at is not None
        or conversation.status != "active"
        or conversation.user_id != user_id
        or conversation.companion_id != companion_id
    ):
        raise PresenceScheduleError(
            "PRESENCE_BOUND_CONVERSATION_INVALID",
            "The bound Conversation is unavailable. Choose or create another Conversation.",
        )
    return conversation


def _plan_next_locked(session: Session, schedule: PresenceSchedule, *, now: datetime, reset: bool = False) -> None:
    if schedule.status != "active":
        schedule.next_occurrence_at = None
        return
    existing = session.execute(
        select(PresenceScheduleOccurrence).where(
            PresenceScheduleOccurrence.schedule_id == schedule.id,
            PresenceScheduleOccurrence.status.in_(["scheduled", "retry_wait", "claimed"]),
        ).order_by(PresenceScheduleOccurrence.scheduled_for.asc()).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        schedule.next_occurrence_at = existing.scheduled_for
        return
    draw: dict = {"entropy": "os_csprng", "seed_persisted": False}
    earliest = now
    if not reset and schedule.last_scheduled_at is not None:
        if schedule.cadence_mode == "random_interval":
            span = schedule.random_interval_max_minutes - schedule.random_interval_min_minutes + 1
            interval = schedule.random_interval_min_minutes + secrets.randbelow(span)
            draw["interval_minutes"] = interval
        else:
            interval = schedule.fixed_interval_minutes
        earliest = max(now, _as_utc(schedule.last_scheduled_at) + timedelta(minutes=interval))
    scheduled_for, timing_draw = _select_delivery_time(schedule, earliest)
    draw.update(timing_draw)
    occurrence = _new_occurrence(session, schedule, scheduled_for, draw)
    schedule.next_occurrence_at = occurrence.scheduled_for
    schedule.last_scheduled_at = occurrence.scheduled_for


def _select_delivery_time(schedule: PresenceSchedule, earliest: datetime) -> tuple[datetime, dict]:
    try:
        zone = ZoneInfo(schedule.timezone)
    except ZoneInfoNotFoundError as exc:
        raise PresenceScheduleError("PRESENCE_TIMEZONE_INVALID", "Unknown IANA timezone.") from exc
    local_earliest = earliest.astimezone(zone)
    allowed = set(schedule.weekdays or range(7))
    for offset in range(0, 370):
        day = local_earliest.date() + timedelta(days=offset)
        if day.weekday() not in allowed:
            continue
        if schedule.timing_mode == "fixed":
            minute = schedule.fixed_minute_of_day
            draw = {"timing_mode": "fixed", "minute_of_day": minute}
        else:
            start, end = schedule.window_start_minute, schedule.window_end_minute
            minutes = _window_minutes(start, end)
            minute = minutes[secrets.randbelow(len(minutes))]
            draw = {
                "timing_mode": "random_window",
                "window_start_minute": start,
                "window_end_minute": end,
                "minute_of_day": minute,
            }
        candidate_day = day + timedelta(days=1) if minute >= 1440 else day
        minute %= 1440
        candidate = datetime.combine(candidate_day, time(minute // 60, minute % 60), tzinfo=zone)
        if candidate >= local_earliest:
            draw["local_date"] = candidate.date().isoformat()
            return candidate.astimezone(timezone.utc), draw
    raise PresenceScheduleError("PRESENCE_SCHEDULE_UNSATISFIABLE", "No valid delivery time could be found.")


def _window_minutes(start: int, end: int) -> list[int]:
    if start < end:
        return list(range(start, end + 1))
    return list(range(start, 1440)) + list(range(1440, 1440 + end + 1))


def _new_occurrence(
    session: Session, schedule: PresenceSchedule, scheduled_for: datetime, draw: dict
) -> PresenceScheduleOccurrence:
    schedule.occurrence_sequence += 1
    occurrence = PresenceScheduleOccurrence(
        schedule_id=schedule.id,
        user_id=schedule.user_id,
        companion_id=schedule.companion_id,
        schedule_revision=schedule.revision,
        sequence_no=schedule.occurrence_sequence,
        idempotency_key=f"presence-schedule:{schedule.id}:{schedule.occurrence_sequence}",
        status="scheduled",
        scheduled_for=scheduled_for,
        random_draw_json=draw,
    )
    session.add(occurrence)
    session.flush()
    return occurrence


def _finish_occurrence(occurrence_id: uuid.UUID, status: str, reason: str, evidence: dict) -> None:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        occurrence = session.execute(
            select(PresenceScheduleOccurrence).where(PresenceScheduleOccurrence.id == occurrence_id).with_for_update()
        ).scalar_one_or_none()
        if occurrence is None:
            return
        if (
            occurrence.status not in {"scheduled", "claimed", "retry_wait"}
            or occurrence.delivered_at is not None
            or occurrence.message_id is not None
        ):
            return
        schedule = session.get(PresenceSchedule, occurrence.schedule_id)
        occurrence.delivery_evidence_json = evidence
        _finish_locked(session, occurrence, schedule, status, reason, now)
        session.commit()


def _finish_locked(
    session: Session,
    occurrence: PresenceScheduleOccurrence,
    schedule: PresenceSchedule | None,
    status: str,
    reason: str,
    now: datetime,
) -> None:
    occurrence.status = status
    occurrence.next_attempt_at = None
    occurrence.lease_expires_at = None
    if status == "suppressed":
        occurrence.suppression_reason = reason
    else:
        occurrence.error_code = reason
    if schedule is not None and schedule.status == "active" and schedule.revision == occurrence.schedule_revision:
        schedule.next_occurrence_at = None
        _plan_next_locked(session, schedule, now=now)


def _retry_or_fail(occurrence_id: uuid.UUID, code: str, summary: str) -> None:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        occurrence = session.execute(
            select(PresenceScheduleOccurrence).where(PresenceScheduleOccurrence.id == occurrence_id).with_for_update()
        ).scalar_one_or_none()
        if occurrence is None:
            return
        occurrence.error_code = code
        occurrence.error_summary = summary[:1000]
        occurrence.lease_expires_at = None
        if occurrence.attempt_count < settings.PRESENCE_SCHEDULER_MAX_ATTEMPTS:
            occurrence.status = "retry_wait"
            occurrence.next_attempt_at = now + timedelta(minutes=5 * max(1, occurrence.attempt_count))
        else:
            occurrence.status = "failed"
            occurrence.next_attempt_at = None
            schedule = session.get(PresenceSchedule, occurrence.schedule_id)
            if schedule and schedule.status == "active" and schedule.revision == occurrence.schedule_revision:
                schedule.next_occurrence_at = None
                _plan_next_locked(session, schedule, now=now)
        session.commit()


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise PresenceScheduleError("PRESENCE_TIMEZONE_INVALID", "Use a valid IANA timezone.") from exc


def schedule_dict(schedule: PresenceSchedule) -> dict:
    return {
        "id": str(schedule.id),
        "user_id": str(schedule.user_id),
        "companion_id": str(schedule.companion_id),
        "status": schedule.status,
        "pause_reason": schedule.pause_reason,
        "destination_mode": schedule.destination_mode,
        "bound_conversation_id": str(schedule.bound_conversation_id) if schedule.bound_conversation_id else None,
        "latest_created_conversation_id": str(schedule.latest_created_conversation_id) if schedule.latest_created_conversation_id else None,
        "timezone": schedule.timezone,
        "weekdays": list(schedule.weekdays or []),
        "timing_mode": schedule.timing_mode,
        "fixed_minute_of_day": schedule.fixed_minute_of_day,
        "window_start_minute": schedule.window_start_minute,
        "window_end_minute": schedule.window_end_minute,
        "cadence_mode": schedule.cadence_mode,
        "fixed_interval_minutes": schedule.fixed_interval_minutes,
        "random_interval_min_minutes": schedule.random_interval_min_minutes,
        "random_interval_max_minutes": schedule.random_interval_max_minutes,
        "revision": schedule.revision,
        "next_occurrence_at": schedule.next_occurrence_at.isoformat() if schedule.next_occurrence_at else None,
        "last_delivered_at": schedule.last_delivered_at.isoformat() if schedule.last_delivered_at else None,
        "updated_at": schedule.updated_at.isoformat(),
    }


def _occurrence_dict(row: PresenceScheduleOccurrence) -> dict:
    return {
        "id": str(row.id),
        "schedule_id": str(row.schedule_id),
        "status": row.status,
        "sequence_no": row.sequence_no,
        "scheduled_for": row.scheduled_for.isoformat(),
        "next_attempt_at": row.next_attempt_at.isoformat() if row.next_attempt_at else None,
        "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None,
        "attempt_count": row.attempt_count,
        "conversation_id": str(row.conversation_id) if row.conversation_id else None,
        "message_id": str(row.message_id) if row.message_id else None,
        "suppression_reason": row.suppression_reason,
        "error_code": row.error_code,
        "random_draw": row.random_draw_json or {},
        "delivery_evidence": row.delivery_evidence_json or {},
    }


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
