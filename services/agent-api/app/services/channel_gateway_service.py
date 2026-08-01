"""Channel Gateway channel gateway core service.

This layer manages provider-neutral channel resources only. It never resolves
external platform tokens and never returns token_secret_ref to API callers.
"""

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
    ChannelBotRegistry,
    ChannelProvider,
    ChannelRevokeEvent,
    ChannelTraceEvent,
    Companion,
    PresenceChannelBinding,
    User,
)
from app.schemas.channel_gateway import (
    ChannelBindingRead,
    ChannelBotRegistryRead,
    ChannelProviderRead,
    ChannelRevokeEventRead,
)

_engine = None
_SENSITIVE_KEY_PARTS = ("token", "secret", "password", "api_key", "authorization", "credential")


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_providers(
    *,
    provider_kind: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelProvider)
        if provider_kind:
            stmt = stmt.where(ChannelProvider.provider_kind == provider_kind)
        if status:
            stmt = stmt.where(ChannelProvider.provider_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelProvider.provider_kind.asc(), ChannelProvider.provider_key.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_provider_to_dict(item) for item in items], "total": total}


def get_provider(provider_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        provider = s.get(ChannelProvider, provider_id)
        return _provider_to_dict(provider) if provider else None


def get_provider_by_key(provider_key: str) -> dict[str, Any] | None:
    with get_session() as s:
        provider = s.execute(select(ChannelProvider).where(ChannelProvider.provider_key == provider_key)).scalar_one_or_none()
        return _provider_to_dict(provider) if provider else None


def list_bots(
    *,
    user_id: uuid.UUID | None = None,
    provider_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelBotRegistry)
        if user_id is not None:
            stmt = stmt.where(ChannelBotRegistry.user_id == user_id)
        if provider_id is not None:
            stmt = stmt.where(ChannelBotRegistry.provider_id == provider_id)
        if status:
            stmt = stmt.where(ChannelBotRegistry.bot_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelBotRegistry.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_bot_to_dict(item) for item in items], "total": total}


def register_bot(user_id: uuid.UUID | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    if _contains_plain_secret_field(payload):
        return None
    with get_session() as s:
        provider = s.get(ChannelProvider, _to_uuid(payload.get("provider_id")))
        if provider is None:
            return None
        if user_id is not None and s.get(User, user_id) is None:
            return None

        token_secret_ref = payload.get("token_secret_ref")
        if token_secret_ref and not _is_secret_reference(token_secret_ref):
            return None
        token_status = "configured" if token_secret_ref else "missing"
        bot = ChannelBotRegistry(
            user_id=user_id,
            provider_id=provider.id,
            bot_key=payload.get("bot_key") or f"{provider.provider_key}-{uuid.uuid4().hex[:8]}",
            bot_display_name=payload.get("bot_display_name") or provider.provider_display_name,
            bot_status=payload.get("bot_status") or ("ready" if token_secret_ref or not provider.requires_external_token else "draft"),
            token_status=token_status,
            token_secret_ref=token_secret_ref,
            stores_plaintext_token=False,
            external_application_id_hash=payload.get("external_application_id_hash"),
            external_bot_user_id_hash=payload.get("external_bot_user_id_hash"),
            safe_metadata_json=_safe_json(payload.get("safe_metadata_json")),
            metadata_={"implementation_origin": "channel_gateway", "service": "channel_gateway_core"},
        )
        s.add(bot)
        s.commit()
        s.refresh(bot)
        return _bot_to_dict(bot)


def list_bindings(
    *,
    user_id: uuid.UUID | None = None,
    companion_id: uuid.UUID | None = None,
    provider_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelBinding)
        if user_id is not None:
            stmt = stmt.where(ChannelBinding.user_id == user_id)
        if companion_id is not None:
            stmt = stmt.where(ChannelBinding.companion_id == companion_id)
        if provider_id is not None:
            stmt = stmt.where(ChannelBinding.provider_id == provider_id)
        if status:
            stmt = stmt.where(ChannelBinding.binding_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelBinding.updated_at.desc(), ChannelBinding.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_binding_to_dict(item) for item in items], "total": total}


def create_binding(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        user = s.get(User, user_id)
        companion = s.get(Companion, _to_uuid(payload.get("companion_id")))
        provider = s.get(ChannelProvider, _to_uuid(payload.get("provider_id")))
        if user is None or companion is None or provider is None or companion.user_id != user.id:
            return None

        provider_bot_id = _to_uuid(payload.get("provider_bot_id"))
        bot = s.get(ChannelBotRegistry, provider_bot_id) if provider_bot_id else None
        if provider.provider_kind == "discord" and bot is None:
            return None
        if bot is not None and bot.provider_id != provider.id:
            return None

        permission_scope = payload.get("permission_scope") or "reply_only"
        outbound_policy = payload.get("outbound_policy") or "reply_only"
        memory_policy = payload.get("memory_policy") or "ephemeral_review_gated"
        checkin_enabled = permission_scope == "low_frequency_checkin" and bool(payload.get("checkin_enabled", False))

        presence_binding = PresenceChannelBinding(
            user_id=user.id,
            companion_id=companion.id,
            binding_status="ready",
            channel_kind="readiness_stub",
            connector_kind="readiness_stub",
            external_channel_label=payload.get("external_channel_label") or provider.provider_display_name,
            external_channel_ref_hash=payload.get("external_channel_ref_hash"),
            stores_plaintext_token=False,
            credentials_ref=None,
            can_receive_inbound=True,
            can_send_outbound=outbound_policy != "disabled",
            requires_user_approval=True,
            readiness_notes="Channel Gateway channel gateway bridge binding",
            permission_snapshot_json=_safe_json(payload.get("permission_snapshot_json")),
            boundary_snapshot_json=_safe_json(payload.get("boundary_snapshot_json")),
            metadata_={"implementation_origin": "channel_gateway", "bridge": "presence_channel_binding"},
        )
        s.add(presence_binding)
        s.flush()

        binding = ChannelBinding(
            user_id=user.id,
            companion_id=companion.id,
            provider_id=provider.id,
            provider_bot_id=bot.id if bot else None,
            presence_channel_binding_id=presence_binding.id,
            binding_status=payload.get("binding_status") or "draft",
            binding_scope=payload.get("binding_scope") or "dm",
            permission_scope=permission_scope,
            outbound_policy=outbound_policy,
            memory_policy=memory_policy,
            requires_user_approval=True,
            can_receive_inbound=bool(payload.get("can_receive_inbound", True)),
            can_send_outbound=outbound_policy != "disabled" and bool(payload.get("can_send_outbound", True)),
            checkin_enabled=checkin_enabled,
            memory_write_requires_review=True,
            raw_message_storage_allowed=False,
            stores_plaintext_token=False,
            external_channel_ref_hash=payload.get("external_channel_ref_hash"),
            external_user_ref_hash=payload.get("external_user_ref_hash"),
            external_guild_ref_hash=payload.get("external_guild_ref_hash"),
            external_thread_ref_hash=payload.get("external_thread_ref_hash"),
            permission_snapshot_json=_safe_json(payload.get("permission_snapshot_json")),
            boundary_snapshot_json=_safe_json(payload.get("boundary_snapshot_json")),
            metadata_={"implementation_origin": "channel_gateway", "provider_key": provider.provider_key},
        )
        s.add(binding)
        s.flush()
        _record_binding_status(s, binding, "created", None, binding.binding_status, "Channel binding created")
        trace = _record_trace(s, binding, "binding", "recorded", "Channel binding created")
        _record_audit(s, binding, "binding_created", "Channel binding created", trace.id)
        s.commit()
        return get_binding_bundle(binding.id)


def get_binding_bundle(binding_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        binding = s.get(ChannelBinding, binding_id)
        if binding is None:
            return None
        provider = s.get(ChannelProvider, binding.provider_id)
        bot = s.get(ChannelBotRegistry, binding.provider_bot_id) if binding.provider_bot_id else None
        recent_status_events = list(
            s.execute(
                select(ChannelBindingStatusEvent)
                .where(ChannelBindingStatusEvent.channel_binding_id == binding.id)
                .order_by(ChannelBindingStatusEvent.occurred_at.desc())
                .limit(10)
            ).scalars().all()
        )
        recent_trace_events = list(
            s.execute(
                select(ChannelTraceEvent)
                .where(ChannelTraceEvent.channel_binding_id == binding.id)
                .order_by(ChannelTraceEvent.occurred_at.desc())
                .limit(10)
            ).scalars().all()
        )
        recent_audit_logs = list(
            s.execute(
                select(ChannelAuditLog)
                .where(ChannelAuditLog.channel_binding_id == binding.id)
                .order_by(ChannelAuditLog.occurred_at.desc())
                .limit(10)
            ).scalars().all()
        )
        return {
            **_binding_to_dict(binding),
            "provider": _provider_to_dict(provider) if provider else None,
            "provider_bot": _bot_to_dict(bot) if bot else None,
            "recent_status_events": [_status_event_to_dict(item) for item in recent_status_events],
            "recent_trace_events": [_trace_to_dict(item) for item in recent_trace_events],
            "recent_audit_logs": [_audit_to_dict(item) for item in recent_audit_logs],
        }


def transition_binding(binding_id: uuid.UUID, action: str, reason: str | None = None) -> dict[str, Any] | None:
    next_status_by_action = {"activate": "active", "disable": "disabled", "restore": "active"}
    status_event_by_action = {"activate": "activated", "disable": "disabled", "restore": "restored"}
    if action not in next_status_by_action:
        return None
    with get_session() as s:
        binding = s.get(ChannelBinding, binding_id)
        if binding is None:
            return None
        previous_status = binding.binding_status
        next_status = next_status_by_action[action]
        binding.binding_status = next_status
        binding.updated_at = _now()
        if binding.presence_channel_binding_id:
            presence_binding = s.get(PresenceChannelBinding, binding.presence_channel_binding_id)
            if presence_binding is not None:
                presence_binding.binding_status = "ready" if next_status == "active" else next_status
                presence_binding.updated_at = _now()
        _record_binding_status(s, binding, status_event_by_action[action], previous_status, next_status, reason)
        trace = _record_trace(s, binding, "binding", "recorded", f"Channel binding {action}")
        _record_audit(s, binding, "binding_updated", f"Channel binding {action}", trace.id)
        s.commit()
        return get_binding_bundle(binding.id)


def revoke_binding(binding_id: uuid.UUID, reason: str | None = None) -> dict[str, Any] | None:
    with get_session() as s:
        binding = s.get(ChannelBinding, binding_id)
        if binding is None or binding.presence_channel_binding_id is None:
            return None
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

        revoke_event = ChannelRevokeEvent(
            user_id=binding.user_id,
            presence_channel_binding_id=binding.presence_channel_binding_id,
            channel_binding_id=binding.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            revoke_status="applied",
            revoke_scope="all",
            revokes_credentials_ref=True,
            stops_inbound=True,
            stops_outbound=True,
            stops_checkins=True,
            clears_ephemeral_buffer=True,
            disables_memory_candidates=True,
            audit_required=True,
            revoke_reason=reason,
            revoke_payload_json={"reason": reason} if reason else {},
            applied_at=now,
            metadata_={"implementation_origin": "channel_gateway"},
        )
        s.add(revoke_event)
        _record_binding_status(s, binding, "revoked", previous_status, "revoked", reason)
        trace = _record_trace(s, binding, "revoke", "recorded", "Channel binding revoked")
        _record_audit(s, binding, "revoked", "Channel binding revoked", trace.id)
        s.commit()
        s.refresh(revoke_event)
        bundle = get_binding_bundle(binding.id)
        if bundle is not None:
            bundle["revoke_event"] = _revoke_to_dict(revoke_event)
        return bundle


def _record_binding_status(
    s: Session,
    binding: ChannelBinding,
    status_event: str,
    from_status: str | None,
    to_status: str,
    reason: str | None,
) -> ChannelBindingStatusEvent:
    event = ChannelBindingStatusEvent(
        user_id=binding.user_id,
        channel_binding_id=binding.id,
        status_event=status_event,
        from_status=from_status,
        to_status=to_status,
        status_reason=reason,
        safe_status_payload_json={"reason": reason} if reason else {},
        occurred_at=_now(),
        metadata_={"implementation_origin": "channel_gateway"},
    )
    s.add(event)
    return event


def _record_trace(
    s: Session,
    binding: ChannelBinding,
    trace_event_type: str,
    trace_status: str,
    summary: str,
) -> ChannelTraceEvent:
    event = ChannelTraceEvent(
        user_id=binding.user_id,
        companion_id=binding.companion_id,
        channel_binding_id=binding.id,
        provider_id=binding.provider_id,
        provider_bot_id=binding.provider_bot_id,
        trace_event_type=trace_event_type,
        trace_status=trace_status,
        trace_summary=summary,
        safe_trace_payload_json={"binding_status": binding.binding_status},
        occurred_at=_now(),
        metadata_={"implementation_origin": "channel_gateway"},
    )
    s.add(event)
    s.flush()
    return event


def _record_audit(
    s: Session,
    binding: ChannelBinding,
    audit_log_type: str,
    summary: str,
    trace_event_id: uuid.UUID | None = None,
) -> ChannelAuditLog:
    audit = ChannelAuditLog(
        user_id=binding.user_id,
        channel_binding_id=binding.id,
        provider_id=binding.provider_id,
        provider_bot_id=binding.provider_bot_id,
        channel_trace_event_id=trace_event_id,
        audit_log_type=audit_log_type,
        audit_summary=summary,
        safe_audit_payload_json={"binding_status": binding.binding_status},
        occurred_at=_now(),
        metadata_={"implementation_origin": "channel_gateway"},
    )
    s.add(audit)
    return audit


def _provider_to_dict(row: ChannelProvider) -> dict[str, Any]:
    return ChannelProviderRead.model_validate(row).model_dump(mode="json")


def _bot_to_dict(row: ChannelBotRegistry) -> dict[str, Any]:
    return ChannelBotRegistryRead.model_validate(row).model_dump(mode="json")


def _binding_to_dict(row: ChannelBinding) -> dict[str, Any]:
    return ChannelBindingRead.model_validate(row).model_dump(mode="json")


def _revoke_to_dict(row: ChannelRevokeEvent) -> dict[str, Any]:
    return ChannelRevokeEventRead.model_validate(row).model_dump(mode="json")


def _status_event_to_dict(row: ChannelBindingStatusEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "channel_binding_id": str(row.channel_binding_id),
        "status_event": row.status_event,
        "from_status": row.from_status,
        "to_status": row.to_status,
        "status_reason": row.status_reason,
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _trace_to_dict(row: ChannelTraceEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "trace_event_type": row.trace_event_type,
        "trace_status": row.trace_status,
        "trace_summary": row.trace_summary,
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _audit_to_dict(row: ChannelAuditLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "audit_log_type": row.audit_log_type,
        "audit_summary": row.audit_summary,
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _safe_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _scrub_safe_json(value)


def _scrub_safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                continue
            result[key_text] = _scrub_safe_json(item)
        return result
    if isinstance(value, list):
        return [_scrub_safe_json(item) for item in value]
    return value


def _contains_plain_secret_field(payload: dict[str, Any]) -> bool:
    for key in payload:
        key_text = str(key).lower()
        if key_text == "token_secret_ref":
            continue
        if _is_sensitive_key(key_text):
            return True
    return False


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _is_secret_reference(value: str) -> bool:
    allowed_prefixes = (".secrets/", "secret://", "env:", "local:", "vault://")
    return any(value.startswith(prefix) for prefix in allowed_prefixes)


def _to_uuid(value: Any) -> uuid.UUID | None:
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)
