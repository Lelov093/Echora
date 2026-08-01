"""Realtime compatibility realtime memory buffer service."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import (
    CompanionPrivateRealtimeBuffer,
    CoPresenceSessionBuffer,
    MemoryGateTrace,
    RealtimeCoPresenceSession,
    RealtimeMemoryBuffer,
    RealtimeMemoryBufferItem,
    RealtimeMemoryExpiryEvent,
    RealtimeTraceSession,
    SharedSceneBuffer,
    User,
)
from app.services.realtime_copresence_service import get_session

BUFFER_SCOPES = {"companion_private", "co_presence_session", "shared_scene"}
SOURCE_TYPES = {"voice_turn", "transcript", "multimodal_context", "session_event", "channel_event", "manual_note"}


def classify_buffer_scope(payload: dict[str, Any], realtime_session: RealtimeCoPresenceSession | None = None) -> str:
    requested = payload.get("buffer_scope")
    if requested in BUFFER_SCOPES:
        return requested
    if payload.get("owner_companion_id"):
        return "companion_private"
    if payload.get("shared_scene_id") or (realtime_session and realtime_session.shared_scene_id):
        return "shared_scene"
    return "co_presence_session"


def create_buffer(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        user = s.get(User, user_id)
        realtime_session = s.get(RealtimeCoPresenceSession, _to_uuid(payload.get("realtime_session_id")))
        if user is None or realtime_session is None or realtime_session.user_id != user_id:
            return None
        scope = classify_buffer_scope(payload, realtime_session)
        owner_companion_id = _to_uuid(payload.get("owner_companion_id")) or realtime_session.active_companion_id
        shared_scene_id = _to_uuid(payload.get("shared_scene_id")) or realtime_session.shared_scene_id
        if scope == "companion_private" and owner_companion_id is None:
            return None
        if scope == "shared_scene" and shared_scene_id is None:
            scope = "co_presence_session"
        expires_at = _now() + timedelta(minutes=int(payload.get("ttl_minutes") or 120))
        buffer = RealtimeMemoryBuffer(
            user_id=user_id,
            realtime_session_id=realtime_session.id,
            co_presence_session_id=realtime_session.co_presence_session_id,
            shared_scene_id=shared_scene_id,
            owner_companion_id=owner_companion_id if scope == "companion_private" else None,
            buffer_scope=scope,
            buffer_status="active",
            default_memory_action="candidate_review",
            retention_policy="ephemeral",
            review_required=True,
            auto_write_private_memory=False,
            auto_write_shared_memory=False,
            buffer_summary=payload.get("buffer_summary") or "Realtime memory buffer",
            policy_snapshot_json={
                "buffer_is_long_term_memory": False,
                "auto_write_private_memory": False,
                "auto_write_shared_memory": False,
            },
            expires_at=expires_at,
            metadata_={"implementation_origin": "realtime_memory"},
        )
        s.add(buffer)
        s.flush()
        if scope == "companion_private":
            s.add(
                CompanionPrivateRealtimeBuffer(
                    user_id=user_id,
                    buffer_id=buffer.id,
                    companion_id=owner_companion_id,
                    private_memory_sync_policy="review_required",
                    auto_write_private_memory=False,
                    review_required=True,
                    policy_json={"private_memory_write": "review_required"},
                    metadata_={"implementation_origin": "realtime_memory"},
                )
            )
        elif scope == "co_presence_session" and realtime_session.co_presence_session_id:
            s.add(
                CoPresenceSessionBuffer(
                    user_id=user_id,
                    buffer_id=buffer.id,
                    co_presence_session_id=realtime_session.co_presence_session_id,
                    shared_candidate_policy="review_required",
                    review_required=True,
                    policy_json={"shared_candidate": "review_required"},
                    metadata_={"implementation_origin": "realtime_memory"},
                )
            )
        elif scope == "shared_scene" and shared_scene_id:
            s.add(
                SharedSceneBuffer(
                    user_id=user_id,
                    buffer_id=buffer.id,
                    shared_scene_id=shared_scene_id,
                    shared_candidate_policy="review_required",
                    review_required=True,
                    policy_json={"shared_scene_candidate": "review_required"},
                    metadata_={"implementation_origin": "realtime_memory"},
                )
            )
        s.commit()
        return get_buffer_bundle(buffer.id)


def get_buffer_bundle(buffer_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        buffer = s.get(RealtimeMemoryBuffer, buffer_id)
        if buffer is None:
            return None
        items = list(
            s.execute(
                select(RealtimeMemoryBufferItem)
                .where(RealtimeMemoryBufferItem.buffer_id == buffer.id)
                .order_by(RealtimeMemoryBufferItem.created_at.asc())
            ).scalars().all()
        )
        expiries = list(
            s.execute(
                select(RealtimeMemoryExpiryEvent)
                .where(RealtimeMemoryExpiryEvent.buffer_id == buffer.id)
                .order_by(RealtimeMemoryExpiryEvent.created_at.asc())
            ).scalars().all()
        )
        return {
            **_buffer_to_dict(buffer),
            "items": [_item_to_dict(item) for item in items],
            "expiry_events": [_expiry_to_dict(item) for item in expiries],
        }


def append_buffer_item(buffer_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        buffer = s.get(RealtimeMemoryBuffer, buffer_id)
        if buffer is None:
            return None
        source_type = payload.get("source_type") if payload.get("source_type") in SOURCE_TYPES else "manual_note"
        item = RealtimeMemoryBufferItem(
            user_id=buffer.user_id,
            buffer_id=buffer.id,
            realtime_session_id=buffer.realtime_session_id,
            source_type=source_type,
            source_voice_turn_id=_to_uuid(payload.get("source_voice_turn_id")),
            source_context_event_id=_to_uuid(payload.get("source_context_event_id")),
            source_session_event_id=_to_uuid(payload.get("source_session_event_id")),
            source_channel_event_id=_to_uuid(payload.get("source_channel_event_id")),
            item_status="active",
            retention_policy="ephemeral",
            content_summary=payload.get("content_summary") or "",
            raw_content_ref=None,
            can_generate_salient_moment=True,
            can_write_long_term_memory=False,
            payload_json={
                "raw_content_ref_blocked": bool(payload.get("raw_content_ref")),
                "memory_write": "review_required",
                **(payload.get("payload_json") or {}),
            },
            expires_at=buffer.expires_at,
            metadata_={"implementation_origin": "realtime_memory"},
        )
        s.add(item)
        s.commit()
        s.refresh(item)
        return _item_to_dict(item)


def expire_buffer_items(buffer_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        buffer = s.get(RealtimeMemoryBuffer, buffer_id)
        if buffer is None:
            return None
        now = _now()
        items = list(
            s.execute(select(RealtimeMemoryBufferItem).where(RealtimeMemoryBufferItem.buffer_id == buffer.id)).scalars().all()
        )
        for item in items:
            item.item_status = "expired"
            item.raw_content_ref = None
            s.add(
                RealtimeMemoryExpiryEvent(
                    user_id=buffer.user_id,
                    buffer_id=buffer.id,
                    buffer_item_id=item.id,
                    expiry_status="completed",
                    scheduled_for=item.expires_at,
                    expired_at=now,
                    raw_data_deleted=True,
                    expiry_payload_json={"expired_by": "realtime_memory_service"},
                    metadata_={"implementation_origin": "realtime_memory"},
                )
            )
        if buffer.expires_at and buffer.expires_at <= now:
            buffer.buffer_status = "expired"
        s.commit()
        return get_buffer_bundle(buffer.id)


def write_memory_gate_trace(buffer_id: uuid.UUID, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    with get_session() as s:
        buffer = s.get(RealtimeMemoryBuffer, buffer_id)
        if buffer is None or buffer.realtime_session_id is None:
            return None
        trace = s.execute(
            select(RealtimeTraceSession)
            .where(RealtimeTraceSession.realtime_session_id == buffer.realtime_session_id)
            .order_by(RealtimeTraceSession.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()
        if trace is None:
            trace = RealtimeTraceSession(
                user_id=buffer.user_id,
                realtime_session_id=buffer.realtime_session_id,
                co_presence_session_id=buffer.co_presence_session_id,
                trace_status="recording",
                trace_level="key_events",
                raw_capture_policy="disabled",
                raw_audio_storage_allowed=False,
                raw_screen_storage_allowed=False,
                raw_video_storage_allowed=False,
                redaction_required=True,
                retention_policy="review_summary_only",
                trace_summary="Memory gate trace for realtime buffer",
                policy_snapshot_json={"raw_capture": "disabled"},
                started_at=_now(),
                metadata_={"implementation_origin": "realtime_memory"},
            )
            s.add(trace)
            s.flush()
        gate = MemoryGateTrace(
            user_id=buffer.user_id,
            realtime_trace_session_id=trace.id,
            memory_buffer_id=buffer.id,
            gate_status="review_required",
            auto_write_blocked=True,
            gate_summary=payload.get("gate_summary") or "Long-term memory write blocked pending review",
            gate_payload_json={"auto_write_blocked": True, "implementation_origin": "realtime_memory"},
            metadata_={"implementation_origin": "realtime_memory"},
        )
        s.add(gate)
        s.commit()
        s.refresh(gate)
        return {
            "id": str(gate.id),
            "realtime_trace_session_id": str(gate.realtime_trace_session_id),
            "memory_buffer_id": str(gate.memory_buffer_id),
            "gate_status": gate.gate_status,
            "auto_write_blocked": gate.auto_write_blocked,
            "gate_summary": gate.gate_summary,
            "gate_payload_json": gate.gate_payload_json or {},
        }


def _buffer_to_dict(buffer: RealtimeMemoryBuffer) -> dict[str, Any]:
    return {
        "id": str(buffer.id),
        "user_id": str(buffer.user_id),
        "realtime_session_id": str(buffer.realtime_session_id) if buffer.realtime_session_id else None,
        "co_presence_session_id": str(buffer.co_presence_session_id) if buffer.co_presence_session_id else None,
        "shared_scene_id": str(buffer.shared_scene_id) if buffer.shared_scene_id else None,
        "owner_companion_id": str(buffer.owner_companion_id) if buffer.owner_companion_id else None,
        "buffer_scope": buffer.buffer_scope,
        "buffer_status": buffer.buffer_status,
        "default_memory_action": buffer.default_memory_action,
        "retention_policy": buffer.retention_policy,
        "review_required": buffer.review_required,
        "auto_write_private_memory": buffer.auto_write_private_memory,
        "auto_write_shared_memory": buffer.auto_write_shared_memory,
        "buffer_summary": buffer.buffer_summary,
        "policy_snapshot_json": buffer.policy_snapshot_json or {},
        "expires_at": buffer.expires_at.isoformat() if buffer.expires_at else None,
    }


def _item_to_dict(item: RealtimeMemoryBufferItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "buffer_id": str(item.buffer_id),
        "realtime_session_id": str(item.realtime_session_id) if item.realtime_session_id else None,
        "source_type": item.source_type,
        "item_status": item.item_status,
        "retention_policy": item.retention_policy,
        "content_summary": item.content_summary,
        "raw_content_ref": item.raw_content_ref,
        "can_generate_salient_moment": item.can_generate_salient_moment,
        "can_write_long_term_memory": item.can_write_long_term_memory,
        "payload_json": item.payload_json or {},
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
    }


def _expiry_to_dict(item: RealtimeMemoryExpiryEvent) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "buffer_id": str(item.buffer_id) if item.buffer_id else None,
        "buffer_item_id": str(item.buffer_item_id) if item.buffer_item_id else None,
        "salient_moment_id": str(item.salient_moment_id) if item.salient_moment_id else None,
        "expiry_status": item.expiry_status,
        "scheduled_for": item.scheduled_for.isoformat() if item.scheduled_for else None,
        "expired_at": item.expired_at.isoformat() if item.expired_at else None,
        "raw_data_deleted": item.raw_data_deleted,
        "expiry_payload_json": item.expiry_payload_json or {},
    }


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)
