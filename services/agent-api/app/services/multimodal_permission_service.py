"""Realtime compatibility multimodal context permission service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text

from app.db.models import (
    ContextRetentionPolicy,
    DeviceContextEvent,
    EphemeralContextExpiryEvent,
    FileContextRealtimeEvent,
    ImageContextEvent,
    MultimodalContextEvent,
    ParticipantContextPermission,
    RealtimeCoPresenceParticipant,
    RealtimeCoPresenceSession,
    ScreenContextEvent,
    User,
)
from app.services import realtime_context_retention_service
from app.services.realtime_copresence_service import get_session

CONTEXT_TYPES = {"image", "screen", "file", "device"}
CONTEXT_SOURCES = {"user_upload", "user_paste", "manual_summary", "session_event", "test"}
PERMISSION_SOURCES = {"session_default", "user_grant", "user_override", "policy", "review_decision"}


def block_raw_data_persistence_by_default(payload: dict[str, Any]) -> dict[str, Any]:
    retention = payload.get("raw_data_retention_policy") or "ephemeral"
    explicit_authorization = bool(payload.get("explicit_retention_authorized"))
    if retention != "explicit_retention" or not explicit_authorization:
        return {
            **payload,
            "raw_data_ref": None,
            "raw_data_storage_allowed": False,
            "raw_data_retention_policy": "ephemeral",
        }
    return {**payload, "raw_data_storage_allowed": True}


def create_context_event(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    sanitized = block_raw_data_persistence_by_default(payload)
    with get_session() as s:
        user = s.get(User, user_id)
        realtime_session = s.get(RealtimeCoPresenceSession, _to_uuid(sanitized.get("realtime_session_id")))
        if user is None or realtime_session is None or realtime_session.user_id != user_id:
            return None

        context_type = sanitized.get("context_type") if sanitized.get("context_type") in CONTEXT_TYPES else "image"
        context_source = sanitized.get("context_source") if sanitized.get("context_source") in CONTEXT_SOURCES else "manual_summary"
        ttl_minutes = int(sanitized.get("ttl_minutes") or 60)
        policy = realtime_context_retention_service.build_ephemeral_policy(ttl_minutes=ttl_minutes)
        now = _now()
        context = MultimodalContextEvent(
            user_id=user_id,
            realtime_session_id=realtime_session.id,
            co_presence_session_id=realtime_session.co_presence_session_id,
            shared_scene_id=realtime_session.shared_scene_id,
            source_participant_id=_to_uuid(sanitized.get("source_participant_id")),
            context_type=context_type,
            context_source=context_source,
            context_status="active",
            raw_data_ref=sanitized.get("raw_data_ref"),
            raw_data_retention_policy=policy["retention_policy"],
            raw_data_storage_allowed=policy["raw_data_storage_allowed"],
            retention_policy_json=policy["policy_json"],
            permission_snapshot_json=sanitized.get("permission_snapshot_json") or {},
            visibility_summary_json={},
            redaction_status="not_required",
            expires_at=policy["expires_at"],
            occurred_at=now,
            metadata_={"implementation_origin": "realtime_permissions", "summary": sanitized.get("summary")},
        )
        s.add(context)
        s.flush()
        _add_context_detail(s, context, sanitized)
        retention_policy = ContextRetentionPolicy(
            user_id=user_id,
            context_event_id=context.id,
            realtime_session_id=realtime_session.id,
            policy_scope="context_event",
            retention_policy="ephemeral",
            redaction_status="not_required",
            raw_data_storage_allowed=False,
            expires_at=context.expires_at,
            policy_json=policy["policy_json"],
            metadata_={"implementation_origin": "realtime_permissions"},
        )
        s.add(retention_policy)
        s.flush()
        s.add(
            EphemeralContextExpiryEvent(
                user_id=user_id,
                context_event_id=context.id,
                retention_policy_id=retention_policy.id,
                expiry_status="scheduled",
                scheduled_for=context.expires_at,
                raw_data_deleted=False,
                redaction_applied=False,
                expiry_payload_json={"scheduled_by": "realtime_permission_service"},
                metadata_={"implementation_origin": "realtime_permissions"},
            )
        )
        for participant_id in sanitized.get("participant_ids") or []:
            participant = s.get(RealtimeCoPresenceParticipant, _to_uuid(participant_id))
            if participant and participant.realtime_session_id == realtime_session.id:
                _upsert_permission(s, context, participant, sanitized.get("permission") or {})
        _refresh_visibility_summary(s, context)
        s.commit()
        return get_context_event_bundle(context.id)


def get_context_event_bundle(context_event_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        context = s.get(MultimodalContextEvent, context_event_id)
        if context is None:
            return None
        permissions = list(
            s.execute(
                select(ParticipantContextPermission)
                .where(ParticipantContextPermission.context_event_id == context.id)
                .order_by(ParticipantContextPermission.created_at.asc())
            ).scalars().all()
        )
        return {
            **_context_to_dict(context),
            "detail": _detail_to_dict(s, context),
            "permissions": [_permission_to_dict(item) for item in permissions],
            "retention": realtime_context_retention_service.check_context_retention(context.id),
        }


def record_permission_event(context_event_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        context = s.get(MultimodalContextEvent, context_event_id)
        participant = s.get(RealtimeCoPresenceParticipant, _to_uuid(payload.get("participant_id")))
        if context is None or participant is None or participant.realtime_session_id != context.realtime_session_id:
            return None
        permission = _upsert_permission(s, context, participant, payload)
        _refresh_visibility_summary(s, context)
        s.commit()
        s.refresh(permission)
        return _permission_to_dict(permission)


def check_participant_visibility(context_event_id: uuid.UUID, participant_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        context = s.get(MultimodalContextEvent, context_event_id)
        participant = s.get(RealtimeCoPresenceParticipant, participant_id)
        if context is None or participant is None:
            return None
        permission = s.execute(
            select(ParticipantContextPermission).where(
                ParticipantContextPermission.context_event_id == context.id,
                ParticipantContextPermission.participant_id == participant.id,
            )
        ).scalar_one_or_none()
        if permission is None:
            return {
                "context_event_id": str(context.id),
                "participant_id": str(participant.id),
                "can_see": False,
                "can_use": False,
                "can_remember": False,
                "can_view_raw_data": False,
                "review_required": True,
                "reason": "no explicit visibility grant",
            }
        return _permission_to_dict(permission)


def check_context_retention(context_event_id: uuid.UUID) -> dict[str, Any] | None:
    return realtime_context_retention_service.check_context_retention(context_event_id)


def expire_ephemeral_context(context_event_id: uuid.UUID) -> dict[str, Any] | None:
    return realtime_context_retention_service.expire_ephemeral_context(context_event_id)


def _add_context_detail(s, context: MultimodalContextEvent, payload: dict[str, Any]) -> None:
    if context.context_type == "image":
        s.execute(
            text(
                """
                INSERT INTO image_context_events
                    (user_id, context_event_id, image_context_kind, image_count, image_summary)
                VALUES
                    (:user_id, :context_event_id, :image_context_kind, :image_count, :image_summary)
                """
            ),
            {
                "user_id": context.user_id,
                "context_event_id": context.id,
                "image_context_kind": payload.get("image_context_kind") or "image_summary",
                "image_count": max(1, min(int(payload.get("image_count") or 1), 64)),
                "image_summary": payload.get("summary") or payload.get("image_summary"),
            },
        )
    elif context.context_type == "screen":
        s.execute(
            text(
                """
                INSERT INTO screen_context_events
                    (user_id, context_event_id, screen_context_kind, window_title, screen_summary, requires_manual_user_action)
                VALUES
                    (:user_id, :context_event_id, :screen_context_kind, :window_title, :screen_summary, true)
                """
            ),
            {
                "user_id": context.user_id,
                "context_event_id": context.id,
                "screen_context_kind": payload.get("screen_context_kind") or "manual_summary",
                "window_title": payload.get("window_title"),
                "screen_summary": payload.get("summary") or payload.get("screen_summary"),
            },
        )
    elif context.context_type == "file":
        s.execute(
            text(
                """
                INSERT INTO file_context_realtime_events
                    (user_id, context_event_id, file_context_kind, file_name, file_mime_type, excerpt_text, file_summary)
                VALUES
                    (:user_id, :context_event_id, :file_context_kind, :file_name, :file_mime_type, :excerpt_text, :file_summary)
                """
            ),
            {
                "user_id": context.user_id,
                "context_event_id": context.id,
                "file_context_kind": payload.get("file_context_kind") or "file_summary",
                "file_name": payload.get("file_name"),
                "file_mime_type": payload.get("file_mime_type"),
                "excerpt_text": payload.get("excerpt_text"),
                "file_summary": payload.get("summary") or payload.get("file_summary"),
            },
        )
    elif context.context_type == "device":
        s.execute(
            text(
                """
                INSERT INTO device_context_events
                    (user_id, context_event_id, device_event_kind, device_label, event_summary, requires_manual_user_action)
                VALUES
                    (:user_id, :context_event_id, :device_event_kind, :device_label, :event_summary, true)
                """
            ),
            {
                "user_id": context.user_id,
                "context_event_id": context.id,
                "device_event_kind": payload.get("device_event_kind") or "manual_device_note",
                "device_label": payload.get("device_label"),
                "event_summary": payload.get("summary") or payload.get("event_summary"),
            },
        )


def _upsert_permission(
    s,
    context: MultimodalContextEvent,
    participant: RealtimeCoPresenceParticipant,
    payload: dict[str, Any],
) -> ParticipantContextPermission:
    permission = s.execute(
        select(ParticipantContextPermission).where(
            ParticipantContextPermission.context_event_id == context.id,
            ParticipantContextPermission.participant_id == participant.id,
        )
    ).scalar_one_or_none()
    if permission is None:
        permission = ParticipantContextPermission(
            user_id=context.user_id,
            context_event_id=context.id,
            realtime_session_id=context.realtime_session_id,
            participant_id=participant.id,
            metadata_={"implementation_origin": "realtime_permissions"},
        )
        s.add(permission)
    can_see = bool(payload.get("can_see", True))
    can_view_raw_data = bool(payload.get("can_view_raw_data", False)) and can_see and context.raw_data_storage_allowed
    can_remember = bool(payload.get("can_remember", False))
    permission.permission_source = payload.get("permission_source") if payload.get("permission_source") in PERMISSION_SOURCES else "user_grant"
    permission.can_see = can_see
    permission.can_use = bool(payload.get("can_use", can_see))
    permission.can_remember = can_remember
    permission.can_view_raw_data = can_view_raw_data
    permission.review_required = True if can_remember or payload.get("review_required", True) else False
    permission.expires_at = context.expires_at
    permission.permission_snapshot_json = {
        "context_type": context.context_type,
        "raw_data_storage_allowed": context.raw_data_storage_allowed,
    }
    permission.boundary_policy_json = {
        "can_remember_requires_review": True,
        "raw_data_view_requires_storage_and_visibility": True,
    }
    s.flush()
    return permission


def _refresh_visibility_summary(s, context: MultimodalContextEvent) -> None:
    permissions = list(
        s.execute(
            select(ParticipantContextPermission).where(ParticipantContextPermission.context_event_id == context.id)
        ).scalars().all()
    )
    context.visibility_summary_json = {
        "permission_count": len(permissions),
        "visible_count": len([item for item in permissions if item.can_see]),
        "remember_count": len([item for item in permissions if item.can_remember]),
        "raw_view_count": len([item for item in permissions if item.can_view_raw_data]),
    }


def _detail_to_dict(s, context: MultimodalContextEvent) -> dict[str, Any] | None:
    sql_by_type = {
        "image": """
            SELECT id, context_event_id, image_context_kind, image_count, image_summary
            FROM image_context_events WHERE context_event_id = :context_event_id LIMIT 1
        """,
        "screen": """
            SELECT id, context_event_id, screen_context_kind, window_title, screen_summary, requires_manual_user_action
            FROM screen_context_events WHERE context_event_id = :context_event_id LIMIT 1
        """,
        "file": """
            SELECT id, context_event_id, file_context_kind, file_name, file_mime_type, excerpt_text, file_summary
            FROM file_context_realtime_events WHERE context_event_id = :context_event_id LIMIT 1
        """,
        "device": """
            SELECT id, context_event_id, device_event_kind, device_label, event_summary, requires_manual_user_action, device_payload_json
            FROM device_context_events WHERE context_event_id = :context_event_id LIMIT 1
        """,
    }
    sql = sql_by_type.get(context.context_type)
    if not sql:
        return None
    row = s.execute(text(sql), {"context_event_id": context.id}).mappings().first()
    if row is None:
        return None
    return {
        key: str(value) if key in {"id", "context_event_id"} else value
        for key, value in dict(row).items()
    } | {"context_type": context.context_type}


def _context_to_dict(context: MultimodalContextEvent) -> dict[str, Any]:
    return {
        "id": str(context.id),
        "user_id": str(context.user_id),
        "realtime_session_id": str(context.realtime_session_id) if context.realtime_session_id else None,
        "co_presence_session_id": str(context.co_presence_session_id) if context.co_presence_session_id else None,
        "shared_scene_id": str(context.shared_scene_id) if context.shared_scene_id else None,
        "source_participant_id": str(context.source_participant_id) if context.source_participant_id else None,
        "context_type": context.context_type,
        "context_source": context.context_source,
        "context_status": context.context_status,
        "raw_data_ref": context.raw_data_ref,
        "raw_data_retention_policy": context.raw_data_retention_policy,
        "raw_data_storage_allowed": context.raw_data_storage_allowed,
        "retention_policy_json": context.retention_policy_json or {},
        "permission_snapshot_json": context.permission_snapshot_json or {},
        "visibility_summary_json": context.visibility_summary_json or {},
        "redaction_status": context.redaction_status,
        "expires_at": context.expires_at.isoformat() if context.expires_at else None,
        "occurred_at": context.occurred_at.isoformat() if context.occurred_at else None,
    }


def _permission_to_dict(permission: ParticipantContextPermission) -> dict[str, Any]:
    return {
        "id": str(permission.id),
        "context_event_id": str(permission.context_event_id),
        "realtime_session_id": str(permission.realtime_session_id) if permission.realtime_session_id else None,
        "participant_id": str(permission.participant_id),
        "permission_source": permission.permission_source,
        "can_see": permission.can_see,
        "can_use": permission.can_use,
        "can_remember": permission.can_remember,
        "can_view_raw_data": permission.can_view_raw_data,
        "review_required": permission.review_required,
        "expires_at": permission.expires_at.isoformat() if permission.expires_at else None,
        "permission_snapshot_json": permission.permission_snapshot_json or {},
        "boundary_policy_json": permission.boundary_policy_json or {},
    }


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)
