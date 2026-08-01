"""Realtime compatibility realtime context retention service."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.models import ContextRetentionPolicy, EphemeralContextExpiryEvent, MultimodalContextEvent
from app.services.realtime_copresence_service import get_session


def default_expiry(minutes: int = 60) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=max(minutes, 1))


def build_ephemeral_policy(*, ttl_minutes: int = 60) -> dict[str, Any]:
    expires_at = default_expiry(ttl_minutes)
    return {
        "retention_policy": "ephemeral",
        "raw_data_storage_allowed": False,
        "expires_at": expires_at,
        "policy_json": {
            "ttl_minutes": ttl_minutes,
            "raw_data_persistence": "blocked_by_default",
            "requires_explicit_retention_for_storage": True,
        },
    }


def check_context_retention(context_event_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        context = s.get(MultimodalContextEvent, context_event_id)
        if context is None:
            return None
        policy = (
            s.query(ContextRetentionPolicy)
            .filter(ContextRetentionPolicy.context_event_id == context.id)
            .order_by(ContextRetentionPolicy.created_at.desc())
            .first()
        )
        expiry = (
            s.query(EphemeralContextExpiryEvent)
            .filter(EphemeralContextExpiryEvent.context_event_id == context.id)
            .order_by(EphemeralContextExpiryEvent.created_at.desc())
            .first()
        )
        return {
            "context_event_id": str(context.id),
            "retention_policy": context.raw_data_retention_policy,
            "raw_data_storage_allowed": context.raw_data_storage_allowed,
            "redaction_status": context.redaction_status,
            "expires_at": context.expires_at.isoformat() if context.expires_at else None,
            "policy": _policy_to_dict(policy) if policy else None,
            "expiry": _expiry_to_dict(expiry) if expiry else None,
        }


def expire_ephemeral_context(context_event_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        context = s.get(MultimodalContextEvent, context_event_id)
        if context is None:
            return None
        now = datetime.now(timezone.utc)
        context.context_status = "expired"
        context.raw_data_ref = None
        context.raw_data_storage_allowed = False
        context.redaction_status = "redacted"
        policy = (
            s.query(ContextRetentionPolicy)
            .filter(ContextRetentionPolicy.context_event_id == context.id)
            .order_by(ContextRetentionPolicy.created_at.desc())
            .first()
        )
        expiry = (
            s.query(EphemeralContextExpiryEvent)
            .filter(EphemeralContextExpiryEvent.context_event_id == context.id)
            .order_by(EphemeralContextExpiryEvent.created_at.desc())
            .first()
        )
        if expiry is None:
            expiry = EphemeralContextExpiryEvent(
                user_id=context.user_id,
                context_event_id=context.id,
                retention_policy_id=policy.id if policy else None,
                scheduled_for=context.expires_at or now,
                metadata_={"implementation_origin": "realtime_permissions"},
            )
            s.add(expiry)
        expiry.expiry_status = "completed"
        expiry.expired_at = now
        expiry.raw_data_deleted = True
        expiry.redaction_applied = True
        expiry.expiry_payload_json = {
            "expired_by": "realtime_permission_service",
            "raw_data_ref_cleared": True,
        }
        s.commit()
        return check_context_retention(context.id)


def _policy_to_dict(policy: ContextRetentionPolicy) -> dict[str, Any]:
    return {
        "id": str(policy.id),
        "policy_scope": policy.policy_scope,
        "retention_policy": policy.retention_policy,
        "redaction_status": policy.redaction_status,
        "raw_data_storage_allowed": policy.raw_data_storage_allowed,
        "expires_at": policy.expires_at.isoformat() if policy.expires_at else None,
        "policy_json": policy.policy_json or {},
    }


def _expiry_to_dict(expiry: EphemeralContextExpiryEvent) -> dict[str, Any]:
    return {
        "id": str(expiry.id),
        "expiry_status": expiry.expiry_status,
        "scheduled_for": expiry.scheduled_for.isoformat() if expiry.scheduled_for else None,
        "expired_at": expiry.expired_at.isoformat() if expiry.expired_at else None,
        "raw_data_deleted": expiry.raw_data_deleted,
        "redaction_applied": expiry.redaction_applied,
        "expiry_payload_json": expiry.expiry_payload_json or {},
    }
