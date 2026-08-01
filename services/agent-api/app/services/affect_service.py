"""Versioned Companion affect truth and correction service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.affect.dynamics import ALGORITHM_VERSION, apply_appraisal, decay_state, expression_projection
from app.core.config import settings
from app.db.models import Companion, CompanionAffectEvent, CompanionAffectState, Message


_engine = None


class AffectMutationError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def get_affect_state(companion_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.execute(select(CompanionAffectState).where(CompanionAffectState.companion_id == companion_id)).scalar_one_or_none()
        return _state_dict(row, include_decayed=True) if row else None


def list_affect_events(companion_id: uuid.UUID, page: int = 1, page_size: int = 20) -> dict:
    with get_session() as session:
        stmt = select(CompanionAffectEvent).where(CompanionAffectEvent.companion_id == companion_id)
        total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        rows = list(session.execute(stmt.order_by(CompanionAffectEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).scalars())
        return {"items": [_event_dict(row) for row in rows], "total": total}


def apply_validated_appraisal(data: dict[str, Any]) -> dict:
    validation = dict(data.get("validation") or {})
    if validation.get("status") != "passed":
        raise AffectMutationError("AFFECT_APPRAISAL_NOT_VALIDATED", "Affect appraisal must pass deterministic validation.")
    now = datetime.now(timezone.utc)
    message_ids = _uuid_list(data.get("source_message_ids"))
    with get_session() as session:
        companion = session.get(Companion, data["companion_id"])
        if companion is None or companion.deleted_at is not None or companion.user_id != data["user_id"]:
            raise AffectMutationError("AFFECT_SCOPE_MISMATCH", "Companion scope does not match appraisal owner.")
        _validate_messages(session, companion.id, message_ids, str(data["evidence_quote"]), data.get("conversation_id"))
        existing = session.execute(select(CompanionAffectEvent).where(CompanionAffectEvent.idempotency_key == data["idempotency_key"])).scalar_one_or_none()
        if existing:
            state = session.execute(select(CompanionAffectState).where(CompanionAffectState.companion_id == companion.id)).scalar_one()
            return {"state": _state_dict(state), "event": _event_dict(existing)}
        state = session.execute(select(CompanionAffectState).where(
            CompanionAffectState.user_id == companion.user_id, CompanionAffectState.companion_id == companion.id,
        ).with_for_update()).scalar_one_or_none()
        if state is None:
            state = CompanionAffectState(user_id=companion.user_id, companion_id=companion.id, last_transition_at=now)
            session.add(state)
            session.flush()
        transition = apply_appraisal(_state_values(state), {**validation["appraisals"], "confidence": validation["confidence"], "evidence_score": validation["evidence_score"]}, at=now)
        state.revision += 1
        state.valence, state.arousal = transition["after"]["valence"], transition["after"]["arousal"]
        state.last_transition_at = now
        state.expression_json = transition["expression"]
        event = CompanionAffectEvent(
            user_id=state.user_id, companion_id=state.companion_id,
            conversation_id=data.get("conversation_id"), trace_run_id=data.get("trace_run_id"),
            source_message_ids=message_ids, summary=str(data["summary"])[:300], evidence_quote=str(data["evidence_quote"])[:500],
            appraisal_json=validation["appraisals"], transition_json=_json_transition(transition),
            extraction_json=dict(data.get("extraction") or {}), validation_json=validation,
            state_revision=state.revision, provider_name=data.get("provider_name"), model_name=data.get("model_name"),
            algorithm_version=ALGORITHM_VERSION, idempotency_key=str(data["idempotency_key"]),
        )
        session.add(event)
        session.flush()
        state.current_event_id = event.id
        session.commit()
        session.refresh(state); session.refresh(event)
        return {"state": _state_dict(state), "event": _event_dict(event)}


def update_expression_preferences(companion_id: uuid.UUID, *, expected_revision: int, enabled: bool, intensity: str) -> dict:
    if intensity not in {"off", "subtle", "balanced"}:
        raise AffectMutationError("AFFECT_PREFERENCE_INVALID", "Expression intensity is invalid.")
    with get_session() as session:
        state = session.execute(select(CompanionAffectState).where(CompanionAffectState.companion_id == companion_id).with_for_update()).scalar_one_or_none()
        if state is None:
            companion = session.get(Companion, companion_id)
            if companion is None or companion.deleted_at is not None:
                raise AffectMutationError("AFFECT_STATE_NOT_FOUND", "Companion affect state not found.")
            state = CompanionAffectState(user_id=companion.user_id, companion_id=companion.id)
            session.add(state); session.flush()
        if state.revision != expected_revision:
            raise AffectMutationError("AFFECT_REVISION_CONFLICT", "Affect state changed after it was loaded.", {"current_revision": state.revision})
        state.expression_enabled = bool(enabled)
        state.expression_intensity = intensity
        state.revision += 1
        session.commit(); session.refresh(state)
        return _state_dict(state)


def invalidate_event(event_id: uuid.UUID, companion_id: uuid.UUID, *, expected_revision: int, reason: str) -> dict:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        source = session.execute(select(CompanionAffectEvent).where(
            CompanionAffectEvent.id == event_id, CompanionAffectEvent.companion_id == companion_id,
        ).with_for_update()).scalar_one_or_none()
        state = session.execute(select(CompanionAffectState).where(CompanionAffectState.companion_id == companion_id).with_for_update()).scalar_one_or_none()
        if source is None or state is None:
            raise AffectMutationError("AFFECT_EVENT_NOT_FOUND", "Affect event not found.")
        if source.status != "active" or source.operation != "appraised" or state.current_event_id != source.id:
            raise AffectMutationError("AFFECT_EVENT_NOT_CURRENT", "Only the current active affect event can be corrected.")
        if state.revision != expected_revision:
            raise AffectMutationError("AFFECT_REVISION_CONFLICT", "Affect state changed after it was loaded.", {"current_revision": state.revision})
        before = {"valence": state.valence, "arousal": state.arousal}
        source_before = dict((source.transition_json or {}).get("before") or {})
        if set(source_before) != {"valence", "arousal"}:
            raise AffectMutationError("AFFECT_EVENT_NOT_CORRECTABLE", "Affect event has no restorable prior state.")
        corrected_decay = decay_state({
            "valence": source_before["valence"], "arousal": source_before["arousal"],
            "home_valence": state.home_valence, "home_arousal": state.home_arousal,
            "half_life_hours": state.half_life_hours,
            "last_transition_at": source.created_at,
        }, now)
        target = {"valence": corrected_decay["valence"], "arousal": corrected_decay["arousal"]}
        state.revision += 1
        state.valence, state.arousal = float(target["valence"]), float(target["arousal"])
        state.last_transition_at = now
        state.expression_json = expression_projection(state.valence, state.arousal)
        source.status = "invalidated"; source.invalidated_at = now
        correction = CompanionAffectEvent(
            user_id=state.user_id, companion_id=state.companion_id, status="active", operation="corrected",
            summary=reason, evidence_quote="用户纠正该事件理解", appraisal_json={},
            transition_json={"before": before, "after": target, "expression": state.expression_json},
            extraction_json={}, validation_json={"status": "user_corrected"}, state_revision=state.revision,
            supersedes_event_id=source.id, algorithm_version=ALGORITHM_VERSION,
            idempotency_key=f"affect-correction:{source.id}:{state.revision}",
        )
        session.add(correction); session.flush(); state.current_event_id = correction.id
        session.commit(); session.refresh(state); session.refresh(correction)
        return {"state": _state_dict(state), "event": _event_dict(correction)}


def _validate_messages(session: Session, companion_id: uuid.UUID, ids: list[uuid.UUID], quote: str, conversation_id: Any) -> None:
    stmt = select(Message).where(Message.id.in_(ids), Message.companion_id == companion_id, Message.deleted_at.is_(None))
    if conversation_id:
        stmt = stmt.where(Message.conversation_id == uuid.UUID(str(conversation_id)))
    rows = list(session.execute(stmt).scalars())
    if {row.id for row in rows} != set(ids) or not any(row.role == "user" and quote in row.content for row in rows):
        raise AffectMutationError("AFFECT_EVIDENCE_SCOPE_MISMATCH", "Affect evidence is missing or outside Companion scope.")


def _state_values(row: CompanionAffectState) -> dict:
    return {"valence": row.valence, "arousal": row.arousal, "home_valence": row.home_valence, "home_arousal": row.home_arousal,
            "half_life_hours": row.half_life_hours, "last_transition_at": row.last_transition_at}


def _state_dict(row: CompanionAffectState, include_decayed: bool = False) -> dict:
    values = decay_state(_state_values(row)) if include_decayed else {"valence": row.valence, "arousal": row.arousal}
    expression = expression_projection(values["valence"], values["arousal"])
    return {"id": str(row.id), "user_id": str(row.user_id), "companion_id": str(row.companion_id), "revision": row.revision,
            "current_event_id": str(row.current_event_id) if row.current_event_id else None,
            "expression": expression, "expression_enabled": row.expression_enabled, "expression_intensity": row.expression_intensity,
            "last_transition_at": row.last_transition_at.isoformat() if row.last_transition_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None}


def _event_dict(row: CompanionAffectEvent) -> dict:
    return {"id": str(row.id), "companion_id": str(row.companion_id), "conversation_id": str(row.conversation_id) if row.conversation_id else None,
            "status": row.status, "operation": row.operation, "summary": row.summary, "evidence_quote": row.evidence_quote,
            "appraisals": row.appraisal_json or {}, "transition": row.transition_json or {}, "state_revision": row.state_revision,
            "supersedes_event_id": str(row.supersedes_event_id) if row.supersedes_event_id else None,
            "provider_name": row.provider_name, "model_name": row.model_name, "algorithm_version": row.algorithm_version,
            "created_at": row.created_at.isoformat() if row.created_at else None, "invalidated_at": row.invalidated_at.isoformat() if row.invalidated_at else None}


def _json_transition(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "at"}


def _uuid_list(values: Any) -> list[uuid.UUID]:
    return [value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)) for value in (values or [])]
