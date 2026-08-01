"""Channel Gateway companion channel identity API service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    ChannelBinding,
    ChannelBotRegistry,
    ChannelProvider,
    Companion,
    CompanionBoundaryProfile,
    CompanionChannelIdentity,
    CompanionIdentityProfile,
    CompanionPersonaProfile,
    PresenceChannelBinding,
)
from app.services.channel_gateway_service import get_binding_bundle

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_identities(
    *,
    companion_id: uuid.UUID | None = None,
    channel_status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(CompanionChannelIdentity)
        if companion_id is not None:
            stmt = stmt.where(CompanionChannelIdentity.companion_id == companion_id)
        if channel_status:
            stmt = stmt.where(CompanionChannelIdentity.channel_status == channel_status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(CompanionChannelIdentity.updated_at.desc(), CompanionChannelIdentity.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_identity_to_dict(s, item) for item in items], "total": total}


def get_identity(identity_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        identity = s.get(CompanionChannelIdentity, identity_id)
        return _identity_to_dict(s, identity) if identity else None


def create_identity(payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, _to_uuid(payload.get("companion_id")))
        if companion is None or companion.deleted_at is not None:
            return None

        binding = s.get(ChannelBinding, _to_uuid(payload.get("channel_binding_id"))) if payload.get("channel_binding_id") else None
        presence_binding = _resolve_presence_binding(s, companion, binding, payload)
        if presence_binding is None:
            return None

        provider_bot_id = _to_uuid(payload.get("provider_bot_id")) or (binding.provider_bot_id if binding else None)
        bot = s.get(ChannelBotRegistry, provider_bot_id) if provider_bot_id else None
        if bot is not None and _bot_occupied_by_other_companion(s, bot.id, companion.id):
            return None
        if binding is not None and binding.companion_id != companion.id:
            return None
        if binding is not None and bot is not None and binding.provider_bot_id != bot.id:
            return None

        identity_scope = payload.get("identity_scope") or ("discord_bot_identity" if bot else "mock_projection")
        if identity_scope == "discord_bot_identity" and bot is None:
            return None

        projection = _build_persona_projection(s, companion, payload)
        identity = CompanionChannelIdentity(
            user_id=companion.user_id,
            presence_channel_binding_id=presence_binding.id,
            companion_id=companion.id,
            identity_status=payload.get("identity_status") or "ready",
            display_name=payload.get("display_name") or companion.name,
            external_identity_ref_hash=payload.get("external_identity_ref_hash"),
            persona_projection_policy=payload.get("persona_projection_policy") or "summary_only",
            can_present_companion_identity=True,
            can_autonomously_message=False,
            identity_profile_json={
                "projection_source": "companion_profile",
                "private_memory_visible": False,
            },
            channel_binding_id=binding.id if binding else None,
            provider_bot_id=bot.id if bot else None,
            identity_scope=identity_scope,
            channel_status=payload.get("channel_status") or "active",
            channel_display_name=payload.get("channel_display_name") or companion.name,
            channel_avatar_placeholder=payload.get("channel_avatar_placeholder"),
            channel_persona_projection=projection["summary"],
            channel_persona_projection_json=projection["json"],
            channel_presence_style=payload.get("channel_presence_style") or "inherit_companion",
            channel_boundary_profile=_boundary_profile(s, companion, payload),
            persona_projection_mode=payload.get("persona_projection_mode") or "summary_only",
            private_memory_visible_by_default=False,
            uses_single_global_bot_gateway=False,
            is_global_bot_identity=False,
            metadata_={"implementation_origin": "channel_identity"},
        )
        s.add(identity)
        s.commit()
        s.refresh(identity)
        return _identity_to_dict(s, identity)


def update_identity(identity_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        identity = s.get(CompanionChannelIdentity, identity_id)
        if identity is None:
            return None
        companion = s.get(Companion, identity.companion_id)
        if companion is None:
            return None

        if "provider_bot_id" in payload and payload["provider_bot_id"]:
            bot_id = _to_uuid(payload["provider_bot_id"])
            bot = s.get(ChannelBotRegistry, bot_id)
            if bot is None or _bot_occupied_by_other_companion(s, bot.id, companion.id):
                return None
            identity.provider_bot_id = bot.id
            identity.identity_scope = "discord_bot_identity"

        mutable_fields = [
            "channel_display_name",
            "channel_avatar_placeholder",
            "channel_presence_style",
            "channel_status",
            "identity_status",
            "persona_projection_mode",
            "persona_projection_policy",
        ]
        for field in mutable_fields:
            if field in payload and payload[field] is not None:
                setattr(identity, field, payload[field])
        if "channel_boundary_profile" in payload and isinstance(payload["channel_boundary_profile"], dict):
            identity.channel_boundary_profile = _safe_boundary(payload["channel_boundary_profile"])
        if payload.get("refresh_persona_projection"):
            projection = _build_persona_projection(s, companion, payload)
            identity.channel_persona_projection = projection["summary"]
            identity.channel_persona_projection_json = projection["json"]
        identity.private_memory_visible_by_default = False
        identity.uses_single_global_bot_gateway = False
        identity.is_global_bot_identity = False
        identity.can_autonomously_message = False
        identity.updated_at = _now()
        s.commit()
        s.refresh(identity)
        return _identity_to_dict(s, identity)


def disable_identity(identity_id: uuid.UUID, reason: str | None = None) -> dict[str, Any] | None:
    with get_session() as s:
        identity = s.get(CompanionChannelIdentity, identity_id)
        if identity is None:
            return None
        identity.channel_status = "disabled"
        identity.identity_status = "disabled"
        identity.updated_at = _now()
        metadata = dict(identity.metadata_ or {})
        metadata["disabled_reason"] = reason
        identity.metadata_ = metadata
        s.commit()
        s.refresh(identity)
        return _identity_to_dict(s, identity)


def unbind_identity(identity_id: uuid.UUID, reason: str | None = None) -> dict[str, Any] | None:
    with get_session() as s:
        identity = s.get(CompanionChannelIdentity, identity_id)
        if identity is None:
            return None
        identity.provider_bot_id = None
        identity.channel_binding_id = None
        identity.identity_scope = "mock_projection"
        identity.channel_status = "disabled"
        identity.identity_status = "disabled"
        identity.private_memory_visible_by_default = False
        identity.uses_single_global_bot_gateway = False
        identity.is_global_bot_identity = False
        identity.can_autonomously_message = False
        identity.updated_at = _now()
        metadata = dict(identity.metadata_ or {})
        metadata["unbind_reason"] = reason
        identity.metadata_ = metadata
        s.commit()
        s.refresh(identity)
        return _identity_to_dict(s, identity)


def _resolve_presence_binding(
    s: Session,
    companion: Companion,
    binding: ChannelBinding | None,
    payload: dict[str, Any],
) -> PresenceChannelBinding | None:
    if binding is not None:
        if binding.companion_id != companion.id or binding.presence_channel_binding_id is None:
            return None
        return s.get(PresenceChannelBinding, binding.presence_channel_binding_id)
    presence_binding_id = _to_uuid(payload.get("presence_channel_binding_id"))
    if presence_binding_id is None:
        return None
    presence_binding = s.get(PresenceChannelBinding, presence_binding_id)
    if presence_binding is None or presence_binding.companion_id != companion.id:
        return None
    return presence_binding


def _bot_occupied_by_other_companion(s: Session, bot_id: uuid.UUID, companion_id: uuid.UUID) -> bool:
    row = s.execute(
        select(CompanionChannelIdentity)
        .where(
            CompanionChannelIdentity.provider_bot_id == bot_id,
            CompanionChannelIdentity.companion_id != companion_id,
            CompanionChannelIdentity.channel_status.in_(["draft", "active"]),
        )
        .limit(1)
    ).scalar_one_or_none()
    return row is not None


def _build_persona_projection(s: Session, companion: Companion, payload: dict[str, Any]) -> dict[str, Any]:
    explicit_summary = payload.get("channel_persona_projection")
    if explicit_summary:
        summary = _truncate(str(explicit_summary), 800)
    else:
        identity = s.execute(
            select(CompanionIdentityProfile).where(CompanionIdentityProfile.companion_id == companion.id)
        ).scalar_one_or_none()
        persona = s.execute(
            select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion.id)
        ).scalar_one_or_none()
        parts = [
            companion.name,
            identity.identity_summary if identity else companion.subtitle,
            persona.persona_summary if persona else companion.base_personality,
            persona.communication_style_summary if persona else None,
        ]
        summary = " | ".join(_truncate(str(item), 220) for item in parts if item)
    return {
        "summary": summary,
        "json": {
            "source": "companion_safe_summary",
            "display_name": companion.name,
            "private_memory_included": False,
            "projection_mode": payload.get("persona_projection_mode") or "summary_only",
        },
    }


def _boundary_profile(s: Session, companion: Companion, payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("channel_boundary_profile"), dict):
        return _safe_boundary(payload["channel_boundary_profile"])
    boundary = s.execute(
        select(CompanionBoundaryProfile).where(CompanionBoundaryProfile.companion_id == companion.id)
    ).scalar_one_or_none()
    return {
        "source": "companion_boundary_summary",
        "private_memory_visible_by_default": False,
        "cross_companion_memory_allowed": False,
        "raw_channel_payload_allowed": False,
        "relationship_boundary_summary": getattr(boundary, "relationship_boundary_summary", None) if boundary else None,
    }


def _safe_boundary(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["private_memory_visible_by_default"] = False
    result["cross_companion_memory_allowed"] = False
    result["raw_channel_payload_allowed"] = False
    return result


def _identity_to_dict(s: Session, row: CompanionChannelIdentity) -> dict[str, Any]:
    bot = s.get(ChannelBotRegistry, row.provider_bot_id) if row.provider_bot_id else None
    provider = s.get(ChannelProvider, bot.provider_id) if bot else None
    binding = get_binding_bundle(row.channel_binding_id) if row.channel_binding_id else None
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "companion_id": str(row.companion_id),
        "presence_channel_binding_id": str(row.presence_channel_binding_id),
        "channel_binding_id": str(row.channel_binding_id) if row.channel_binding_id else None,
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "identity_status": row.identity_status,
        "identity_scope": row.identity_scope,
        "display_name": row.display_name,
        "channel_status": row.channel_status,
        "channel_display_name": row.channel_display_name,
        "channel_avatar_placeholder": row.channel_avatar_placeholder,
        "channel_persona_projection": row.channel_persona_projection,
        "channel_persona_projection_json": row.channel_persona_projection_json or {},
        "channel_presence_style": row.channel_presence_style,
        "channel_boundary_profile": row.channel_boundary_profile or {},
        "persona_projection_policy": row.persona_projection_policy,
        "persona_projection_mode": row.persona_projection_mode,
        "can_present_companion_identity": row.can_present_companion_identity,
        "can_autonomously_message": row.can_autonomously_message,
        "private_memory_visible_by_default": row.private_memory_visible_by_default,
        "uses_single_global_bot_gateway": row.uses_single_global_bot_gateway,
        "is_global_bot_identity": row.is_global_bot_identity,
        "provider": _provider_to_dict(provider) if provider else None,
        "provider_bot": _bot_to_safe_dict(bot) if bot else None,
        "binding": binding,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _provider_to_dict(row: ChannelProvider) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "provider_key": row.provider_key,
        "provider_kind": row.provider_kind,
        "provider_status": row.provider_status,
        "supports_multi_bot": row.supports_multi_bot,
        "requires_external_token": row.requires_external_token,
    }


def _bot_to_safe_dict(row: ChannelBotRegistry) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "provider_id": str(row.provider_id),
        "user_id": str(row.user_id) if row.user_id else None,
        "bot_key": row.bot_key,
        "bot_display_name": row.bot_display_name,
        "bot_status": row.bot_status,
        "token_status": row.token_status,
        "stores_plaintext_token": row.stores_plaintext_token,
        "safe_metadata_json": row.safe_metadata_json or {},
    }


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
