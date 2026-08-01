"""Channel Gateway.1 Discord Conversation Bridge.

Routes Discord messages to Echora conversation runs and returns responses.
Maintains {companion_id}:{channel_id}:{discord_author_id} → conversation_id mapping.

Companion resolution order:
  1. DB companion_channel_identities (authoritative)
  2. Runtime bindings file (debug fallback)
  3. Registry JSON companion_id field
"""

import json
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.services.discord_multi_bot_adapter_service import _load_registry, _project_root
from app.services import discord_dm_service

logger = logging.getLogger(__name__)

# In-memory conversation mapping (companion_id:channel_id:author_id → conv_id)
_conversation_map: dict[str, str] = {}

# Bot user ID cache (populated from READY events)
_bot_user_id_cache: dict[str, str] = {}

# Runtime bindings file (debug fallback only)
BINDINGS_PATH = _project_root() / ".data" / "discord_runtime_bindings.json"

_http: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _http
    if _http is None:
        _http = httpx.Client(timeout=httpx.Timeout(60.0))
    return _http


import re

def _make_conv_key(companion_id: str, channel_id: str, author_id: str) -> str:
    return f"discord:{companion_id}:{channel_id}:{author_id}"


def _normalize_content(content: str) -> str:
    """Strip Discord mention syntax (<@ID>, <@!ID>, <@&ID>) from message content."""
    cleaned = re.sub(r'<@!?\d+>', '', content)   # user mentions
    cleaned = re.sub(r'<@&\d+>', '', cleaned)     # role mentions
    cleaned = re.sub(r'<#\d+>', '', cleaned)      # channel mentions
    return cleaned.strip()


def cache_bot_user_id(bot_key: str, bot_user_id: str) -> None:
    """Cache the bot's Discord user ID from READY event."""
    _bot_user_id_cache[bot_key] = bot_user_id


def _load_runtime_bindings() -> dict[str, str]:
    """Load bot_key → companion_id from runtime bindings file (debug fallback)."""
    try:
        BINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        if BINDINGS_PATH.exists():
            return json.loads(BINDINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def resolve_companion_id(bot_key: str, bot_user_id: str | None = None) -> dict[str, Any]:
    """Resolve companion_id for a bot_key. DB is the authoritative source."""
    # 1. DB companion_channel_identities (authoritative source of truth)
    try:
        from app.services.companion_channel_identity_service import get_session
        s = get_session()
        from sqlalchemy import select as sa_select
        from app.db.models.channel_gateway_readiness import CompanionChannelIdentity
        from app.db.models.channel_gateway import ChannelBotRegistry
        rows = list(s.execute(
            sa_select(CompanionChannelIdentity).where(
                CompanionChannelIdentity.channel_status == "active"
            )
        ).scalars().all())
        for row in rows:
            provider_bot_id = row.provider_bot_id
            if not provider_bot_id:
                continue
            try:
                bot_ident = s.get(ChannelBotRegistry, provider_bot_id)
                if bot_ident and bot_ident.bot_key == bot_key:
                    cid = str(row.companion_id) if row.companion_id else None
                    if cid:
                        s.close()
                        return {
                            "companion_id": cid,
                            "source": "db",
                            "resolved": True,
                            "bot_identity_id": str(provider_bot_id),
                            "companion_channel_identity_id": str(row.id),
                        }
            except Exception:
                pass
        s.close()
    except Exception as e:
        logger.warning(f"DB companion_channel_identity lookup error: {e}")

    # 2. Runtime bindings file (debug fallback, not authoritative)
    runtime = _load_runtime_bindings()
    if bot_key in runtime:
        return {
            "companion_id": runtime[bot_key],
            "source": "runtime_file_fallback",
            "resolved": True,
        }

    # 3. Registry JSON companion_id field (config-level, least preferred)
    registry = _load_registry()
    for item in registry.get("bots", []):
        bk = item.bot_key if hasattr(item, 'bot_key') else item.get("bot_key", "")
        if bk == bot_key:
            cid = item.companion_id if hasattr(item, 'companion_id') else item.get("companion_id")
            if cid:
                return {"companion_id": cid, "source": "registry_json", "resolved": True}

    return {
        "companion_id": None,
        "source": None,
        "resolved": False,
        "reason": "companion_channel_identity_not_found",
    }


def preflight_companion_rebind(bot_key: str, companion_id: str) -> dict[str, Any]:
    """Return durable dependencies that make a Bot/Companion rebind consequential."""
    from sqlalchemy import select as sa_select
    from app.db.models import (
        ChannelBotRegistry, CompanionChannelIdentity, DiscordChannelBotMembership,
        DiscordChannelRoomBinding, DiscordDmConversationBinding, DiscordDmDelivery,
    )
    from app.services.companion_channel_identity_service import get_session

    with get_session() as s:
        bot = s.execute(sa_select(ChannelBotRegistry).where(ChannelBotRegistry.bot_key == bot_key)).scalar_one_or_none()
        if bot is None:
            return {"bot_key": bot_key, "target_companion_id": companion_id, "current_identity": None, "dependencies": {}, "allowed": True}
        current = s.execute(sa_select(CompanionChannelIdentity).where(
            CompanionChannelIdentity.provider_bot_id == bot.id,
            CompanionChannelIdentity.channel_status == "active",
        )).scalar_one_or_none()
        if current is None or str(current.companion_id) == str(companion_id):
            return {
                "bot_key": bot_key, "provider_bot_id": str(bot.id), "target_companion_id": companion_id,
                "current_identity": _safe_identity_projection(current), "dependencies": {}, "allowed": True,
            }
        dm_bindings = list(s.execute(sa_select(DiscordDmConversationBinding).where(
            DiscordDmConversationBinding.provider_bot_id == bot.id,
            DiscordDmConversationBinding.binding_status.in_(["active", "paused"]),
        )).scalars().all())
        dm_ids = [item.id for item in dm_bindings]
        pending_deliveries = list(s.execute(sa_select(DiscordDmDelivery).where(
            DiscordDmDelivery.dm_binding_id.in_(dm_ids),
            DiscordDmDelivery.delivery_status.in_(["queued", "leased", "retry_scheduled"]),
        )).scalars().all()) if dm_ids else []
        memberships = list(s.execute(sa_select(DiscordChannelBotMembership).where(
            DiscordChannelBotMembership.provider_bot_id == bot.id,
            DiscordChannelBotMembership.membership_status == "active",
        )).scalars().all())
        room_binding_ids = list({item.discord_channel_room_binding_id for item in memberships})
        room_bindings = list(s.execute(sa_select(DiscordChannelRoomBinding).where(
            DiscordChannelRoomBinding.id.in_(room_binding_ids),
            DiscordChannelRoomBinding.binding_status.in_(["active", "paused", "conflict_paused"]),
        )).scalars().all()) if room_binding_ids else []
        dependencies = {
            "live_dm_binding_count": len(dm_bindings),
            "pending_delivery_count": len(pending_deliveries),
            "live_room_binding_count": len(room_bindings),
            "dm_binding_ids": [str(item.id) for item in dm_bindings],
            "room_binding_ids": [str(item.id) for item in room_bindings],
        }
        return {
            "bot_key": bot_key, "provider_bot_id": str(bot.id), "target_companion_id": companion_id,
            "current_identity": _safe_identity_projection(current), "dependencies": dependencies,
            "allowed": not any((dm_bindings, pending_deliveries, room_bindings)),
            "requires_explicit_pause": any((dm_bindings, pending_deliveries, room_bindings)),
        }


def bind_companion(
    bot_key: str,
    companion_id: str,
    app_id: str = "",
    *,
    expected_revision: int | None = None,
    dependency_action: str = "reject",
) -> dict[str, Any]:
    """CAS-safe Web-only Bot rebind; dependency pause must be explicit."""
    from sqlalchemy import select as sa_select
    from app.db.models import (
        ChannelBotRegistry, ChannelProvider, Companion, CompanionChannelIdentity,
        DiscordChannelBotMembership, DiscordChannelRoomBinding,
        DiscordDmConversationBinding, DiscordDmDelivery, PresenceChannelBinding,
    )
    from app.services.companion_channel_identity_service import get_session

    target_id = uuid.UUID(companion_id)
    now = datetime.now(timezone.utc)
    result = {"bot_key": bot_key, "companion_id": companion_id}
    try:
        with get_session() as s:
            target = s.get(Companion, target_id)
            if target is None or target.deleted_at is not None:
                return {**result, "db_error": "companion_not_found"}
            bot = s.execute(sa_select(ChannelBotRegistry).where(ChannelBotRegistry.bot_key == bot_key).with_for_update()).scalar_one_or_none()
            if bot is None:
                provider = s.execute(sa_select(ChannelProvider).where(ChannelProvider.provider_key == "discord")).scalar_one_or_none()
                presence = s.execute(sa_select(PresenceChannelBinding).where(
                    PresenceChannelBinding.companion_id == target.id,
                ).order_by(PresenceChannelBinding.created_at.asc()).limit(1)).scalar_one_or_none()
                if provider is None or presence is None:
                    return {**result, "db_error": "discord_provider_or_presence_binding_not_ready"}
                bot = ChannelBotRegistry(
                    provider_id=provider.id, user_id=target.user_id, bot_key=bot_key,
                    bot_display_name=bot_key, bot_status="ready", token_status="configured",
                    token_secret_ref=f"DISCORD_SECRET_{bot_key.upper()}_TOKEN",
                    safe_metadata_json={"app_id": app_id} if app_id else {},
                )
                s.add(bot); s.flush()
            current = s.execute(sa_select(CompanionChannelIdentity).where(
                CompanionChannelIdentity.provider_bot_id == bot.id,
                CompanionChannelIdentity.channel_status == "active",
            ).with_for_update()).scalar_one_or_none()
            if current is not None and current.companion_id == target.id:
                return {
                    **result, "bot_identity_id": str(bot.id),
                    "companion_channel_identity_id": str(current.id), "identity_revision": current.revision,
                    "source": "db", "persistent": True, "idempotent": True,
                }
            if current is not None and expected_revision != current.revision:
                return {**result, "db_error": "identity_revision_conflict", "current_revision": current.revision}
            conflict = s.execute(sa_select(CompanionChannelIdentity).where(
                CompanionChannelIdentity.companion_id == target.id,
                CompanionChannelIdentity.channel_status == "active",
                CompanionChannelIdentity.provider_bot_id != bot.id,
            ).limit(1)).scalar_one_or_none()
            if conflict is not None:
                return {**result, "db_error": "companion_already_bound_to_another_discord_bot", "conflict": True}
            preflight = preflight_companion_rebind(bot_key, companion_id)
            if preflight.get("requires_explicit_pause") and dependency_action != "pause":
                return {**result, "db_error": "bot_rebind_requires_dependency_resolution", "preflight": preflight}
            if current is not None and dependency_action == "pause":
                dm_bindings = list(s.execute(sa_select(DiscordDmConversationBinding).where(
                    DiscordDmConversationBinding.provider_bot_id == bot.id,
                    DiscordDmConversationBinding.binding_status.in_(["active", "paused"]),
                ).with_for_update()).scalars().all())
                for dm in dm_bindings:
                    dm.binding_status = "paused"; dm.revision += 1
                dm_ids = [item.id for item in dm_bindings]
                if dm_ids:
                    for delivery in s.execute(sa_select(DiscordDmDelivery).where(
                        DiscordDmDelivery.dm_binding_id.in_(dm_ids),
                        DiscordDmDelivery.delivery_status.in_(["queued", "leased", "retry_scheduled"]),
                    ).with_for_update()).scalars():
                        delivery.delivery_status = "cancelled"; delivery.cancelled_at = now
                        delivery.lease_owner = None; delivery.lease_expires_at = None
                        delivery.last_error_code = "BOT_COMPANION_REBOUND"
                        delivery.last_error_summary = "Cancelled by explicit Web Bot/Companion rebind."
                memberships = list(s.execute(sa_select(DiscordChannelBotMembership).where(
                    DiscordChannelBotMembership.provider_bot_id == bot.id,
                    DiscordChannelBotMembership.membership_status == "active",
                ).with_for_update()).scalars().all())
                room_binding_ids = {item.discord_channel_room_binding_id for item in memberships}
                for membership in memberships:
                    membership.membership_status = "inactive"; membership.deactivated_at = now; membership.revision += 1
                if room_binding_ids:
                    for binding in s.execute(sa_select(DiscordChannelRoomBinding).where(
                        DiscordChannelRoomBinding.id.in_(room_binding_ids),
                        DiscordChannelRoomBinding.binding_status.in_(["active", "paused", "conflict_paused"]),
                    ).with_for_update()).scalars():
                        binding.binding_status = "conflict_paused"; binding.paused_at = now; binding.revision += 1
                        binding.evidence_json = {**(binding.evidence_json or {}), "paused_reason": "bot_companion_rebound", "at": now.isoformat()}
            if current is not None:
                current.channel_status = "disabled"; current.identity_status = "disabled"
                current.revision += 1; current.updated_at = now
            channel_identity = s.execute(sa_select(CompanionChannelIdentity).where(
                CompanionChannelIdentity.provider_bot_id == bot.id,
                CompanionChannelIdentity.companion_id == target.id,
            ).order_by(CompanionChannelIdentity.created_at.asc()).limit(1).with_for_update()).scalar_one_or_none()
            if channel_identity is None:
                presence = s.execute(sa_select(PresenceChannelBinding).where(
                    PresenceChannelBinding.companion_id == target.id,
                ).order_by(PresenceChannelBinding.created_at.asc()).limit(1)).scalar_one_or_none()
                if presence is None:
                    return {**result, "db_error": "presence_binding_not_ready"}
                channel_identity = CompanionChannelIdentity(
                    user_id=target.user_id, presence_channel_binding_id=presence.id,
                    companion_id=target.id, provider_bot_id=bot.id,
                    identity_status="ready", channel_status="active", revision=1,
                    identity_scope="discord_bot_identity", channel_display_name=target.name,
                    private_memory_visible_by_default=False, can_autonomously_message=False,
                    metadata_={"implementation_origin": "companion_room_binding", "source": "web"},
                )
                s.add(channel_identity); s.flush()
            else:
                channel_identity.channel_status = "active"; channel_identity.identity_status = "ready"
                channel_identity.revision += 1; channel_identity.updated_at = now
            bot.bot_display_name = bot.bot_display_name or bot_key
            bot.token_status = "configured"; bot.updated_at = now
            if app_id: bot.safe_metadata_json = {**(bot.safe_metadata_json or {}), "app_id": app_id}
            s.commit(); s.refresh(channel_identity)
            result.update({
                "bot_identity_id": str(bot.id), "companion_channel_identity_id": str(channel_identity.id),
                "identity_revision": channel_identity.revision, "source": "db", "persistent": True,
                "dependencies_paused": dependency_action == "pause",
            })
    except Exception as exc:
        logger.exception("DB Bot/Companion bind failed")
        return {**result, "db_error": type(exc).__name__, "persistent": False}

    # Runtime fallback mirrors a successful DB commit only; it is never a write fallback.
    bindings = _load_runtime_bindings(); bindings[bot_key] = companion_id
    try:
        BINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        BINDINGS_PATH.write_text(json.dumps(bindings, indent=2), encoding="utf-8")
    except Exception:
        logger.warning("Runtime binding mirror could not be updated for %s", bot_key)
    return result


def _safe_identity_projection(identity) -> dict[str, Any] | None:
    if identity is None:
        return None
    return {
        "id": str(identity.id), "companion_id": str(identity.companion_id),
        "revision": identity.revision, "status": identity.channel_status,
    }


async def route_discord_message(
    bot_key: str,
    author_id: str,
    author_name: str,
    content: str,
    channel_id: str,
    guild_id: str,
) -> dict[str, Any]:
    """Route a Discord message through the Echora conversation pipeline."""
    result = resolve_companion_id(bot_key)
    if not result["resolved"]:
        return {
            "error": result.get("reason", "no_companion_bound"),
            "reply": None,
            "diagnosis": result,
        }

    companion_id = result["companion_id"]

    # Normalize input: strip Discord mention syntax
    normalized_content = _normalize_content(content)
    conv_key = _make_conv_key(companion_id, channel_id, author_id)

    logger.info(
        f"[{bot_key}] bridge: raw_len={len(content)} normalized_len={len(normalized_content)} "
        f"companion_id={companion_id[:8]} content_logged=false"
    )
    conv_id = _conversation_map.get(conv_key)

    # Create conversation if needed
    client = _get_client()
    backend_url = f"http://127.0.0.1:{settings.BACKEND_PORT}/api/v1"

    if not conv_id:
        try:
            resp = client.post(
                f"{backend_url}/conversations",
                json={
                    "user_id": "4a4f3806-0d3e-4ab1-80ed-51f93b60aa80",
                    "companion_id": companion_id,
                    "title": f"Discord: {author_name}",
                    "mode_key": "project",
                },
            )
            if resp.status_code == 200:
                conv_id = resp.json().get("data", {}).get("id")
                if conv_id:
                    _conversation_map[conv_key] = conv_id
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            return {"error": str(e), "reply": "I couldn't start a conversation right now."}

    if not conv_id:
        return {"error": "no_conversation", "reply": "I couldn't prepare a conversation for you."}

    # Call /run
    try:
        resp = client.post(
            f"{backend_url}/conversations/{conv_id}/run",
            json={
                "companion_id": companion_id,
                "content": normalized_content,
                "mode_key": "project",
            },
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            assistant = data.get("assistant_message", {})
            reply = assistant.get("content", "") if assistant else ""
            return {
                "reply": reply[:2000],  # Discord 2000 char limit
                "conversation_id": conv_id,
                "trace_run_id": data.get("trace", {}).get("trace_run_id"),
                "companion_id": companion_id,
            }
        else:
            logger.error(f"/run failed: {resp.status_code}")
            return {"error": f"run_failed_{resp.status_code}", "reply": "I'm having trouble thinking right now."}
    except Exception as e:
        logger.error(f"Conversation run error: {e}")
        return {"error": str(e), "reply": "I couldn't process that message."}


async def route_discord_dm(
    *,
    bot_key: str,
    author_id: str,
    author_name: str,
    content: str,
    channel_id: str,
    message_id: str,
) -> dict[str, Any]:
    """Run the durable Discord DM DM path without blocking the Gateway heartbeat."""
    try:
        return await asyncio.to_thread(
            discord_dm_service.route_inbound_dm,
            bot_key=bot_key,
            author_id=author_id,
            author_name=author_name,
            content=content,
            channel_id=channel_id,
            message_id=message_id,
        )
    except discord_dm_service.DiscordDmError as exc:
        logger.warning("[%s] DM route blocked code=%s retryable=%s", bot_key, exc.code, exc.retryable)
        return {"error": exc.code, "error_message": exc.message, "retryable": exc.retryable, "reply": None}
