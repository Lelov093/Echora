"""Discord multi-bot adapter contract routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services.discord_multi_bot_adapter_service import DiscordMultiBotAdapter
from app.services.discord_conversation_bridge import resolve_companion_id
from app.services.companion_channel_identity_service import get_session
from app.services import discord_dm_service

router = APIRouter(prefix="/discord-bot-identities", tags=["Discord Bot Identities"])


@router.get("")
def list_discord_bot_identities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    status = DiscordMultiBotAdapter().registry_status()
    bots = status.get("bots", [])
    total = len(bots)
    start = (page - 1) * page_size
    return paginated_ok(bots[start:start + page_size], page, page_size, total)


@router.get("/bindings")
def get_discord_bot_bindings():
    """Return bot identity + DB binding status for all Discord bots."""
    registry = DiscordMultiBotAdapter().registry_status()
    bots = []
    for raw_bot in registry.get("bots", []):
        bot_key = raw_bot.get("bot_key", "")
        binding = None
        companion_name = None
        try:
            s = get_session()
            from sqlalchemy import select as sa_select
            from app.db.models.channel_gateway import ChannelBotRegistry
            from app.db.models.channel_gateway_readiness import CompanionChannelIdentity
            from app.db.models.companion import Companion

            bot_rows = list(s.execute(
                sa_select(ChannelBotRegistry).where(ChannelBotRegistry.bot_key == bot_key)
            ).scalars().all())
            if bot_rows:
                bot_ident = bot_rows[0]
                cci_rows = list(s.execute(
                    sa_select(CompanionChannelIdentity).where(
                        CompanionChannelIdentity.provider_bot_id == bot_ident.id,
                        CompanionChannelIdentity.channel_status == "active",
                    )
                ).scalars().all())
                if cci_rows:
                    cci = cci_rows[0]
                    comp = s.get(Companion, cci.companion_id)
                    if comp:
                        companion_name = comp.name
                    binding = {
                        "source": "db",
                        "companion_channel_identity_id": str(cci.id),
                        "companion_id": str(cci.companion_id) if cci.companion_id else None,
                        "companion_name": companion_name,
                        "status": cci.channel_status,
                        "revision": cci.revision,
                    }
            s.close()
        except Exception:
            pass
        bots.append({
            "bot_key": bot_key,
            "display_name": raw_bot.get("bot_display_name", bot_key),
            "app_id": raw_bot.get("app_id", ""),
            "token_status": raw_bot.get("token_status", "unknown"),
            "binding": binding,
            "binding_status": "bound" if binding else "companion_unbound",
        })
    return ok({"bots": bots})


@router.post("/bind-companion")
def bind_bot_to_companion(body: dict):
    """CAS-safe Web-only Bot/Companion bind with explicit dependency handling."""
    bot_key = body.get("bot_key", "")
    companion_id = body.get("companion_id", "")
    if not bot_key or not companion_id:
        return err("VALIDATION_ERROR", "bot_key and companion_id are required")
    app_id = body.get("app_id", "")
    try:
        from app.services.discord_conversation_bridge import bind_companion
        result = bind_companion(
            bot_key,
            companion_id,
            app_id,
            expected_revision=int(body["expected_revision"]) if body.get("expected_revision") is not None else None,
            dependency_action=str(body.get("dependency_action") or "reject"),
        )
        if result.get("source") == "db" and result.get("persistent"):
            return ok(result)
        else:
            return err("BIND_FAILED", result.get("db_error", "Unknown error"))
    except Exception as e:
        return err("BIND_ERROR", type(e).__name__)


@router.post("/rebind-preflight")
def preflight_bot_companion_rebind(body: dict):
    bot_key = str(body.get("bot_key") or "")
    companion_id = str(body.get("companion_id") or "")
    if not bot_key or not companion_id:
        return err("VALIDATION_ERROR", "bot_key and companion_id are required")
    try:
        from app.services.discord_conversation_bridge import preflight_companion_rebind
        return ok(preflight_companion_rebind(bot_key, companion_id))
    except Exception as exc:
        return err("REBIND_PREFLIGHT_ERROR", type(exc).__name__)


@router.delete("/{bot_identity_id}/binding")
def unbind_discord_bot(bot_identity_id: str):
    """Deactivate a bot's companion binding without deleting history."""
    try:
        s = get_session()
        from sqlalchemy import select as sa_select
        from app.db.models import (
            CompanionChannelIdentity,
            DiscordChannelBotMembership,
            DiscordDmConversationBinding,
        )
        provider_bot_id = uuid.UUID(bot_identity_id)
        dependent_dm = s.execute(sa_select(DiscordDmConversationBinding.id).where(
            DiscordDmConversationBinding.provider_bot_id == provider_bot_id,
            DiscordDmConversationBinding.binding_status.in_(["active", "paused"]),
        ).limit(1)).first()
        dependent_room = s.execute(sa_select(DiscordChannelBotMembership.id).where(
            DiscordChannelBotMembership.provider_bot_id == provider_bot_id,
            DiscordChannelBotMembership.membership_status == "active",
        ).limit(1)).first()
        if dependent_dm or dependent_room:
            s.close()
            return err("UNBIND_REQUIRES_DEPENDENCY_RESOLUTION", "请先暂停或撤销相关 DM 与聊天室频道绑定。")
        rows = list(s.execute(sa_select(CompanionChannelIdentity).where(
            CompanionChannelIdentity.provider_bot_id == provider_bot_id,
            CompanionChannelIdentity.channel_status == "active",
        ).with_for_update()).scalars().all())
        for row in rows:
            row.channel_status = "disabled"
            row.identity_status = "disabled"
            row.revision += 1
        s.commit()
        s.close()
        if rows:
            return ok({"unbound": True, "ids": [str(row.id) for row in rows]})
        return ok({"unbound": False, "reason": "no_active_binding"})
    except Exception as e:
        return err("UNBIND_ERROR", str(e))


@router.get("/status")
def discord_bot_identity_status():
    return ok(DiscordMultiBotAdapter().registry_status())


@router.post("/normalize-inbound")
def discord_normalize_inbound(body: dict):
    data = DiscordMultiBotAdapter().normalize_inbound(body or {})
    if not data:
        return err("DISCORD_BOT_IDENTITY_NOT_FOUND", "Discord bot identity not found")
    return ok(data)


@router.post("/prepare-outbound")
def discord_prepare_outbound(body: dict):
    data = DiscordMultiBotAdapter().prepare_outbound(body or {})
    if not data:
        return err("DISCORD_BOT_IDENTITY_NOT_FOUND", "Discord bot identity not found")
    return ok(data)


@router.post("/test-connection")
def discord_test_connection(body: dict):
    data = DiscordMultiBotAdapter().test_connection(body or {})
    if not data:
        return err("DISCORD_BOT_IDENTITY_NOT_FOUND", "Discord bot identity not found")
    return ok(data)


@router.post("/map-failure")
def discord_map_failure(body: dict):
    return ok(DiscordMultiBotAdapter().map_failure(body or {}))


@router.post("/map-rate-limit")
def discord_map_rate_limit(body: dict):
    return ok(DiscordMultiBotAdapter().map_rate_limit(body or {}))


@router.get("/dm-bindings")
def list_discord_dm_bindings(user_id: str | None = None, companion_id: str | None = None):
    return ok(
        {
            "items": discord_dm_service.list_bindings(
                user_id=uuid.UUID(user_id) if user_id else None,
                companion_id=uuid.UUID(companion_id) if companion_id else None,
            )
        }
    )


@router.get("/dm-deliveries")
def list_discord_dm_deliveries(dm_binding_id: str | None = None, limit: int = Query(50, ge=1, le=100)):
    return ok(
        {
            "items": discord_dm_service.list_deliveries(
                dm_binding_id=uuid.UUID(dm_binding_id) if dm_binding_id else None,
                limit=limit,
            )
        }
    )


@router.post("/dm-bindings/{binding_id}/{action}")
def transition_discord_dm_binding(binding_id: str, action: str, body: dict | None = None):
    payload = body or {}
    if payload.get("expected_revision") is None:
        return err("DM_BINDING_REVISION_REQUIRED", "expected_revision is required")
    try:
        data = discord_dm_service.transition_binding(
            uuid.UUID(binding_id),
            action,
            expected_revision=int(payload["expected_revision"]),
            conversation_id=uuid.UUID(payload["conversation_id"]) if payload.get("conversation_id") else None,
            source="web",
        )
        return ok(data)
    except discord_dm_service.DiscordDmError as exc:
        return err(exc.code, exc.message, {"retryable": exc.retryable})
