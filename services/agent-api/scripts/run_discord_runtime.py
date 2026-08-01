"""Run the Echora Discord Gateway and durable DM delivery worker."""

import asyncio
import logging
import os
import re
import signal
import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import discord_dm_service, discord_room_service
from app.services.discord_conversation_bridge import route_discord_dm
from app.services.discord_gateway_client import DiscordGatewayRuntime, resolve_role_mention


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("discord_runtime")

DISCORD_API = "https://discord.com/api/v10"
runtime = DiscordGatewayRuntime()

_BINDING_COMMAND = {
    "name": "echora-binding",
    "description": "查看或调整这位 Companion 的 Discord 私信连续性",
    "dm_permission": True,
    "options": [
        {"type": 1, "name": "status", "description": "查看当前绑定"},
        {"type": 1, "name": "list", "description": "列出可切换的 Web Conversation"},
        {"type": 1, "name": "new", "description": "新建并切换 Web Conversation"},
        {
            "type": 1,
            "name": "switch",
            "description": "切换到指定 Web Conversation",
            "options": [{"type": 3, "name": "conversation_id", "description": "搜索并选择 Web Conversation", "required": True, "autocomplete": True}],
        },
        {"type": 1, "name": "pause", "description": "暂停 Discord 私信回复"},
        {"type": 1, "name": "resume", "description": "恢复 Discord 私信回复"},
        {"type": 1, "name": "revoke", "description": "撤销并取消待发送回复"},
    ],
}

_ROOM_COMMAND = {
    "name": "echora-room",
    "description": "查看当前 Discord 频道与 Echora 聊天室连续性",
    "dm_permission": False,
    "options": [
        {"type": 1, "name": "status", "description": "查看频道绑定、策略与共同对话状态"},
        {"type": 1, "name": "members", "description": "查看逻辑参与 Bot 与 Companion 映射"},
        {
            "type": 1,
            "name": "switch",
            "description": "切换到 roster 完全一致且未占用的 Web 聊天室",
            "options": [{"type": 3, "name": "room_id", "description": "搜索并选择 Web 聊天室", "required": True, "autocomplete": True}],
        },
        {"type": 1, "name": "pause", "description": "暂停此频道的 Companion 回复"},
        {"type": 1, "name": "resume", "description": "恢复此频道的 Companion 回复"},
    ],
}


async def send_discord_reply(bot_key: str, channel_id: str, content: str) -> dict:
    """Send one real provider message and return a structured delivery result."""
    bot = runtime._bots.get(bot_key)
    if bot is None:
        return {"ok": False, "error_code": "bot_not_loaded", "retryable": True}
    if not content.strip():
        return {"ok": False, "error_code": "empty_content", "retryable": False}
    safe_content = content[:2000]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{DISCORD_API}/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {bot.token}", "Content-Type": "application/json"},
                json={"content": safe_content},
            )
        if response.status_code == 200:
            provider_message_id = str((response.json() or {}).get("id") or "")
            logger.info(
                "[%s] Discord reply delivered channel_hash=%s",
                bot_key,
                discord_dm_service.hash_provider_ref(channel_id)[:12],
            )
            return {"ok": True, "provider_message_id": provider_message_id}
        retry_after = None
        if response.status_code == 429:
            try:
                retry_after = max(1, int(float((response.json() or {}).get("retry_after", 1))))
            except (TypeError, ValueError):
                retry_after = 1
        logger.warning(
            "[%s] Discord reply failed status=%s body_logged=false",
            bot_key,
            response.status_code,
        )
        return {
            "ok": False,
            "error_code": f"discord_http_{response.status_code}",
            "retryable": response.status_code == 429 or response.status_code >= 500,
            "retry_after_seconds": retry_after,
        }
    except Exception as exc:
        logger.error("[%s] Discord transport error type=%s", bot_key, type(exc).__name__)
        return {"ok": False, "error_code": "discord_transport_error", "retryable": True}


async def drain_dm_outbox(bot_key: str) -> None:
    worker_id = f"discord-runtime:{os.getpid()}:{bot_key}"
    claimed = await asyncio.to_thread(
        discord_dm_service.claim_due_deliveries,
        bot_key,
        worker_id,
    )
    for delivery in claimed:
        result = await send_discord_reply(bot_key, delivery["channel_id"], delivery["content"])
        delivery_id = uuid.UUID(delivery["id"])
        if result.get("ok"):
            await asyncio.to_thread(
                discord_dm_service.mark_delivered,
                delivery_id,
                result.get("provider_message_id") or f"missing-provider-ref:{delivery['id']}",
            )
        else:
            await asyncio.to_thread(
                discord_dm_service.mark_delivery_failed,
                delivery_id,
                error_code=result.get("error_code", "discord_delivery_failed"),
                error_summary="Discord provider delivery failed; response body was not persisted.",
                retryable=bool(result.get("retryable")),
                retry_after_seconds=result.get("retry_after_seconds"),
            )


async def drain_room_outbox(bot_key: str) -> None:
    worker_id = f"discord-room-runtime:{os.getpid()}:{bot_key}"
    claimed = await asyncio.to_thread(discord_room_service.claim_due_deliveries, bot_key, worker_id)
    for delivery in claimed:
        result = await send_discord_reply(bot_key, delivery["channel_id"], delivery["content"])
        delivery_id = uuid.UUID(delivery["id"])
        if result.get("ok"):
            await asyncio.to_thread(
                discord_room_service.mark_delivered,
                delivery_id,
                result.get("provider_message_id") or f"missing-provider-ref:{delivery['id']}",
            )
        else:
            await asyncio.to_thread(
                discord_room_service.mark_delivery_failed,
                delivery_id,
                error_code=result.get("error_code", "discord_delivery_failed"),
                error_summary="Discord provider delivery failed; response body was not persisted.",
                retryable=bool(result.get("retryable")),
                retry_after_seconds=result.get("retry_after_seconds"),
            )


async def outbox_worker() -> None:
    """Poll every bot independently so one failed delivery cannot stop the runtime."""
    while True:
        try:
            await asyncio.to_thread(discord_room_service.reconcile_pending_ingresses)
        except Exception as exc:
            logger.error("Room ingress reconciliation isolated failure type=%s", type(exc).__name__)
        for bot_key in list(runtime._bots):
            try:
                await drain_dm_outbox(bot_key)
                await drain_room_outbox(bot_key)
            except Exception as exc:
                logger.error("[%s] Outbox task isolated failure type=%s", bot_key, type(exc).__name__)
        await asyncio.sleep(2)


async def register_binding_commands() -> None:
    """Idempotently register DM and Room deterministic commands for each app."""
    for bot_key, bot in runtime._bots.items():
        if not bot.app_id:
            logger.warning("[%s] Slash command registration skipped: application ID missing", bot_key)
            continue
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for command in (_BINDING_COMMAND, _ROOM_COMMAND):
                    response = await client.post(
                        f"{DISCORD_API}/applications/{bot.app_id}/commands",
                        headers={"Authorization": f"Bot {bot.token}", "Content-Type": "application/json"},
                        json=command,
                    )
                    if response.status_code in {200, 201}:
                        logger.info("[%s] Slash command registered name=%s", bot_key, command["name"])
                    else:
                        logger.warning("[%s] Slash command registration failed name=%s status=%s body_logged=false", bot_key, command["name"], response.status_code)
        except Exception as exc:
            logger.warning("[%s] Slash command registration transport failure type=%s", bot_key, type(exc).__name__)


async def on_discord_interaction(bot_key: str, data: dict) -> None:
    """Handle deterministic DM binding and Guild Room read commands without an LLM."""
    command_name = (data.get("data") or {}).get("name")
    if data.get("guild_id") and command_name == "echora-room":
        options = (data.get("data") or {}).get("options") or []
        action_option = options[0] if options else {"name": "status", "options": []}
        action = str(action_option.get("name") or "status")
        values = {item.get("name"): item.get("value") for item in action_option.get("options") or []}
        bot = runtime._bots.get(bot_key)
        if bot is None:
            return
        if data.get("type") == 4:
            focused = next((item for item in action_option.get("options") or [] if item.get("focused")), {})
            choices = await asyncio.to_thread(
                discord_room_service.list_room_switch_choices,
                bot_key=bot_key,
                guild_id=str(data.get("guild_id") or ""),
                channel_id=str(data.get("channel_id") or ""),
                query=str(focused.get("value") or ""),
            )
            await _respond_to_interaction(bot_key, bot, data, {"type": 8, "data": {"choices": choices}})
            return
        if action not in {"status", "members", "switch", "pause", "resume"}:
            action = "status"
        message = await asyncio.to_thread(
            discord_room_service.handle_room_command,
            bot_key=bot_key,
            guild_id=str(data.get("guild_id") or ""),
            channel_id=str(data.get("channel_id") or ""),
            action=action,
            room_id=values.get("room_id"),
        )
        await _respond_to_interaction(bot_key, bot, data, {"type": 4, "data": {"content": message[:1900], "flags": 64}})
        return
    if data.get("guild_id") or command_name != "echora-binding":
        return
    user = data.get("user") or (data.get("member") or {}).get("user") or {}
    author_id = str(user.get("id") or "")
    options = (data.get("data") or {}).get("options") or []
    action_option = options[0] if options else {"name": "status", "options": []}
    action = str(action_option.get("name") or "status")
    values = {item.get("name"): item.get("value") for item in action_option.get("options") or []}
    bot = runtime._bots.get(bot_key)
    if bot is None:
        return
    if data.get("type") == 4:
        focused = next((item for item in action_option.get("options") or [] if item.get("focused")), {})
        choices = await asyncio.to_thread(
            discord_dm_service.list_binding_conversation_choices,
            bot_key=bot_key,
            author_id=author_id,
            query=str(focused.get("value") or ""),
        )
        await _respond_to_interaction(bot_key, bot, data, {"type": 8, "data": {"choices": choices}})
        return
    if action not in {"status", "list", "new", "switch", "pause", "resume", "revoke"}:
        action = "status"
    message = await asyncio.to_thread(
        discord_dm_service.handle_binding_command,
        bot_key=bot_key,
        author_id=author_id,
        action=action,
        conversation_id=values.get("conversation_id"),
    )
    await _respond_to_interaction(
        bot_key,
        bot,
        data,
        {"type": 4, "data": {"content": message[:1900], "flags": 64}},
    )


async def _respond_to_interaction(bot_key: str, bot, data: dict, payload: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{DISCORD_API}/interactions/{data.get('id')}/{data.get('token')}/callback",
                headers={"Authorization": f"Bot {bot.token}", "Content-Type": "application/json"},
                json=payload,
            )
        if response.status_code not in {200, 204}:
            logger.warning("[%s] Interaction response failed status=%s body_logged=false", bot_key, response.status_code)
    except Exception as exc:
        logger.warning("[%s] Interaction response transport failure type=%s", bot_key, type(exc).__name__)


async def on_discord_message(bot_key: str, data: dict) -> None:
    author = data.get("author", {})
    content = str(data.get("content") or "")
    channel_id = str(data.get("channel_id") or "")
    guild_id = str(data.get("guild_id") or "")
    message_id = str(data.get("id") or "")
    author_id = str(author.get("id") or "")
    if author.get("bot") or not content.strip():
        return
    logger.info(
        "[%s] MESSAGE_CREATE msg_hash=%s scope=%s content_len=%s content_logged=false",
        bot_key,
        discord_dm_service.hash_provider_ref(message_id)[:12] if message_id else "missing",
        "guild" if guild_id else "dm",
        len(content),
    )

    if not guild_id:
        result = await route_discord_dm(
            bot_key=bot_key,
            author_id=author_id,
            author_name=str(author.get("global_name") or author.get("username") or "Discord 用户"),
            content=content,
            channel_id=channel_id,
            message_id=message_id,
        )
        if result.get("delivery"):
            await drain_dm_outbox(bot_key)
        elif result.get("error"):
            logger.warning("[%s] DM produced no outbound delivery code=%s", bot_key, result["error"])
        return

    mention_ids = {str(item.get("id") or "") for item in data.get("mentions", [])}
    mentioned_bot_keys = {
        key for key, candidate in runtime._bots.items()
        if str(candidate.bot_meta.get("bot_user_id") or "") in mention_ids
    }
    mentioned_bot_keys.update(
        key for key in (resolve_role_mention(str(role_id)) for role_id in data.get("mention_roles", [])) if key
    )
    normalized = re.sub(r"<@!?\d+>|<@&\d+>|<#\d+>", "", content).strip()
    result = await asyncio.to_thread(
        discord_room_service.route_channel_inbound,
        observed_bot_key=bot_key,
        author_id=author_id,
        author_name=str(author.get("global_name") or author.get("username") or "Discord 用户"),
        content=normalized,
        channel_id=channel_id,
        guild_id=guild_id,
        message_id=message_id,
        mentioned_bot_keys=sorted(mentioned_bot_keys),
    )
    if result.get("ignored"):
        logger.info("[%s] Guild event ignored reason=%s", bot_key, result.get("reason"))
        return
    for delivery_bot_key in list(runtime._bots):
        await drain_room_outbox(delivery_bot_key)


async def main() -> int:
    logger.info("=== Echora Discord Runtime ===")
    bots = runtime.load_bots()
    if not bots:
        logger.error("No bots loaded. Check the local registry and token environment references.")
        return 1
    logger.info("Loaded %s bot(s): %s", len(bots), ", ".join(bots))
    await register_binding_commands()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: None)
        except NotImplementedError:
            pass

    delivery_task = asyncio.create_task(outbox_worker())
    try:
        await runtime.connect_all(on_message=on_discord_message, on_interaction=on_discord_interaction)
    except KeyboardInterrupt:
        pass
    finally:
        delivery_task.cancel()
        await asyncio.gather(delivery_task, return_exceptions=True)
        await runtime.disconnect_all()
        logger.info("All bots disconnected.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
