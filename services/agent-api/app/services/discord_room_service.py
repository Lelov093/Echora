"""Discord Room durable Discord text-channel to Companion Room coordination."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select, text

from app.db.models import (
    BadCase,
    ChannelBotRegistry,
    ChannelFailureEvent,
    Companion,
    CompanionRoomTurn,
    CoPresenceParticipant,
    CoPresenceSession,
    Conversation,
    DiscordChannelBotMembership,
    DiscordChannelDelivery,
    DiscordChannelIngress,
    DiscordChannelRoomBinding,
    DiscordGuild,
    DiscordTextChannel,
    Message,
    SharedScene,
    SharedSceneEvent,
)
from app.services import companion_room_channel_service, companion_room_turn_service
from app.services.conversation_service import get_session
from app.services.discord_dm_service import hash_provider_ref


CONTRACT_VERSION = "discord-room.v1"
TERMINAL_DELIVERY_STATES = {"delivered", "failed", "cancelled", "suppressed"}
TERMINAL_INGRESS_STATES = {"completed", "partial_failed", "suppressed", "failed", "ignored"}
MAX_ATTEMPTS = 5
SHARED_SCENE_EVENT_TYPE = "scene_note"
SHARED_SCENE_EVENT_SOURCE = "system"


class DiscordRoomError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def route_channel_inbound(
    *,
    observed_bot_key: str,
    guild_id: str,
    channel_id: str,
    message_id: str,
    author_id: str,
    author_name: str,
    content: str,
    mentioned_bot_keys: list[str],
) -> dict[str, Any]:
    """Claim one provider event once, run the Room, and queue correct-Bot replies."""
    values = [observed_bot_key, guild_id, channel_id, message_id, author_id]
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise DiscordRoomError("DISCORD_ROOM_EVENT_INVALID", "Discord Channel event is missing routing identity.")
    normalized = content.strip()
    if not normalized:
        normalized = "（Discord 用户提及了伙伴，但没有附加文字。）"
    if len(normalized) > 20_000:
        raise DiscordRoomError("DISCORD_ROOM_CONTENT_TOO_LONG", "Discord Channel message exceeds the Room limit.")

    guild_hash = hash_provider_ref(guild_id)
    channel_hash = hash_provider_ref(channel_id)
    message_hash = hash_provider_ref(message_id)
    author_hash = hash_provider_ref(author_id)
    mentioned_keys = sorted({str(item) for item in mentioned_bot_keys if item})
    request_hash = _request_hash(channel_hash, message_hash, author_hash, normalized, mentioned_keys)
    lock_id = int.from_bytes(hashlib.sha256(f"discord-room:{guild_hash}:{channel_hash}:{message_hash}".encode()).digest()[:8], "big", signed=True)

    with get_session() as s:
        s.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        existing = s.execute(select(DiscordChannelIngress).where(
            DiscordChannelIngress.provider_guild_ref_hash == guild_hash,
            DiscordChannelIngress.provider_channel_ref_hash == channel_hash,
            DiscordChannelIngress.provider_message_ref_hash == message_hash,
        )).scalar_one_or_none()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise DiscordRoomError("DISCORD_ROOM_IDEMPOTENCY_CONFLICT", "Provider message identity was reused with different content.")
            projection = _ingress_dict(s, existing)
            projection["idempotent_replay"] = True
            return projection

        guild = s.execute(select(DiscordGuild).where(
            DiscordGuild.provider_guild_ref_hash == guild_hash,
            DiscordGuild.guild_status == "active",
        )).scalar_one_or_none()
        channel = s.execute(select(DiscordTextChannel).where(
            DiscordTextChannel.provider_channel_ref_hash == channel_hash,
            DiscordTextChannel.channel_status == "active",
        )).scalar_one_or_none()
        if guild is None or channel is None or channel.discord_guild_id != guild.id:
            return {"ignored": True, "reason": "channel_not_registered", "idempotent_replay": False}
        binding = s.execute(select(DiscordChannelRoomBinding).where(
            DiscordChannelRoomBinding.discord_text_channel_id == channel.id,
            DiscordChannelRoomBinding.binding_status.in_(["active", "paused", "conflict_paused"]),
        ).order_by(DiscordChannelRoomBinding.created_at.desc()).limit(1)).scalar_one_or_none()
        if binding is None:
            return {"ignored": True, "reason": "channel_not_bound", "idempotent_replay": False}

        membership_rows = list(s.execute(
            select(DiscordChannelBotMembership, ChannelBotRegistry)
            .join(ChannelBotRegistry, ChannelBotRegistry.id == DiscordChannelBotMembership.provider_bot_id)
            .where(
                DiscordChannelBotMembership.discord_channel_room_binding_id == binding.id,
                DiscordChannelBotMembership.membership_status == "active",
            )
        ).all())
        by_key = {bot.bot_key: (membership, bot) for membership, bot in membership_rows}
        if observed_bot_key not in by_key:
            return {"ignored": True, "reason": "physical_bot_not_in_logical_roster", "idempotent_replay": False}

        conversation = s.execute(select(Conversation).where(
            Conversation.co_presence_session_id == binding.co_presence_session_id,
            Conversation.deleted_at.is_(None),
        ).order_by(Conversation.created_at.asc()).limit(1)).scalar_one_or_none()
        if conversation is None:
            raise DiscordRoomError("DISCORD_ROOM_CONVERSATION_MISSING", "Bound Room Conversation is unavailable.")

        selected_ids = [
            str(by_key[key][0].companion_id)
            for key in mentioned_keys if key in by_key
        ]
        binding_ready = binding.binding_status == "active" and channel.permission_status == "ready"
        explicit_required = binding.mention_policy != "coordinator_managed" or not binding_ready
        if binding.mention_policy == "observe_only":
            selected_ids = []
            explicit_required = True
        ingress = DiscordChannelIngress(
            user_id=binding.user_id,
            discord_channel_room_binding_id=binding.id,
            discord_text_channel_id=channel.id,
            co_presence_session_id=binding.co_presence_session_id,
            conversation_id=conversation.id,
            provider_guild_ref_hash=guild_hash,
            provider_channel_ref_hash=channel_hash,
            provider_message_ref_hash=message_hash,
            external_author_ref_hash=author_hash,
            author_display_name=(author_name or "Discord user")[:200],
            observed_bot_key=observed_bot_key[:120],
            ingress_status="processing",
            request_hash=request_hash,
            mentioned_bot_keys_json=mentioned_keys,
            selected_companion_ids_json=selected_ids,
            evidence_json={
                "contract_version": CONTRACT_VERSION,
                "binding_status": binding.binding_status,
                "permission_status": channel.permission_status,
                "mention_policy": binding.mention_policy,
                "logical_roster_bot_count": len(by_key),
                "unmapped_mentions_ignored": [key for key in mentioned_keys if key not in by_key],
                "raw_provider_payload_persisted": False,
                "channel_memory_policy": "review_required",
            },
            received_at=_now(),
            metadata_={"implementation_origin": "discord_room", "terminal_monotonic": True},
        )
        s.add(ingress)
        s.commit()
        ingress_id = ingress.id
        room_id = binding.co_presence_session_id

    try:
        turn = companion_room_turn_service.execute_room_turn(room_id, {
            "content": normalized,
            "target_companion_ids": selected_ids,
            "idempotency_key": f"discord-channel:{message_hash}",
            "source": "discord_channel",
            "require_explicit_targets": explicit_required,
            "source_metadata": {
                "discord_channel_ingress_id": str(ingress_id),
                "discord_message_ref_hash": message_hash,
                "channel_memory_policy": "review_required",
                "external_author_display_name": (author_name or "Discord user")[:200],
            },
        })
        _complete_ingress(ingress_id, turn, queue_deliveries=binding_ready)
    except Exception as exc:
        _fail_ingress(ingress_id, exc)
    with get_session() as s:
        return _ingress_dict(s, s.get(DiscordChannelIngress, ingress_id))


def claim_due_deliveries(bot_key: str, worker_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    now = _now()
    lease_until = now + timedelta(seconds=45)
    with get_session() as s:
        rows = list(s.execute(
            select(DiscordChannelDelivery)
            .join(ChannelBotRegistry, ChannelBotRegistry.id == DiscordChannelDelivery.provider_bot_id)
            .join(DiscordChannelRoomBinding, DiscordChannelRoomBinding.id == DiscordChannelDelivery.discord_channel_room_binding_id)
            .where(
                ChannelBotRegistry.bot_key == bot_key,
                DiscordChannelRoomBinding.binding_status == "active",
                DiscordChannelDelivery.delivery_status.in_(["queued", "retry_scheduled", "leased"]),
                or_(DiscordChannelDelivery.next_attempt_at.is_(None), DiscordChannelDelivery.next_attempt_at <= now),
                or_(DiscordChannelDelivery.lease_expires_at.is_(None), DiscordChannelDelivery.lease_expires_at <= now),
            )
            .order_by(DiscordChannelDelivery.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        ).scalars())
        claimed = []
        for row in rows:
            if row.delivery_status in TERMINAL_DELIVERY_STATES:
                continue
            ingress = s.get(DiscordChannelIngress, row.discord_channel_ingress_id)
            binding = s.get(DiscordChannelRoomBinding, row.discord_channel_room_binding_id)
            channel = s.get(DiscordTextChannel, binding.discord_text_channel_id) if binding else None
            message = s.get(Message, row.assistant_message_id)
            if ingress is None or channel is None or message is None or channel.permission_status != "ready":
                _terminal_delivery_failure(row, "delivery_reference_or_permission_missing", "Channel delivery reference or permission is unavailable.")
                continue
            row.delivery_status = "leased"
            row.attempt_count += 1
            row.lease_owner = worker_id
            row.lease_expires_at = lease_until
            row.updated_at = now
            claimed.append({
                "id": str(row.id), "bot_key": bot_key,
                "channel_id": channel.provider_channel_ref,
                "content": message.content[:2000],
                "attempt_count": row.attempt_count, "max_attempts": row.max_attempts,
            })
        s.commit()
        return claimed


def mark_delivered(delivery_id: uuid.UUID, provider_message_id: str) -> dict[str, Any] | None:
    with get_session() as s:
        row = s.get(DiscordChannelDelivery, delivery_id)
        if row is None:
            return None
        if row.delivery_status == "delivered" or row.delivery_status in {"failed", "cancelled", "suppressed"}:
            return _delivery_dict(row)
        now = _now()
        row.delivery_status = "delivered"
        row.provider_message_ref_hash = hash_provider_ref(provider_message_id)
        row.delivered_at = now
        row.next_attempt_at = None
        row.lease_owner = None
        row.lease_expires_at = None
        row.last_error_code = None
        row.last_error_summary = None
        row.error_json = {}
        row.updated_at = now
        s.commit()
        return _delivery_dict(row)


def mark_delivery_failed(
    delivery_id: uuid.UUID,
    *,
    error_code: str,
    error_summary: str,
    retryable: bool,
    retry_after_seconds: int | None = None,
) -> dict[str, Any] | None:
    with get_session() as s:
        row = s.get(DiscordChannelDelivery, delivery_id)
        if row is None:
            return None
        if row.delivery_status in TERMINAL_DELIVERY_STATES:
            return _delivery_dict(row)
        now = _now()
        can_retry = retryable and row.attempt_count < row.max_attempts
        row.delivery_status = "retry_scheduled" if can_retry else "failed"
        delay = retry_after_seconds if retry_after_seconds is not None else min(300, 2 ** max(1, row.attempt_count))
        row.next_attempt_at = now + timedelta(seconds=max(1, delay)) if can_retry else None
        row.lease_owner = None
        row.lease_expires_at = None
        row.last_error_code = error_code[:120]
        row.last_error_summary = error_summary[:500]
        row.error_json = {"retryable": can_retry, "attempt": row.attempt_count}
        row.updated_at = now
        _append_delivery_failure_evidence(s, row, can_retry)
        if not can_retry:
            _append_delivery_bad_case(s, row)
        s.commit()
        return _delivery_dict(row)


def command_status(*, bot_key: str, guild_id: str, channel_id: str) -> str:
    guild_hash, channel_hash = hash_provider_ref(guild_id), hash_provider_ref(channel_id)
    with get_session() as s:
        bundle = _command_binding(s, guild_hash, channel_hash)
        if bundle is None:
            return "此频道尚未绑定 Echora 聊天室。"
        binding, channel = bundle
        if not _command_bot_in_roster(s, binding.id, bot_key):
            return "当前 Bot 未进入此频道的逻辑 roster，命令已忽略。"
        conversation_id = _conversation_id_for_room(s, binding.co_presence_session_id)
        room = s.get(Conversation, conversation_id) if conversation_id else None
        return (
            f"聊天室绑定：{binding.binding_status} · 策略 {binding.mention_policy}\n"
            f"频道：#{channel.channel_display_name} · Room {str(binding.co_presence_session_id)[:8]}\n"
            f"共同对话：{room.title if room else '不可用'}"
        )


def command_members(*, bot_key: str, guild_id: str, channel_id: str) -> str:
    with get_session() as s:
        bundle = _command_binding(s, hash_provider_ref(guild_id), hash_provider_ref(channel_id))
        if bundle is None:
            return "此频道尚未绑定 Echora 聊天室。"
        binding, _ = bundle
        if not _command_bot_in_roster(s, binding.id, bot_key):
            return "当前 Bot 未进入此频道的逻辑 roster，命令已忽略。"
        rows = list(s.execute(
            select(DiscordChannelBotMembership, ChannelBotRegistry, Companion)
            .join(ChannelBotRegistry, ChannelBotRegistry.id == DiscordChannelBotMembership.provider_bot_id)
            .join(Companion, Companion.id == DiscordChannelBotMembership.companion_id)
            .where(DiscordChannelBotMembership.discord_channel_room_binding_id == binding.id)
            .order_by(DiscordChannelBotMembership.created_at.asc())
        ).all())
        lines = [f"{bot.bot_display_name} → {companion.name} · {membership.membership_status}/{membership.participation_mode}" for membership, bot, companion in rows]
        return "当前逻辑参与 Bot：\n" + ("\n".join(lines) if lines else "无")


def list_room_switch_choices(*, bot_key: str, guild_id: str, channel_id: str, query: str = "") -> list[dict[str, str]]:
    """Return only unoccupied, owner-scoped Rooms with the exact logical Companion roster."""
    with get_session() as s:
        bundle = _command_binding(s, hash_provider_ref(guild_id), hash_provider_ref(channel_id))
        if bundle is None:
            return []
        binding, _ = bundle
        if not _command_bot_in_roster(s, binding.id, bot_key):
            return []
        mapped_ids = set(s.execute(select(DiscordChannelBotMembership.companion_id).where(
            DiscordChannelBotMembership.discord_channel_room_binding_id == binding.id,
            DiscordChannelBotMembership.membership_status.in_(["active", "inactive"]),
        )).scalars().all())
        occupied_room_ids = set(s.execute(select(DiscordChannelRoomBinding.co_presence_session_id).where(
            DiscordChannelRoomBinding.id != binding.id,
            DiscordChannelRoomBinding.binding_status.in_(["active", "paused", "conflict_paused"]),
        )).scalars().all())
        rooms = list(s.execute(select(CoPresenceSession).where(
            CoPresenceSession.user_id == binding.user_id,
            CoPresenceSession.session_source == "companion_home",
            CoPresenceSession.session_status == "active",
            CoPresenceSession.id != binding.co_presence_session_id,
        ).order_by(CoPresenceSession.updated_at.desc()).limit(100)).scalars().all())
        needle = query.strip().casefold()
        choices = []
        for room in rooms:
            if room.id in occupied_room_ids:
                continue
            participant_ids = set(s.execute(select(CoPresenceParticipant.participant_companion_id).where(
                CoPresenceParticipant.co_presence_session_id == room.id,
                CoPresenceParticipant.participant_type == "companion",
                CoPresenceParticipant.join_status == "active",
            )).scalars().all())
            if participant_ids != mapped_ids:
                continue
            title = room.session_title or "未命名聊天室"
            if needle and needle not in title.casefold() and needle not in str(room.id).casefold():
                continue
            choices.append({"name": f"{title[:76]} · {str(room.id)[:8]}", "value": str(room.id)})
            if len(choices) >= 25:
                break
        return choices


def handle_room_command(
    *, bot_key: str, guild_id: str, channel_id: str, action: str, room_id: str | None = None,
) -> str:
    """Apply deterministic Channel/Room continuity commands without invoking an LLM."""
    if action == "status":
        return command_status(bot_key=bot_key, guild_id=guild_id, channel_id=channel_id)
    if action == "members":
        return command_members(bot_key=bot_key, guild_id=guild_id, channel_id=channel_id)
    try:
        with get_session() as s:
            bundle = _command_binding(s, hash_provider_ref(guild_id), hash_provider_ref(channel_id))
            if bundle is None:
                return "此频道尚未绑定 Echora 聊天室。"
            binding, _ = bundle
            if not _command_bot_in_roster(s, binding.id, bot_key):
                return "当前 Bot 未进入此频道的逻辑 roster，命令已忽略。"
            binding_id, revision = binding.id, binding.revision
        if action in {"pause", "resume"}:
            updated = companion_room_channel_service.transition_channel_binding(binding_id, action, revision, "discord_command")
            verb = "暂停" if action == "pause" else "恢复"
            return f"频道绑定已{verb} · revision {updated['revision']}。"
        if action == "switch":
            if not room_id:
                return "请选择一个 roster 完全一致且未被占用的聊天室。"
            updated = companion_room_channel_service.switch_channel_room(binding_id, uuid.UUID(room_id), revision)
            return f"频道已切换到 Room {updated['room_id'][:8]} · #{updated.get('channel_display_name') or 'Discord'}。"
        return "不支持的聊天室命令。"
    except (ValueError, companion_room_channel_service.CompanionRoomChannelError) as exc:
        code = getattr(exc, "code", "DISCORD_ROOM_COMMAND_INVALID")
        return f"操作未完成（{code}）。请刷新 Web 端绑定状态后重试。"


def list_recent_ingresses(room_id: uuid.UUID, *, limit: int = 30) -> list[dict[str, Any]]:
    with get_session() as s:
        rows = list(s.execute(select(DiscordChannelIngress).where(
            DiscordChannelIngress.co_presence_session_id == room_id,
        ).order_by(DiscordChannelIngress.created_at.desc()).limit(limit)).scalars())
        return [_ingress_dict(s, row) for row in rows]


def reconcile_pending_ingresses(*, limit: int = 20) -> int:
    """Finish durable Channel ingresses whose Room Turn reached a terminal state."""
    with get_session() as s:
        rows = list(s.execute(select(DiscordChannelIngress).where(
            DiscordChannelIngress.ingress_status.in_(["received", "processing"]),
        ).order_by(DiscordChannelIngress.received_at.asc()).limit(limit)).scalars().all())
        candidates = [(row.id, row.co_presence_session_id, f"discord-channel:{row.provider_message_ref_hash}") for row in rows]
    reconciled = 0
    for ingress_id, room_id, key in candidates:
        with get_session() as s:
            turn = s.execute(select(CompanionRoomTurn).where(
                CompanionRoomTurn.co_presence_session_id == room_id,
                CompanionRoomTurn.idempotency_key == key,
                CompanionRoomTurn.status.in_(["completed", "partial_failed", "suppressed", "failed", "cancelled"]),
            )).scalar_one_or_none()
            projection = companion_room_turn_service._project_turn(s, turn) if turn is not None else None
        if projection is None:
            continue
        _complete_ingress(ingress_id, projection, queue_deliveries=True)
        reconciled += 1
    return reconciled


def cancel_pending_deliveries(binding_id: uuid.UUID, *, reason: str) -> int:
    """Cancel only deliveries that have not entered an in-flight provider lease."""
    with get_session() as s:
        rows = list(s.execute(select(DiscordChannelDelivery).where(
            DiscordChannelDelivery.discord_channel_room_binding_id == binding_id,
            DiscordChannelDelivery.delivery_status.in_(["queued", "retry_scheduled"]),
        ).with_for_update()).scalars())
        now = _now()
        for row in rows:
            row.delivery_status = "cancelled"
            row.cancelled_at = now
            row.next_attempt_at = None
            row.lease_owner = None
            row.lease_expires_at = None
            row.last_error_code = reason[:120]
            row.last_error_summary = "Cancelled because the Discord Room binding is no longer active."
        s.commit()
        return len(rows)


def _complete_ingress(ingress_id: uuid.UUID, turn: dict[str, Any], *, queue_deliveries: bool) -> None:
    with get_session() as s:
        ingress = s.execute(select(DiscordChannelIngress).where(DiscordChannelIngress.id == ingress_id).with_for_update()).scalar_one()
        if ingress.ingress_status in TERMINAL_INGRESS_STATES:
            return
        ingress.room_turn_id = uuid.UUID(turn["id"])
        ingress.user_message_id = uuid.UUID(turn["user_message_id"])
        ingress.ingress_status = turn["status"] if turn["status"] in {"completed", "partial_failed", "suppressed", "failed"} else "failed"
        ingress.completed_at = _now()
        ingress.evidence_json = {
            **(ingress.evidence_json or {}),
            "room_turn_status": turn["status"],
            "room_turn_revision": turn["revision"],
            "selected_step_count": len(turn.get("steps") or []),
        }
        if queue_deliveries:
            for step_data in turn.get("steps") or []:
                if step_data.get("status") != "completed" or not step_data.get("assistant_message_id"):
                    continue
                step_id = uuid.UUID(step_data["id"])
                companion_id = uuid.UUID(step_data["companion_id"])
                membership = s.execute(select(DiscordChannelBotMembership).where(
                    DiscordChannelBotMembership.discord_channel_room_binding_id == ingress.discord_channel_room_binding_id,
                    DiscordChannelBotMembership.companion_id == companion_id,
                    DiscordChannelBotMembership.membership_status == "active",
                ).limit(1)).scalar_one_or_none()
                if membership is None:
                    ingress.error_json = {**(ingress.error_json or {}), "missing_bot_for_companion": str(companion_id)}
                    continue
                existing = s.execute(select(DiscordChannelDelivery).where(
                    DiscordChannelDelivery.discord_channel_ingress_id == ingress.id,
                    DiscordChannelDelivery.room_turn_step_id == step_id,
                )).scalar_one_or_none()
                if existing is None:
                    s.add(DiscordChannelDelivery(
                        user_id=ingress.user_id,
                        discord_channel_ingress_id=ingress.id,
                        discord_channel_room_binding_id=ingress.discord_channel_room_binding_id,
                        room_turn_step_id=step_id,
                        companion_id=companion_id,
                        provider_bot_id=membership.provider_bot_id,
                        assistant_message_id=uuid.UUID(step_data["assistant_message_id"]),
                        trace_run_id=uuid.UUID(step_data["trace_run_id"]) if step_data.get("trace_run_id") else None,
                        idempotency_key=f"discord-channel:{ingress.provider_message_ref_hash}:{step_id}",
                        delivery_status="queued",
                        max_attempts=MAX_ATTEMPTS,
                        next_attempt_at=_now(),
                        metadata_={"implementation_origin": "discord_room", "terminal_monotonic": True, "correct_bot_mapping": True},
                    ))
        s.commit()
    _safe_append_shared_scene_event(ingress_id)


def _fail_ingress(ingress_id: uuid.UUID, exc: Exception) -> None:
    with get_session() as s:
        ingress = s.execute(select(DiscordChannelIngress).where(DiscordChannelIngress.id == ingress_id).with_for_update()).scalar_one_or_none()
        if ingress is None or ingress.ingress_status in TERMINAL_INGRESS_STATES:
            return
        ingress.ingress_status = "failed"
        ingress.completed_at = _now()
        ingress.error_json = {
            "code": getattr(exc, "code", type(exc).__name__),
            "message": getattr(exc, "message", "Discord Room processing failed."),
        }
        s.commit()
    _safe_append_ingress_failure_event(ingress_id)


def _safe_append_ingress_failure_event(ingress_id: uuid.UUID) -> None:
    try:
        with get_session() as s:
            ingress = s.get(DiscordChannelIngress, ingress_id)
            if ingress is None:
                return
            binding = s.get(DiscordChannelRoomBinding, ingress.discord_channel_room_binding_id)
            channel = s.get(DiscordTextChannel, ingress.discord_text_channel_id)
            guild = s.get(DiscordGuild, channel.discord_guild_id) if channel else None
            if guild is None:
                return
            s.add(ChannelFailureEvent(
                provider_id=guild.provider_id,
                failure_type="discord_room_ingress",
                failure_status="recorded",
                safe_error_summary="Discord Room ingress failed after durable claim.",
                safe_error_json={"error_code": (ingress.error_json or {}).get("code"), "binding_id": str(binding.id) if binding else None},
                occurred_at=_now(),
                metadata_={"implementation_origin": "discord_room", "ingress_id": str(ingress.id)},
            ))
            s.commit()
    except Exception:
        return


def _append_shared_scene_event(s, ingress: DiscordChannelIngress) -> None:
    scene = s.execute(select(SharedScene).where(
        SharedScene.co_presence_session_id == ingress.co_presence_session_id,
    ).order_by(SharedScene.created_at.asc()).limit(1)).scalar_one_or_none()
    if scene is None:
        return
    existing = s.execute(select(SharedSceneEvent).where(
        SharedSceneEvent.metadata_["discord_channel_ingress_id"].astext == str(ingress.id),
    )).scalar_one_or_none()
    if existing is not None:
        return
    s.add(SharedSceneEvent(
        user_id=ingress.user_id,
        shared_scene_id=scene.id,
        co_presence_session_id=ingress.co_presence_session_id,
        event_type=SHARED_SCENE_EVENT_TYPE,
        event_source=SHARED_SCENE_EVENT_SOURCE,
        title="Discord Channel turn",
        content=None,
        visibility_scope="role_summary",
        triggers_shared_experience_candidate=False,
        event_payload_json={
            "ingress_id": str(ingress.id), "room_turn_id": str(ingress.room_turn_id) if ingress.room_turn_id else None,
            "status": ingress.ingress_status, "review_required": True, "raw_content_copied": False,
        },
        occurred_at=ingress.received_at,
        metadata_={"implementation_origin": "discord_room", "discord_channel_ingress_id": str(ingress.id)},
    ))


def _safe_append_shared_scene_event(ingress_id: uuid.UUID) -> None:
    """Shared evidence is review-gated and must never roll back ingress/outbox truth."""
    try:
        with get_session() as s:
            ingress = s.get(DiscordChannelIngress, ingress_id)
            if ingress is None:
                return
            _append_shared_scene_event(s, ingress)
            s.commit()
    except Exception as exc:
        try:
            with get_session() as s:
                ingress = s.execute(select(DiscordChannelIngress).where(
                    DiscordChannelIngress.id == ingress_id,
                ).with_for_update()).scalar_one_or_none()
                if ingress is not None:
                    ingress.evidence_json = {
                        **(ingress.evidence_json or {}),
                        "shared_scene_evidence": "failed",
                        "shared_scene_error_code": type(exc).__name__,
                    }
                    s.commit()
        except Exception:
            return


def _append_delivery_failure_evidence(s, row: DiscordChannelDelivery, retrying: bool) -> None:
    bot = s.get(ChannelBotRegistry, row.provider_bot_id)
    if bot is None:
        return
    s.add(ChannelFailureEvent(
        provider_id=bot.provider_id,
        provider_bot_id=bot.id,
        failure_type="discord_room_delivery",
        failure_status="retry_scheduled" if retrying else "recorded",
        safe_error_summary=row.last_error_summary or "Discord Room delivery failed.",
        safe_error_json={"error_code": row.last_error_code, "attempt": row.attempt_count, "retryable": retrying},
        occurred_at=_now(),
        metadata_={"implementation_origin": "discord_room", "delivery_id": str(row.id)},
    ))


def _append_delivery_bad_case(s, row: DiscordChannelDelivery) -> None:
    try:
        with s.begin_nested():
            ingress = s.get(DiscordChannelIngress, row.discord_channel_ingress_id)
            s.add(BadCase(
                user_id=row.user_id,
                companion_id=row.companion_id,
                conversation_id=ingress.conversation_id if ingress else None,
                message_id=row.assistant_message_id,
                trace_run_id=row.trace_run_id,
                type="other",
                title="Discord Room delivery exhausted retries",
                description=row.last_error_summary,
                severity="medium",
                status="open",
                regression_seed_json={"contract_version": CONTRACT_VERSION, "delivery_id": str(row.id), "error_code": row.last_error_code},
                metadata_={"implementation_origin": "discord_room", "source": "discord_room_delivery"},
            ))
            s.flush()
    except Exception:
        row.error_json = {**(row.error_json or {}), "bad_case_recording": "failed"}


def _terminal_delivery_failure(row: DiscordChannelDelivery, code: str, summary: str) -> None:
    row.delivery_status = "failed"
    row.last_error_code = code
    row.last_error_summary = summary
    row.next_attempt_at = None
    row.lease_owner = None
    row.lease_expires_at = None


def _command_binding(s, guild_hash: str, channel_hash: str):
    guild = s.execute(select(DiscordGuild).where(DiscordGuild.provider_guild_ref_hash == guild_hash)).scalar_one_or_none()
    channel = s.execute(select(DiscordTextChannel).where(DiscordTextChannel.provider_channel_ref_hash == channel_hash)).scalar_one_or_none()
    if guild is None or channel is None or channel.discord_guild_id != guild.id:
        return None
    binding = s.execute(select(DiscordChannelRoomBinding).where(
        DiscordChannelRoomBinding.discord_text_channel_id == channel.id,
        DiscordChannelRoomBinding.binding_status.in_(["active", "paused", "conflict_paused"]),
    ).order_by(DiscordChannelRoomBinding.created_at.desc()).limit(1)).scalar_one_or_none()
    return (binding, channel) if binding else None


def _command_bot_in_roster(s, binding_id: uuid.UUID, bot_key: str) -> bool:
    return s.execute(
        select(DiscordChannelBotMembership.id)
        .join(ChannelBotRegistry, ChannelBotRegistry.id == DiscordChannelBotMembership.provider_bot_id)
        .where(
            DiscordChannelBotMembership.discord_channel_room_binding_id == binding_id,
            DiscordChannelBotMembership.membership_status.in_(["active", "inactive"]),
            ChannelBotRegistry.bot_key == bot_key,
        ).limit(1)
    ).scalar_one_or_none() is not None


def _conversation_id_for_room(s, room_id: uuid.UUID) -> uuid.UUID | None:
    return s.execute(select(Conversation.id).where(
        Conversation.co_presence_session_id == room_id,
        Conversation.deleted_at.is_(None),
    ).order_by(Conversation.created_at.asc()).limit(1)).scalar_one_or_none()


def _request_hash(channel_hash: str, message_hash: str, author_hash: str, content: str, mentions: list[str]) -> str:
    return hashlib.sha256(json.dumps({
        "channel": channel_hash, "message": message_hash, "author": author_hash,
        "content": content, "mentions": mentions,
    }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _ingress_dict(s, row: DiscordChannelIngress) -> dict[str, Any]:
    deliveries = list(s.execute(select(DiscordChannelDelivery).where(
        DiscordChannelDelivery.discord_channel_ingress_id == row.id,
    ).order_by(DiscordChannelDelivery.created_at.asc())).scalars())
    return {
        "id": str(row.id), "room_id": str(row.co_presence_session_id),
        "conversation_id": str(row.conversation_id), "room_turn_id": str(row.room_turn_id) if row.room_turn_id else None,
        "user_message_id": str(row.user_message_id) if row.user_message_id else None,
        "status": row.ingress_status, "mentioned_bot_keys": row.mentioned_bot_keys_json or [],
        "selected_companion_ids": row.selected_companion_ids_json or [],
        "evidence": row.evidence_json or {}, "error": row.error_json or {},
        "deliveries": [_delivery_dict(item) for item in deliveries],
        "received_at": _iso(row.received_at), "completed_at": _iso(row.completed_at),
        "idempotent_replay": False,
    }


def _delivery_dict(row: DiscordChannelDelivery) -> dict[str, Any]:
    return {
        "id": str(row.id), "companion_id": str(row.companion_id),
        "assistant_message_id": str(row.assistant_message_id),
        "trace_run_id": str(row.trace_run_id) if row.trace_run_id else None,
        "status": row.delivery_status, "attempt_count": row.attempt_count,
        "max_attempts": row.max_attempts, "next_attempt_at": _iso(row.next_attempt_at),
        "delivered_at": _iso(row.delivered_at), "last_error_code": row.last_error_code,
        "last_error_summary": row.last_error_summary,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _now() -> datetime:
    return datetime.now(timezone.utc)
