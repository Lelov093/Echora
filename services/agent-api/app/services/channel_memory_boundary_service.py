"""Channel Gateway channel memory boundary and review service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    ChannelBinding,
    ChannelContextRedactionEvent,
    ChannelMemoryCandidate,
    ChannelMemoryGateTrace,
    ChannelMemoryReview,
    ChannelMessageEvent,
)

_engine = None
_SENSITIVE_KEY_PARTS = ("token", "secret", "password", "api_key", "authorization", "credential", "raw")


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_candidates(
    *,
    channel_binding_id: uuid.UUID | None = None,
    companion_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelMemoryCandidate)
        if channel_binding_id is not None:
            stmt = stmt.where(ChannelMemoryCandidate.channel_binding_id == channel_binding_id)
        if companion_id is not None:
            stmt = stmt.where(ChannelMemoryCandidate.companion_id == companion_id)
        if status:
            stmt = stmt.where(ChannelMemoryCandidate.candidate_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelMemoryCandidate.updated_at.desc(), ChannelMemoryCandidate.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_candidate_to_dict(item) for item in items], "total": total}


def list_reviews(
    *,
    candidate_id: uuid.UUID | None = None,
    decision: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelMemoryReview)
        if candidate_id is not None:
            stmt = stmt.where(ChannelMemoryReview.channel_memory_candidate_id == candidate_id)
        if decision:
            stmt = stmt.where(ChannelMemoryReview.review_decision == decision)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelMemoryReview.updated_at.desc(), ChannelMemoryReview.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_review_to_dict(item) for item in items], "total": total}


def get_candidate(candidate_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        candidate = s.get(ChannelMemoryCandidate, candidate_id)
        if candidate is None:
            return None
        return _candidate_bundle(s, candidate)


def create_candidate(payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        binding = s.get(ChannelBinding, _to_uuid(payload.get("channel_binding_id")))
        if binding is None:
            return None
        if binding.binding_status == "revoked" or binding.revoked_at is not None:
            return None
        message = s.get(ChannelMessageEvent, _to_uuid(payload.get("channel_message_event_id"))) if payload.get("channel_message_event_id") else None
        if message is not None and message.channel_binding_id != binding.id:
            return None

        candidate = ChannelMemoryCandidate(
            user_id=binding.user_id,
            companion_id=binding.companion_id,
            channel_binding_id=binding.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            channel_message_event_id=message.id if message else None,
            channel_ephemeral_buffer_item_id=_to_uuid(payload.get("channel_ephemeral_buffer_item_id")),
            candidate_status="pending_review",
            target_memory_scope=payload.get("target_memory_scope") or "companion_private",
            candidate_summary=_truncate(str(payload.get("candidate_summary") or "Channel memory candidate"), 500),
            suggested_memory_content=_truncate(str(payload.get("suggested_memory_content") or ""), 2000),
            salience_score=_bounded_float(payload.get("salience_score"), default=0.5),
            requires_user_review=True,
            auto_commit_allowed=False,
            raw_payload_storage_allowed=False,
            safe_evidence_json=_safe_json(payload.get("safe_evidence_json")),
            metadata_={"implementation_origin": "channel_memory", "memory_write": "not_committed"},
        )
        s.add(candidate)
        s.flush()
        trace = _record_gate_trace(
            s,
            candidate,
            "candidate_created",
            "review_required",
            "Channel memory candidate created; review required",
        )
        s.commit()
        s.refresh(candidate)
        return {**_candidate_bundle(s, candidate), "memory_gate_trace": _gate_trace_to_dict(trace)}


def approve_candidate(candidate_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _review_candidate(candidate_id, "approved", payload)


def reject_candidate(candidate_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _review_candidate(candidate_id, "rejected", payload)


def redact_candidate(candidate_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        candidate = s.get(ChannelMemoryCandidate, candidate_id)
        if candidate is None:
            return None
        candidate.candidate_status = "redacted"
        candidate.raw_payload_storage_allowed = False
        candidate.auto_commit_allowed = False
        candidate.updated_at = _now()
        review = _create_review(s, candidate, "redacted", payload, memory_write_allowed=False)
        redaction = ChannelContextRedactionEvent(
            user_id=candidate.user_id,
            channel_binding_id=candidate.channel_binding_id,
            channel_message_event_id=candidate.channel_message_event_id,
            channel_memory_candidate_id=candidate.id,
            redaction_scope="memory_candidate",
            redaction_status="applied",
            redaction_reason=payload.get("review_notes") or payload.get("reason"),
            safe_redaction_payload_json=_safe_json(payload.get("safe_review_payload_json")),
            applied_at=_now(),
            metadata_={"implementation_origin": "channel_memory"},
        )
        s.add(redaction)
        trace = _record_gate_trace(s, candidate, "redacted", "redacted", "Channel memory candidate redacted")
        s.commit()
        s.refresh(candidate)
        s.refresh(review)
        s.refresh(redaction)
        return {
            **_candidate_bundle(s, candidate),
            "review": _review_to_dict(review),
            "redaction_event": _redaction_to_dict(redaction),
            "memory_gate_trace": _gate_trace_to_dict(trace),
        }


def commit_intent(candidate_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        candidate = s.get(ChannelMemoryCandidate, candidate_id)
        if candidate is None:
            return None
        approved_review = s.execute(
            select(ChannelMemoryReview)
            .where(
                ChannelMemoryReview.channel_memory_candidate_id == candidate.id,
                ChannelMemoryReview.review_decision == "approved",
                ChannelMemoryReview.memory_write_allowed_after_review.is_(True),
            )
            .order_by(ChannelMemoryReview.reviewed_at.desc(), ChannelMemoryReview.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if approved_review is None:
            return None
        candidate.candidate_status = "committed"
        candidate.auto_commit_allowed = False
        candidate.raw_payload_storage_allowed = False
        candidate.updated_at = _now()
        trace = _record_gate_trace(
            s,
            candidate,
            "review_required",
            "recorded",
            "Commit intent recorded; existing memory write chain must execute separately",
            payload={"commit_intent_only": True, "memory_written": False},
        )
        s.commit()
        s.refresh(candidate)
        return {
            **_candidate_bundle(s, candidate),
            "approved_review": _review_to_dict(approved_review),
            "memory_gate_trace": _gate_trace_to_dict(trace),
            "memory_write": "not_written_commit_intent_only",
        }


def _review_candidate(candidate_id: uuid.UUID, decision: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        candidate = s.get(ChannelMemoryCandidate, candidate_id)
        if candidate is None:
            return None
        candidate.candidate_status = "approved" if decision == "approved" else "rejected"
        candidate.auto_commit_allowed = False
        candidate.raw_payload_storage_allowed = False
        candidate.updated_at = _now()
        review = _create_review(
            s,
            candidate,
            decision,
            payload,
            memory_write_allowed=(decision == "approved"),
        )
        trace = _record_gate_trace(
            s,
            candidate,
            "review_required",
            "review_required" if decision == "approved" else "recorded",
            f"Channel memory candidate {decision}",
        )
        s.commit()
        s.refresh(candidate)
        s.refresh(review)
        return {
            **_candidate_bundle(s, candidate),
            "review": _review_to_dict(review),
            "memory_gate_trace": _gate_trace_to_dict(trace),
        }


def _create_review(
    s: Session,
    candidate: ChannelMemoryCandidate,
    decision: str,
    payload: dict[str, Any],
    *,
    memory_write_allowed: bool,
) -> ChannelMemoryReview:
    review = ChannelMemoryReview(
        user_id=candidate.user_id,
        channel_memory_candidate_id=candidate.id,
        review_decision=decision,
        target_memory_id=None,
        review_notes=payload.get("review_notes"),
        memory_write_allowed_after_review=memory_write_allowed,
        safe_review_payload_json=_safe_json(payload.get("safe_review_payload_json")),
        reviewed_at=_now(),
        metadata_={"implementation_origin": "channel_memory", "memory_write": "not_written"},
    )
    s.add(review)
    return review


def _record_gate_trace(
    s: Session,
    candidate: ChannelMemoryCandidate,
    decision: str,
    status: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> ChannelMemoryGateTrace:
    trace = ChannelMemoryGateTrace(
        user_id=candidate.user_id,
        companion_id=candidate.companion_id,
        channel_binding_id=candidate.channel_binding_id,
        channel_message_event_id=candidate.channel_message_event_id,
        channel_memory_candidate_id=candidate.id,
        memory_gate_decision=decision,
        memory_gate_status=status,
        gate_summary=summary,
        safe_gate_payload_json={"auto_commit_allowed": False, "raw_payload_storage_allowed": False, **(payload or {})},
        occurred_at=_now(),
        metadata_={"implementation_origin": "channel_memory"},
    )
    s.add(trace)
    s.flush()
    return trace


def _candidate_bundle(s: Session, candidate: ChannelMemoryCandidate) -> dict[str, Any]:
    reviews = list(
        s.execute(
            select(ChannelMemoryReview)
            .where(ChannelMemoryReview.channel_memory_candidate_id == candidate.id)
            .order_by(ChannelMemoryReview.reviewed_at.desc(), ChannelMemoryReview.created_at.desc())
            .limit(10)
        ).scalars().all()
    )
    traces = list(
        s.execute(
            select(ChannelMemoryGateTrace)
            .where(ChannelMemoryGateTrace.channel_memory_candidate_id == candidate.id)
            .order_by(ChannelMemoryGateTrace.occurred_at.desc())
            .limit(10)
        ).scalars().all()
    )
    return {
        **_candidate_to_dict(candidate),
        "recent_reviews": [_review_to_dict(item) for item in reviews],
        "recent_memory_gate_traces": [_gate_trace_to_dict(item) for item in traces],
    }


def _candidate_to_dict(row: ChannelMemoryCandidate) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "companion_id": str(row.companion_id),
        "channel_binding_id": str(row.channel_binding_id),
        "provider_id": str(row.provider_id),
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "channel_message_event_id": str(row.channel_message_event_id) if row.channel_message_event_id else None,
        "channel_ephemeral_buffer_item_id": str(row.channel_ephemeral_buffer_item_id) if row.channel_ephemeral_buffer_item_id else None,
        "candidate_status": row.candidate_status,
        "target_memory_scope": row.target_memory_scope,
        "candidate_summary": row.candidate_summary,
        "suggested_memory_content": row.suggested_memory_content,
        "salience_score": row.salience_score,
        "requires_user_review": row.requires_user_review,
        "auto_commit_allowed": row.auto_commit_allowed,
        "raw_payload_storage_allowed": row.raw_payload_storage_allowed,
        "safe_evidence_json": row.safe_evidence_json or {},
    }


def _review_to_dict(row: ChannelMemoryReview) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "channel_memory_candidate_id": str(row.channel_memory_candidate_id),
        "review_decision": row.review_decision,
        "target_memory_id": str(row.target_memory_id) if row.target_memory_id else None,
        "review_notes": row.review_notes,
        "memory_write_allowed_after_review": row.memory_write_allowed_after_review,
        "safe_review_payload_json": row.safe_review_payload_json or {},
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


def _redaction_to_dict(row: ChannelContextRedactionEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "channel_binding_id": str(row.channel_binding_id) if row.channel_binding_id else None,
        "channel_message_event_id": str(row.channel_message_event_id) if row.channel_message_event_id else None,
        "channel_memory_candidate_id": str(row.channel_memory_candidate_id) if row.channel_memory_candidate_id else None,
        "redaction_scope": row.redaction_scope,
        "redaction_status": row.redaction_status,
        "redaction_reason": row.redaction_reason,
        "safe_redaction_payload_json": row.safe_redaction_payload_json or {},
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
    }


def _gate_trace_to_dict(row: ChannelMemoryGateTrace) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "channel_binding_id": str(row.channel_binding_id),
        "channel_message_event_id": str(row.channel_message_event_id) if row.channel_message_event_id else None,
        "channel_memory_candidate_id": str(row.channel_memory_candidate_id) if row.channel_memory_candidate_id else None,
        "memory_gate_decision": row.memory_gate_decision,
        "memory_gate_status": row.memory_gate_status,
        "gate_summary": row.gate_summary,
        "safe_gate_payload_json": row.safe_gate_payload_json or {},
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _safe_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _scrub(value)


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower().replace("-", "_") for part in _SENSITIVE_KEY_PARTS):
                continue
            result[key_text] = _scrub(item)
        return result
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _bounded_float(value: Any, *, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    return max(0.0, min(1.0, result))


def _to_uuid(value: Any) -> uuid.UUID | None:
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "."


def _now() -> datetime:
    return datetime.now(timezone.utc)
