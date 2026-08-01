"""Create, query, sanitize, and apply canonical feedback samples."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.feedback_event import FeedbackEvent
from app.db.models.memory import Memory


FEEDBACK_ALGORITHM_VERSION = "core-feedback-v1"
_INFERRED_ACTIONS = {"shown", "continued", "ignored"}
_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "history",
    "password",
    "prompt",
    "raw_content",
    "raw_history",
    "raw_message",
    "secret",
    "token",
    "transcript",
}
_SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/=-]{8,}|sk-[a-z0-9_-]{8,}|"
    r"(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+)"
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def _as_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _action_to_label(action: str) -> str:
    mapping = {
        "accept": "positive",
        "confirm": "positive",
        "helpful": "positive",
        "lock": "positive",
        "accept_presence": "positive",
        "continued": "positive",
        "useful": "positive",
        "edit_accept": "weak_positive",
        "shown": "neutral",
        "archive": "neutral",
        "mark_sensitive": "neutral",
        "snooze": "weak_negative",
        "ignored": "weak_negative",
        "fade": "negative",
        "irrelevant": "negative",
        "dismiss": "negative",
        "outdated": "negative",
        "too_tool_like": "negative",
        "too_verbose": "negative",
        "too_intrusive": "strong_negative",
        "delete": "strong_negative",
        "wrong": "strong_negative",
        "revert": "strong_negative",
        "suppress_type": "strong_negative",
        "disabled": "strong_negative",
        "reject": "strong_negative",
        "mark_important": "positive",
        "reactivate": "positive",
    }
    return mapping.get(action, "neutral")


def _action_to_reward(action: str) -> float:
    mapping = {
        "accept": 1.0,
        "confirm": 1.0,
        "helpful": 1.0,
        "lock": 0.8,
        "accept_presence": 1.0,
        "continued": 0.8,
        "useful": 1.0,
        "edit_accept": 0.6,
        "shown": 0.0,
        "archive": 0.0,
        "mark_sensitive": 0.0,
        "snooze": -0.25,
        "ignored": -0.35,
        "fade": -0.6,
        "irrelevant": -0.7,
        "dismiss": -0.8,
        "outdated": -0.8,
        "too_tool_like": -0.6,
        "too_verbose": -0.6,
        "too_intrusive": -1.0,
        "delete": -1.0,
        "wrong": -1.0,
        "revert": -1.0,
        "suppress_type": -1.0,
        "disabled": -1.0,
        "reject": -1.0,
        "mark_important": 0.8,
        "reactivate": 0.8,
    }
    return mapping.get(action, 0.0)


def _infer_applies(action: str, target_type: str) -> dict[str, bool]:
    result = {
        "applies_to_memory": False,
        "applies_to_growth": False,
        "applies_to_presence": False,
        "applies_to_retrieval": False,
        "applies_to_relationship": False,
        "applies_to_boundary": False,
    }
    if target_type in {"memory", "memory_candidate", "related_memory"}:
        result["applies_to_memory"] = True
    if target_type in {"growth_candidate", "growth_record"}:
        result["applies_to_growth"] = True
    if target_type == "presence_opportunity":
        result["applies_to_presence"] = True
    if target_type in {"related_memory", "retrieval_result"}:
        result["applies_to_retrieval"] = True
    if target_type == "relationship":
        result["applies_to_relationship"] = True
    if target_type == "settings":
        result["applies_to_boundary"] = True
    if action in {"snooze", "dismiss", "suppress_type", "accept_presence", "shown", "continued", "ignored", "disabled"}:
        result["applies_to_presence"] = True
    return result


def _algorithm_key(target_type: str) -> str:
    if target_type in {"memory", "memory_candidate"}:
        return "memory_lifecycle"
    if target_type in {"related_memory", "retrieval_result"}:
        return "memory_retrieval"
    if target_type in {"growth_candidate", "growth_record"}:
        return "growth"
    if target_type == "presence_opportunity":
        return "presence"
    if target_type == "strategy":
        return "companionship_strategy"
    return "core_feedback"


def _sanitize_value(value: Any) -> tuple[Any, bool]:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        changed = False
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                safe[str(key)] = "[REDACTED]"
                changed = True
                continue
            safe_item, item_changed = _sanitize_value(item)
            safe[str(key)] = safe_item
            changed = changed or item_changed
        return safe, changed
    if isinstance(value, list):
        safe_items = []
        changed = False
        for item in value:
            safe_item, item_changed = _sanitize_value(item)
            safe_items.append(safe_item)
            changed = changed or item_changed
        return safe_items, changed
    if isinstance(value, str):
        safe = _SECRET_PATTERN.sub("[REDACTED]", value)
        return safe, safe != value
    return value, False


def sanitize_learning_payload(value: Any) -> Any:
    """Return a copy safe for audit/training feature storage."""
    return _sanitize_value(value)[0]


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _idempotency_key(data: dict, context_hash: str) -> str:
    explicit_key = data.get("idempotency_key")
    if explicit_key:
        raw = "|".join(
            (
                str(data.get("user_id") or ""),
                str(data.get("companion_id") or ""),
                str(explicit_key),
            )
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    correlation = "|".join(
        str(data.get(key) or "")
        for key in ("trace_run_id", "message_id", "conversation_id", "target_type", "target_id", "action")
    )
    raw = "|".join(
        (
            str(data.get("user_id") or ""),
            str(data.get("companion_id") or ""),
            correlation,
            context_hash,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_feedback_event(data: dict) -> dict:
    safe_context, context_redacted = _sanitize_value(data.get("context_json", {}))
    safe_provenance, provenance_redacted = _sanitize_value(data.get("sample_provenance", {}))
    safe_reason, reason_redacted = _sanitize_value(data.get("reason"))
    safe_note, note_redacted = _sanitize_value(data.get("user_note"))
    any_redacted = context_redacted or provenance_redacted or reason_redacted or note_redacted

    risk_level = data.get("risk_level", "low")
    requested_redaction = data.get("redaction_status")
    redaction_status = "redacted" if any_redacted else (requested_redaction or "not_required")
    training_eligible = data.get("training_eligible", True)
    if any_redacted or risk_level in {"high", "critical"} or redaction_status == "blocked":
        training_eligible = False
    if risk_level in {"high", "critical"}:
        safe_note = "[REDACTED: high-risk feedback note]" if safe_note else None

    action = data["action"]
    target_type = data["target_type"]
    label = data.get("label") or _action_to_label(action)
    reward = data.get("reward")
    if reward is None:
        reward = _action_to_reward(action)
    reward = max(-1.0, min(1.0, float(reward)))
    source = data.get("feedback_source") or ("inferred" if action in _INFERRED_ACTIONS else "explicit")
    context_hash = _canonical_hash(safe_context)
    idempotency_key = _idempotency_key(data, context_hash)
    applies = _infer_applies(action, target_type)

    with get_session() as session:
        existing = session.execute(
            select(FeedbackEvent).where(
                FeedbackEvent.idempotency_key == idempotency_key,
                FeedbackEvent.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if existing:
            return _fe_dict(existing, [], idempotent_replay=True)

        event = FeedbackEvent(
            user_id=_as_uuid(data["user_id"]),
            companion_id=_as_uuid(data["companion_id"]),
            conversation_id=_as_uuid(data.get("conversation_id")),
            message_id=_as_uuid(data.get("message_id")),
            trace_run_id=_as_uuid(data.get("trace_run_id")),
            target_type=target_type,
            target_id=_as_uuid(data.get("target_id")),
            action=action,
            label=label,
            idempotency_key=idempotency_key,
            feedback_source=source,
            reward=reward,
            reason=safe_reason,
            user_note=safe_note,
            score_delta=float(data.get("score_delta", 0.0)),
            confidence_delta=float(data.get("confidence_delta", 0.0)),
            strength_delta=float(data.get("strength_delta", 0.0)),
            priority_delta=float(data.get("priority_delta", 0.0)),
            context_json=safe_context,
            sample_provenance=safe_provenance,
            context_hash=context_hash,
            algorithm_key=data.get("algorithm_key") or _algorithm_key(target_type),
            algorithm_version=data.get("algorithm_version") or FEEDBACK_ALGORITHM_VERSION,
            risk_level=risk_level,
            redaction_status=redaction_status,
            training_eligible=bool(training_eligible),
            **{
                key: bool(applies[key] or data.get(key, False))
                for key in applies
            },
        )
        session.add(event)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            existing = session.execute(
                select(FeedbackEvent).where(FeedbackEvent.idempotency_key == idempotency_key)
            ).scalar_one()
            return _fe_dict(existing, [], idempotent_replay=True)

        effects: list[dict] = []
        apply_now = data.get("apply_immediately", True)
        if apply_now and label != "neutral":
            effects = _apply_basic_calibration(session, event)
        if data.get("effect_already_applied") or (apply_now and effects):
            event.calibration_status = "applied"
            event.applied_at = datetime.now(timezone.utc)

        session.commit()
        session.refresh(event)
        return _fe_dict(event, effects)


def _apply_basic_calibration(session: Session, event: FeedbackEvent) -> list[dict]:
    effects = []
    if not event.applies_to_memory or not event.target_id or event.target_type != "memory":
        return effects

    memory = session.get(Memory, event.target_id)
    if memory is None:
        return effects

    before = {
        "helpful_count": memory.helpful_count,
        "irrelevant_count": memory.irrelevant_count,
        "wrong_count": memory.wrong_count,
        "feedback_score": memory.feedback_score,
    }
    if event.label == "positive":
        memory.helpful_count += 1
        memory.feedback_score = min(1.0, memory.feedback_score + 0.05)
    elif event.label == "weak_positive":
        memory.feedback_score = min(1.0, memory.feedback_score + 0.02)
    elif event.label in {"weak_negative", "negative"}:
        memory.irrelevant_count += 1
        memory.feedback_score = max(-1.0, memory.feedback_score - 0.05)
    elif event.label == "strong_negative":
        memory.wrong_count += 1
        memory.feedback_score = max(-1.0, memory.feedback_score - 0.10)
    memory.last_feedback_at = datetime.now(timezone.utc)
    after = {
        "helpful_count": memory.helpful_count,
        "irrelevant_count": memory.irrelevant_count,
        "wrong_count": memory.wrong_count,
        "feedback_score": round(memory.feedback_score, 4),
    }
    event.before_json = before
    event.after_json = after
    effects.append(
        {
            "target_type": "memory",
            "target_id": str(event.target_id),
            "field_changes": [
                {"field": field, "before": before[field], "after": after[field]}
                for field in before
                if before[field] != after[field]
            ],
            "user_visible_summary": _effect_summary(event.label),
        }
    )
    return effects


def _effect_summary(label: str) -> str:
    mapping = {
        "positive": "This memory will be favored in later retrieval.",
        "weak_positive": "This memory received a small relevance increase.",
        "weak_negative": "This memory received a small relevance decrease.",
        "negative": "This memory will be deprioritized in later retrieval.",
        "strong_negative": "This memory was marked inaccurate and strongly deprioritized.",
    }
    return mapping.get(label, "Feedback was recorded.")


def list_feedback_events(
    companion_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    label: str | None = None,
    calibration_status: str | None = None,
    feedback_source: str | None = None,
    risk_level: str | None = None,
    training_eligible: bool | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    with get_session() as session:
        stmt = select(FeedbackEvent).where(FeedbackEvent.deleted_at.is_(None))
        filters = {
            FeedbackEvent.companion_id: companion_id,
            FeedbackEvent.target_type: target_type,
            FeedbackEvent.target_id: target_id,
            FeedbackEvent.label: label,
            FeedbackEvent.calibration_status: calibration_status,
            FeedbackEvent.feedback_source: feedback_source,
            FeedbackEvent.risk_level: risk_level,
            FeedbackEvent.training_eligible: training_eligible,
        }
        for column, value in filters.items():
            if value is not None:
                stmt = stmt.where(column == value)
        if created_after:
            stmt = stmt.where(FeedbackEvent.created_at >= created_after)
        if created_before:
            stmt = stmt.where(FeedbackEvent.created_at <= created_before)
        total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(FeedbackEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = [_fe_dict(event) for event in session.execute(stmt).scalars().all()]
        return {"items": items, "total": total}


def get_feedback_event(fe_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        event = session.get(FeedbackEvent, fe_id)
        return _fe_dict(event) if event else None


def update_feedback_event(fe_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        event = session.get(FeedbackEvent, fe_id)
        if event is None:
            return None
        for key in ("calibration_status", "reason", "user_note"):
            if key in data and data[key] is not None:
                safe_value, changed = _sanitize_value(data[key])
                setattr(event, key, safe_value)
                if changed:
                    event.redaction_status = "redacted"
                    event.training_eligible = False
        session.commit()
        session.refresh(event)
        return _fe_dict(event)


def apply_feedback_event(fe_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        event = session.get(FeedbackEvent, fe_id)
        if event is None:
            return None
        if event.calibration_status == "applied":
            return _fe_dict(event)
        effects = _apply_basic_calibration(session, event)
        event.calibration_status = "applied"
        event.applied_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(event)
        return _fe_dict(event, effects)


def _fe_dict(
    event: FeedbackEvent,
    effects: list[dict] | None = None,
    *,
    idempotent_replay: bool = False,
) -> dict:
    return {
        "id": str(event.id),
        "user_id": str(event.user_id),
        "companion_id": str(event.companion_id),
        "conversation_id": str(event.conversation_id) if event.conversation_id else None,
        "message_id": str(event.message_id) if event.message_id else None,
        "trace_run_id": str(event.trace_run_id) if event.trace_run_id else None,
        "target_type": event.target_type,
        "target_id": str(event.target_id) if event.target_id else None,
        "action": event.action,
        "label": event.label,
        "idempotency_key": event.idempotency_key,
        "feedback_source": event.feedback_source,
        "reward": event.reward,
        "reason": event.reason,
        "user_note": event.user_note,
        "score_delta": event.score_delta,
        "confidence_delta": event.confidence_delta,
        "strength_delta": event.strength_delta,
        "priority_delta": event.priority_delta,
        "applies_to_memory": event.applies_to_memory,
        "applies_to_growth": event.applies_to_growth,
        "applies_to_presence": event.applies_to_presence,
        "applies_to_retrieval": event.applies_to_retrieval,
        "applies_to_relationship": event.applies_to_relationship,
        "applies_to_boundary": event.applies_to_boundary,
        "calibration_status": event.calibration_status,
        "applied_at": event.applied_at.isoformat() if event.applied_at else None,
        "context_json": event.context_json,
        "sample_provenance": event.sample_provenance,
        "context_hash": event.context_hash,
        "algorithm_key": event.algorithm_key,
        "algorithm_version": event.algorithm_version,
        "risk_level": event.risk_level,
        "redaction_status": event.redaction_status,
        "training_eligible": event.training_eligible,
        "idempotent_replay": idempotent_replay,
        "before_json": event.before_json,
        "after_json": event.after_json,
        "effects": effects or [],
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
    }
