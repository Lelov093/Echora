"""Channel Gateway channel trace, audit, and revoke service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    ChannelAuditLog,
    ChannelBinding,
    ChannelBindingStatusEvent,
    ChannelCheckinSetting,
    ChannelEphemeralBuffer,
    ChannelEphemeralBufferItem,
    ChannelMemoryCandidate,
    ChannelPresencePolicy,
    ChannelRevokeEvent,
    ChannelTraceEvent,
    PresenceChannelBinding,
)

_engine = None
_SENSITIVE_KEY_PARTS = ("token", "secret", "password", "api_key", "authorization", "credential", "raw", "private")


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_trace_events(
    *,
    channel_binding_id: uuid.UUID | None = None,
    event_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelTraceEvent)
        if channel_binding_id is not None:
            stmt = stmt.where(ChannelTraceEvent.channel_binding_id == channel_binding_id)
        if event_type:
            stmt = stmt.where(ChannelTraceEvent.trace_event_type == event_type)
        if status:
            stmt = stmt.where(ChannelTraceEvent.trace_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelTraceEvent.occurred_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_trace_to_dict(item) for item in items], "total": total}


def list_audit_logs(
    *,
    channel_binding_id: uuid.UUID | None = None,
    audit_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelAuditLog)
        if channel_binding_id is not None:
            stmt = stmt.where(ChannelAuditLog.channel_binding_id == channel_binding_id)
        if audit_type:
            stmt = stmt.where(ChannelAuditLog.audit_log_type == audit_type)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelAuditLog.occurred_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_audit_to_dict(item) for item in items], "total": total}


def list_revoke_events(
    *,
    channel_binding_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelRevokeEvent)
        if channel_binding_id is not None:
            stmt = stmt.where(ChannelRevokeEvent.channel_binding_id == channel_binding_id)
        if status:
            stmt = stmt.where(ChannelRevokeEvent.revoke_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelRevokeEvent.applied_at.desc(), ChannelRevokeEvent.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_revoke_to_dict(item) for item in items], "total": total}


def apply_revoke(channel_binding_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        binding = s.get(ChannelBinding, channel_binding_id)
        if binding is None or binding.presence_channel_binding_id is None:
            return None
        if binding.binding_status == "revoked" or binding.revoked_at is not None:
            latest_revoke = s.execute(
                select(ChannelRevokeEvent)
                .where(
                    ChannelRevokeEvent.channel_binding_id == binding.id,
                    ChannelRevokeEvent.revoke_status == "applied",
                )
                .order_by(ChannelRevokeEvent.applied_at.desc(), ChannelRevokeEvent.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            latest_trace = s.execute(
                select(ChannelTraceEvent)
                .where(
                    ChannelTraceEvent.channel_binding_id == binding.id,
                    ChannelTraceEvent.trace_event_type == "revoke",
                )
                .order_by(ChannelTraceEvent.occurred_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            latest_audit = s.execute(
                select(ChannelAuditLog)
                .where(
                    ChannelAuditLog.channel_binding_id == binding.id,
                    ChannelAuditLog.audit_log_type == "revoked",
                )
                .order_by(ChannelAuditLog.occurred_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            policy_count = s.execute(
                select(func.count()).select_from(ChannelPresencePolicy).where(
                    ChannelPresencePolicy.channel_binding_id == binding.id,
                    ChannelPresencePolicy.policy_status == "revoked",
                )
            ).scalar() or 0
            setting_count = s.execute(
                select(func.count()).select_from(ChannelCheckinSetting).join(
                    ChannelPresencePolicy,
                    ChannelPresencePolicy.id == ChannelCheckinSetting.channel_presence_policy_id,
                ).where(
                    ChannelPresencePolicy.channel_binding_id == binding.id,
                    ChannelCheckinSetting.enabled.is_(False),
                )
            ).scalar() or 0
            buffer_count = s.execute(
                select(func.count()).select_from(ChannelEphemeralBuffer).where(
                    ChannelEphemeralBuffer.channel_binding_id == binding.id,
                    ChannelEphemeralBuffer.buffer_status == "cleared",
                )
            ).scalar() or 0
            buffer_item_count = s.execute(
                select(func.count()).select_from(ChannelEphemeralBufferItem).join(
                    ChannelEphemeralBuffer,
                    ChannelEphemeralBuffer.id == ChannelEphemeralBufferItem.channel_ephemeral_buffer_id,
                ).where(
                    ChannelEphemeralBuffer.channel_binding_id == binding.id,
                    ChannelEphemeralBufferItem.buffer_item_status == "cleared",
                )
            ).scalar() or 0
            rejected_candidate_count = s.execute(
                select(func.count()).select_from(ChannelMemoryCandidate).where(
                    ChannelMemoryCandidate.channel_binding_id == binding.id,
                    ChannelMemoryCandidate.candidate_status == "rejected",
                )
            ).scalar() or 0
            return {
                "revoke_event": _revoke_to_dict(latest_revoke) if latest_revoke else None,
                "trace_event": _trace_to_dict(latest_trace) if latest_trace else None,
                "audit_log": _audit_to_dict(latest_audit) if latest_audit else None,
                "effects": {
                    "binding_status": binding.binding_status,
                    "can_receive_inbound": binding.can_receive_inbound,
                    "can_send_outbound": binding.can_send_outbound,
                    "checkin_enabled": binding.checkin_enabled,
                    "presence_policies_revoked": policy_count,
                    "checkin_settings_disabled": setting_count,
                    "ephemeral_buffers_cleared": buffer_count,
                    "ephemeral_buffer_items_cleared": buffer_item_count,
                    "memory_candidates_rejected": rejected_candidate_count,
                    "history_audit_retained": True,
                },
                "idempotent_replay": True,
            }

        previous_status = binding.binding_status
        now = _now()
        binding.binding_status = "revoked"
        binding.can_receive_inbound = False
        binding.can_send_outbound = False
        binding.checkin_enabled = False
        binding.revoked_at = now
        binding.updated_at = now

        presence_binding = s.get(PresenceChannelBinding, binding.presence_channel_binding_id)
        if presence_binding is not None:
            presence_binding.binding_status = "revoked"
            presence_binding.can_receive_inbound = False
            presence_binding.can_send_outbound = False
            presence_binding.updated_at = now

        policy_count, setting_count = _revoke_presence_policies(s, binding.id, now)
        buffer_count, buffer_item_count = _clear_ephemeral_buffers(s, binding.id, now)
        candidate_count = _disable_memory_candidates(s, binding.id, now)

        revoke_payload = {
            "reason": _truncate(str(payload.get("reason") or "Channel Gateway channel revoke"), 500),
            "stops_inbound": True,
            "stops_outbound": True,
            "stops_checkins": True,
            "clears_ephemeral_buffer": True,
            "disables_memory_candidates": True,
            "presence_policies_revoked": policy_count,
            "checkin_settings_disabled": setting_count,
            "ephemeral_buffers_cleared": buffer_count,
            "ephemeral_buffer_items_cleared": buffer_item_count,
            "memory_candidates_rejected": candidate_count,
            **_safe_json(payload.get("safe_revoke_payload_json")),
        }
        revoke_event = ChannelRevokeEvent(
            user_id=binding.user_id,
            presence_channel_binding_id=binding.presence_channel_binding_id,
            channel_binding_id=binding.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            trace_run_id=_to_uuid(payload.get("trace_run_id")),
            revoke_status="applied",
            revoke_scope="all",
            revokes_credentials_ref=True,
            stops_inbound=True,
            stops_outbound=True,
            stops_checkins=True,
            clears_ephemeral_buffer=True,
            disables_memory_candidates=True,
            audit_required=True,
            revoke_reason=revoke_payload["reason"],
            revoke_payload_json=revoke_payload,
            applied_at=now,
            metadata_={"implementation_origin": "channel_audit", "service": "trace_audit_revoke"},
        )
        s.add(revoke_event)

        status = ChannelBindingStatusEvent(
            user_id=binding.user_id,
            channel_binding_id=binding.id,
            status_event="revoked",
            from_status=previous_status,
            to_status="revoked",
            status_reason=revoke_payload["reason"],
            safe_status_payload_json={"reason": revoke_payload["reason"], "implementation_origin": "channel_audit"},
            occurred_at=now,
            metadata_={"implementation_origin": "channel_audit"},
        )
        s.add(status)
        trace = ChannelTraceEvent(
            user_id=binding.user_id,
            companion_id=binding.companion_id,
            channel_binding_id=binding.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            trace_run_id=_to_uuid(payload.get("trace_run_id")),
            trace_event_type="revoke",
            trace_status="recorded",
            trace_summary="Channel binding revoked; future inbound/outbound/check-in/candidate generation disabled",
            safe_trace_payload_json={**revoke_payload, "raw_payload_storage_allowed": False},
            occurred_at=now,
            metadata_={"implementation_origin": "channel_audit"},
        )
        s.add(trace)
        s.flush()
        audit = ChannelAuditLog(
            user_id=binding.user_id,
            channel_binding_id=binding.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            channel_trace_event_id=trace.id,
            audit_log_type="revoked",
            audit_summary="Channel revoke applied with audit trail",
            safe_audit_payload_json={**revoke_payload, "raw_payload_storage_allowed": False},
            occurred_at=now,
            metadata_={"implementation_origin": "channel_audit"},
        )
        s.add(audit)
        s.commit()
        s.refresh(revoke_event)
        s.refresh(trace)
        s.refresh(audit)
        return {
            "revoke_event": _revoke_to_dict(revoke_event),
            "trace_event": _trace_to_dict(trace),
            "audit_log": _audit_to_dict(audit),
            "effects": {
                "binding_status": binding.binding_status,
                "can_receive_inbound": binding.can_receive_inbound,
                "can_send_outbound": binding.can_send_outbound,
                "checkin_enabled": binding.checkin_enabled,
                "presence_policies_revoked": policy_count,
                "checkin_settings_disabled": setting_count,
                "ephemeral_buffers_cleared": buffer_count,
                "ephemeral_buffer_items_cleared": buffer_item_count,
                "memory_candidates_rejected": candidate_count,
                "history_audit_retained": True,
            },
            "idempotent_replay": False,
        }


def _revoke_presence_policies(s: Session, binding_id: uuid.UUID, now: datetime) -> tuple[int, int]:
    policies = list(s.execute(select(ChannelPresencePolicy).where(ChannelPresencePolicy.channel_binding_id == binding_id)).scalars().all())
    setting_count = 0
    for policy in policies:
        policy.policy_status = "revoked"
        policy.low_frequency_checkin_enabled = False
        policy.outbound_disabled = True
        policy.remaining_presence_budget = 0
        policy.updated_at = now
        settings = list(
            s.execute(select(ChannelCheckinSetting).where(ChannelCheckinSetting.channel_presence_policy_id == policy.id)).scalars().all()
        )
        for setting in settings:
            setting.enabled = False
            setting.updated_at = now
            setting_count += 1
    return len(policies), setting_count


def _clear_ephemeral_buffers(s: Session, binding_id: uuid.UUID, now: datetime) -> tuple[int, int]:
    buffers = list(s.execute(select(ChannelEphemeralBuffer).where(ChannelEphemeralBuffer.channel_binding_id == binding_id)).scalars().all())
    item_count = 0
    for buffer in buffers:
        buffer.buffer_status = "cleared"
        buffer.memory_candidate_generation_enabled = False
        buffer.safe_buffer_summary = "Cleared by channel revoke"
        buffer.updated_at = now
        items = list(
            s.execute(select(ChannelEphemeralBufferItem).where(ChannelEphemeralBufferItem.channel_ephemeral_buffer_id == buffer.id)).scalars().all()
        )
        for item in items:
            item.buffer_item_status = "cleared"
            item.long_term_memory_written = False
            item.updated_at = now
            item_count += 1
    return len(buffers), item_count


def _disable_memory_candidates(s: Session, binding_id: uuid.UUID, now: datetime) -> int:
    candidates = list(
        s.execute(
            select(ChannelMemoryCandidate).where(
                ChannelMemoryCandidate.channel_binding_id == binding_id,
                ChannelMemoryCandidate.candidate_status == "pending_review",
            )
        ).scalars().all()
    )
    for candidate in candidates:
        candidate.candidate_status = "rejected"
        candidate.auto_commit_allowed = False
        candidate.raw_payload_storage_allowed = False
        candidate.updated_at = now
    return len(candidates)


def _trace_to_dict(row: ChannelTraceEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "companion_id": str(row.companion_id) if row.companion_id else None,
        "channel_binding_id": str(row.channel_binding_id) if row.channel_binding_id else None,
        "provider_id": str(row.provider_id) if row.provider_id else None,
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "trace_event_type": row.trace_event_type,
        "trace_status": row.trace_status,
        "trace_summary": row.trace_summary,
        "safe_trace_payload_json": row.safe_trace_payload_json or {},
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _audit_to_dict(row: ChannelAuditLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "channel_binding_id": str(row.channel_binding_id) if row.channel_binding_id else None,
        "provider_id": str(row.provider_id) if row.provider_id else None,
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "channel_trace_event_id": str(row.channel_trace_event_id) if row.channel_trace_event_id else None,
        "audit_log_type": row.audit_log_type,
        "audit_summary": row.audit_summary,
        "safe_audit_payload_json": row.safe_audit_payload_json or {},
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _revoke_to_dict(row: ChannelRevokeEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "presence_channel_binding_id": str(row.presence_channel_binding_id),
        "channel_binding_id": str(row.channel_binding_id) if row.channel_binding_id else None,
        "provider_id": str(row.provider_id) if row.provider_id else None,
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "trace_run_id": str(row.trace_run_id) if row.trace_run_id else None,
        "revoke_status": row.revoke_status,
        "revoke_scope": row.revoke_scope,
        "stops_inbound": row.stops_inbound,
        "stops_outbound": row.stops_outbound,
        "stops_checkins": row.stops_checkins,
        "clears_ephemeral_buffer": row.clears_ephemeral_buffer,
        "disables_memory_candidates": row.disables_memory_candidates,
        "audit_required": row.audit_required,
        "revoke_reason": row.revoke_reason,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
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
