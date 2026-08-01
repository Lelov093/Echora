"""Companion Room binding Discord Guild/Channel directory and exact Room roster binding."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import (
    ChannelBotRegistry,
    ChannelProvider,
    Companion,
    CompanionChannelIdentity,
    CoPresenceParticipant,
    CoPresenceSession,
    DiscordChannelBotMembership,
    DiscordChannelDelivery,
    DiscordChannelRoomBinding,
    DiscordGuild,
    DiscordTextChannel,
)
from app.services import co_presence_service


class CompanionRoomChannelError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def list_guilds(user_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    with co_presence_service.get_session() as s:
        stmt = select(DiscordGuild).order_by(DiscordGuild.updated_at.desc())
        if user_id:
            stmt = stmt.where(DiscordGuild.user_id == user_id)
        return [_guild_to_dict(row) for row in s.execute(stmt).scalars().all()]


def create_guild(payload: dict[str, Any]) -> dict[str, Any]:
    guild_ref = str(payload["provider_guild_ref"]).strip()
    display_name = str(payload["guild_display_name"]).strip()
    user_id = _uuid(payload["user_id"])
    if not guild_ref or not display_name:
        raise CompanionRoomChannelError("DISCORD_GUILD_VALIDATION_ERROR", "服务器标识和显示名称不能为空。")
    ref_hash = _hash(guild_ref)
    with co_presence_service.get_session() as s:
        provider = s.execute(select(ChannelProvider).where(ChannelProvider.provider_key == "discord")).scalar_one_or_none()
        if provider is None:
            raise CompanionRoomChannelError("DISCORD_PROVIDER_NOT_READY", "Discord Provider 尚未登记。")
        row = s.execute(select(DiscordGuild).where(
            DiscordGuild.provider_id == provider.id,
            DiscordGuild.provider_guild_ref_hash == ref_hash,
        ).with_for_update()).scalar_one_or_none()
        if row is None:
            row = DiscordGuild(
                user_id=user_id, provider_id=provider.id, provider_guild_ref=guild_ref,
                provider_guild_ref_hash=ref_hash, guild_display_name=display_name,
                guild_status="active", revision=1, metadata_={"source": "web", "implementation_origin": "companion_room_binding"},
            )
            s.add(row)
        else:
            if row.user_id != user_id:
                raise CompanionRoomChannelError("DISCORD_GUILD_SCOPE_MISMATCH", "该服务器不属于当前 owner scope。")
            row.guild_display_name = display_name
            row.guild_status = "active"
            row.revision += 1
        s.commit(); s.refresh(row)
        return _guild_to_dict(row)


def list_channels(guild_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    with co_presence_service.get_session() as s:
        stmt = select(DiscordTextChannel).order_by(DiscordTextChannel.updated_at.desc())
        if guild_id:
            stmt = stmt.where(DiscordTextChannel.discord_guild_id == guild_id)
        if user_id:
            stmt = stmt.where(DiscordTextChannel.user_id == user_id)
        return [_channel_bundle(s, row) for row in s.execute(stmt).scalars().all()]


def create_channel(guild_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    channel_ref = str(payload["provider_channel_ref"]).strip()
    display_name = str(payload["channel_display_name"]).strip()
    ref_hash = _hash(channel_ref)
    with co_presence_service.get_session() as s:
        guild = s.execute(select(DiscordGuild).where(DiscordGuild.id == guild_id).with_for_update()).scalar_one_or_none()
        if guild is None or guild.guild_status != "active":
            raise CompanionRoomChannelError("DISCORD_GUILD_NOT_ACTIVE", "Discord 服务器不存在或不可用。")
        row = s.execute(select(DiscordTextChannel).where(
            DiscordTextChannel.discord_guild_id == guild.id,
            DiscordTextChannel.provider_channel_ref_hash == ref_hash,
        ).with_for_update()).scalar_one_or_none()
        if row is None:
            row = DiscordTextChannel(
                user_id=guild.user_id, discord_guild_id=guild.id,
                provider_channel_ref=channel_ref, provider_channel_ref_hash=ref_hash,
                channel_display_name=display_name, channel_status="active",
                permission_status=payload.get("permission_status", "unverified"),
                permission_snapshot_json={"minimum_permission_integer": 68608, "verified_by": "user" if payload.get("permission_status") == "ready" else None},
                revision=1, metadata_={"source": "web", "implementation_origin": "companion_room_binding"},
            )
            s.add(row)
        else:
            row.channel_display_name = display_name
            row.permission_status = payload.get("permission_status", row.permission_status)
            row.channel_status = "active"
            row.revision += 1
        s.commit(); s.refresh(row)
        return _channel_bundle(s, row)


def list_available_bot_identities(user_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    with co_presence_service.get_session() as s:
        stmt = select(CompanionChannelIdentity).where(
            CompanionChannelIdentity.channel_status == "active",
            CompanionChannelIdentity.provider_bot_id.is_not(None),
        ).order_by(CompanionChannelIdentity.updated_at.desc())
        if user_id:
            stmt = stmt.where(CompanionChannelIdentity.user_id == user_id)
        rows = s.execute(stmt).scalars().all()
        result = []
        for identity in rows:
            bot = s.get(ChannelBotRegistry, identity.provider_bot_id)
            companion = s.get(Companion, identity.companion_id)
            if bot and companion:
                result.append({
                    "provider_bot_id": str(bot.id), "bot_key": bot.bot_key,
                    "bot_display_name": bot.bot_display_name,
                    "companion_channel_identity_id": str(identity.id),
                    "identity_revision": identity.revision,
                    "companion_id": str(companion.id), "companion_name": companion.name,
                })
        return result


def bind_channel_to_room(channel_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    room_id = _uuid(payload["room_id"])
    bot_ids = [_uuid(item) for item in payload["provider_bot_ids"]]
    now = datetime.now(timezone.utc)
    with co_presence_service.get_session() as s:
        channel = s.execute(select(DiscordTextChannel).where(DiscordTextChannel.id == channel_id).with_for_update()).scalar_one_or_none()
        room = s.execute(select(CoPresenceSession).where(CoPresenceSession.id == room_id).with_for_update()).scalar_one_or_none()
        if channel is None or channel.channel_status != "active":
            raise CompanionRoomChannelError("DISCORD_CHANNEL_NOT_ACTIVE", "Discord 频道不存在或不可用。")
        if room is None or room.session_source != "companion_home" or room.session_status != "active":
            raise CompanionRoomChannelError("COMPANION_ROOM_NOT_ACTIVE", "只能绑定进行中的伙伴聊天室。")
        if channel.user_id != room.user_id:
            raise CompanionRoomChannelError("DISCORD_ROOM_SCOPE_MISMATCH", "频道和聊天室必须属于同一 owner scope。")
        if channel.revision != int(payload["expected_channel_revision"]):
            raise CompanionRoomChannelError("DISCORD_CHANNEL_REVISION_CONFLICT", "频道已经变化，请刷新后重试。", {"current_revision": channel.revision})
        if room.roster_revision != int(payload["expected_room_roster_revision"]):
            raise CompanionRoomChannelError("COMPANION_ROOM_REVISION_CONFLICT", "聊天室成员已经变化，请刷新后重试。", {"current_revision": room.roster_revision})
        guild = s.get(DiscordGuild, channel.discord_guild_id)
        participants = list(s.execute(select(CoPresenceParticipant).where(
            CoPresenceParticipant.co_presence_session_id == room.id,
            CoPresenceParticipant.participant_type == "companion",
            CoPresenceParticipant.join_status == "active",
        )).scalars().all())
        room_companion_ids = {item.participant_companion_id for item in participants if item.participant_companion_id}
        identities = list(s.execute(select(CompanionChannelIdentity).where(
            CompanionChannelIdentity.provider_bot_id.in_(bot_ids),
            CompanionChannelIdentity.channel_status == "active",
        ).with_for_update()).scalars().all())
        identity_by_bot = {item.provider_bot_id: item for item in identities}
        mapped_companion_ids = {item.companion_id for item in identities}
        _require_exact_roster(room_companion_ids, bot_ids, identities)
        for bot_id in bot_ids:
            bot = s.get(ChannelBotRegistry, bot_id)
            if bot is None or guild is None or bot.provider_id != guild.provider_id:
                raise CompanionRoomChannelError("DISCORD_ROOM_PROVIDER_MISMATCH", "所选 Bot 不属于该 Discord Provider。")
        conflicting = s.execute(select(DiscordChannelRoomBinding).where(
            DiscordChannelRoomBinding.binding_status.in_(["active", "paused", "conflict_paused"]),
            ((DiscordChannelRoomBinding.discord_text_channel_id == channel.id) & (DiscordChannelRoomBinding.co_presence_session_id != room.id))
            | ((DiscordChannelRoomBinding.co_presence_session_id == room.id) & (DiscordChannelRoomBinding.discord_text_channel_id != channel.id)),
        )).scalar_one_or_none()
        if conflicting:
            raise CompanionRoomChannelError("DISCORD_ROOM_BINDING_CONFLICT", "频道或聊天室已有其他有效绑定。")
        binding = s.execute(select(DiscordChannelRoomBinding).where(
            DiscordChannelRoomBinding.discord_text_channel_id == channel.id,
            DiscordChannelRoomBinding.co_presence_session_id == room.id,
            DiscordChannelRoomBinding.binding_status.in_(["active", "paused", "conflict_paused"]),
        ).with_for_update()).scalar_one_or_none()
        fingerprint = _roster_fingerprint(room_companion_ids, identities)
        if binding is None:
            binding = DiscordChannelRoomBinding(
                user_id=room.user_id, discord_text_channel_id=channel.id,
                co_presence_session_id=room.id, binding_status="active",
                mention_policy=payload.get("mention_policy", "mention_only"),
                roster_fingerprint=fingerprint, room_roster_revision=room.roster_revision,
                revision=1, bound_at=now,
                evidence_json={"exact_roster_match": True, "source": "web"}, metadata_={"implementation_origin": "companion_room_binding"},
            )
            s.add(binding)
        else:
            _cancel_pending_deliveries(s, binding.id, "binding_reconciled", now)
            binding.binding_status = "active"; binding.paused_at = None
            binding.mention_policy = payload.get("mention_policy", binding.mention_policy)
            binding.roster_fingerprint = fingerprint; binding.room_roster_revision = room.roster_revision
            binding.revision += 1
            binding.evidence_json = {"exact_roster_match": True, "source": "web", "reconciled_at": now.isoformat()}
        s.flush()
        for old in s.execute(select(DiscordChannelBotMembership).where(
            DiscordChannelBotMembership.discord_text_channel_id == channel.id,
            DiscordChannelBotMembership.membership_status == "active",
        ).with_for_update()).scalars():
            old.membership_status = "inactive"; old.deactivated_at = now; old.revision += 1
        for bot_id in bot_ids:
            identity = identity_by_bot[bot_id]
            s.add(DiscordChannelBotMembership(
                user_id=room.user_id, discord_text_channel_id=channel.id,
                discord_channel_room_binding_id=binding.id, provider_bot_id=bot_id,
                companion_channel_identity_id=identity.id, companion_id=identity.companion_id,
                participation_mode=payload.get("mention_policy", "mention_only"), membership_status="active",
                identity_revision=identity.revision, revision=1, activated_at=now, metadata_={"implementation_origin": "companion_room_binding"},
            ))
        channel.revision += 1
        s.commit(); s.refresh(binding)
        return _binding_bundle(s, binding)


def transition_channel_binding(binding_id: uuid.UUID, action: str, expected_revision: int, reason: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with co_presence_service.get_session() as s:
        binding = s.execute(select(DiscordChannelRoomBinding).where(DiscordChannelRoomBinding.id == binding_id).with_for_update()).scalar_one_or_none()
        if binding is None:
            raise CompanionRoomChannelError("DISCORD_ROOM_BINDING_NOT_FOUND", "未找到频道与聊天室绑定。")
        if binding.revision != expected_revision:
            raise CompanionRoomChannelError("DISCORD_ROOM_BINDING_REVISION_CONFLICT", "绑定已经变化，请刷新后重试。", {"current_revision": binding.revision})
        if binding.binding_status == "revoked":
            raise CompanionRoomChannelError("DISCORD_ROOM_BINDING_REVOKED", "已撤销绑定不能恢复。")
        memberships = list(s.execute(select(DiscordChannelBotMembership).where(
            DiscordChannelBotMembership.discord_channel_room_binding_id == binding.id,
            DiscordChannelBotMembership.membership_status.in_(["active", "inactive"]),
        ).with_for_update()).scalars().all())
        if action == "pause":
            binding.binding_status = "paused"; binding.paused_at = now
            _cancel_pending_deliveries(s, binding.id, "binding_paused", now)
            for item in memberships:
                if item.membership_status == "active": item.membership_status = "inactive"; item.deactivated_at = now; item.revision += 1
        elif action == "resume":
            _validate_binding_snapshot(s, binding, memberships)
            binding.binding_status = "active"; binding.paused_at = None
            for item in memberships:
                item.membership_status = "active"; item.deactivated_at = None; item.revision += 1
        elif action == "revoke":
            binding.binding_status = "revoked"; binding.revoked_at = now
            _cancel_pending_deliveries(s, binding.id, "binding_revoked", now)
            for item in memberships:
                item.membership_status = "revoked"; item.deactivated_at = now; item.revision += 1
        else:
            raise CompanionRoomChannelError("DISCORD_ROOM_BINDING_ACTION_INVALID", "不支持的绑定操作。")
        binding.revision += 1
        binding.evidence_json = {**(binding.evidence_json or {}), "last_action": action, "reason": reason, "at": now.isoformat()}
        s.commit(); s.refresh(binding)
        return _binding_bundle(s, binding)


def switch_channel_room(binding_id: uuid.UUID, target_room_id: uuid.UUID, expected_revision: int) -> dict[str, Any]:
    """Atomically move one Channel to an unoccupied Room with the exact same mapped roster."""
    now = datetime.now(timezone.utc)
    with co_presence_service.get_session() as s:
        binding = s.execute(select(DiscordChannelRoomBinding).where(
            DiscordChannelRoomBinding.id == binding_id,
        ).with_for_update()).scalar_one_or_none()
        if binding is None or binding.binding_status not in {"active", "paused", "conflict_paused"}:
            raise CompanionRoomChannelError("DISCORD_ROOM_BINDING_NOT_SWITCHABLE", "当前频道绑定不可切换。")
        if binding.revision != expected_revision:
            raise CompanionRoomChannelError(
                "DISCORD_ROOM_BINDING_REVISION_CONFLICT", "频道绑定已经变化，请重新选择。",
                {"current_revision": binding.revision},
            )
        if binding.co_presence_session_id == target_room_id:
            return _binding_bundle(s, binding)
        channel = s.execute(select(DiscordTextChannel).where(
            DiscordTextChannel.id == binding.discord_text_channel_id,
        ).with_for_update()).scalar_one()
        room = s.execute(select(CoPresenceSession).where(
            CoPresenceSession.id == target_room_id,
        ).with_for_update()).scalar_one_or_none()
        if room is None or room.session_source != "companion_home" or room.session_status != "active":
            raise CompanionRoomChannelError("COMPANION_ROOM_NOT_ACTIVE", "只能切换到进行中的伙伴聊天室。")
        if room.user_id != binding.user_id or channel.user_id != binding.user_id:
            raise CompanionRoomChannelError("DISCORD_ROOM_SCOPE_MISMATCH", "频道和目标聊天室必须属于同一 owner scope。")
        occupied = s.execute(select(DiscordChannelRoomBinding.id).where(
            DiscordChannelRoomBinding.co_presence_session_id == room.id,
            DiscordChannelRoomBinding.id != binding.id,
            DiscordChannelRoomBinding.binding_status.in_(["active", "paused", "conflict_paused"]),
        ).limit(1)).scalar_one_or_none()
        if occupied:
            raise CompanionRoomChannelError("DISCORD_ROOM_BINDING_CONFLICT", "目标聊天室已有有效频道绑定。")
        memberships = list(s.execute(select(DiscordChannelBotMembership).where(
            DiscordChannelBotMembership.discord_channel_room_binding_id == binding.id,
            DiscordChannelBotMembership.membership_status.in_(["active", "inactive"]),
        ).with_for_update()).scalars().all())
        bot_ids = [item.provider_bot_id for item in memberships]
        identities = list(s.execute(select(CompanionChannelIdentity).where(
            CompanionChannelIdentity.provider_bot_id.in_(bot_ids),
            CompanionChannelIdentity.channel_status == "active",
        ).with_for_update()).scalars().all())
        participants = list(s.execute(select(CoPresenceParticipant).where(
            CoPresenceParticipant.co_presence_session_id == room.id,
            CoPresenceParticipant.participant_type == "companion",
            CoPresenceParticipant.join_status == "active",
        )).scalars().all())
        room_companion_ids = {item.participant_companion_id for item in participants if item.participant_companion_id}
        _require_exact_roster(room_companion_ids, bot_ids, identities)
        identity_by_bot = {item.provider_bot_id: item for item in identities}

        _cancel_pending_deliveries(s, binding.id, "binding_switched", now)
        binding.binding_status = "revoked"
        binding.revoked_at = now
        binding.revision += 1
        binding.evidence_json = {**(binding.evidence_json or {}), "last_action": "switch", "target_room_id": str(room.id), "at": now.isoformat()}
        for item in memberships:
            item.membership_status = "revoked"
            item.deactivated_at = now
            item.revision += 1
        s.flush()

        new_binding = DiscordChannelRoomBinding(
            user_id=binding.user_id,
            discord_text_channel_id=channel.id,
            co_presence_session_id=room.id,
            binding_status="active",
            mention_policy=binding.mention_policy,
            roster_fingerprint=_roster_fingerprint(room_companion_ids, identities),
            room_roster_revision=room.roster_revision,
            revision=1,
            bound_at=now,
            evidence_json={"exact_roster_match": True, "source": "discord_command", "previous_binding_id": str(binding.id)},
            metadata_={"implementation_origin": "discord_room"},
        )
        s.add(new_binding)
        s.flush()
        for bot_id in bot_ids:
            identity = identity_by_bot[bot_id]
            old = next(item for item in memberships if item.provider_bot_id == bot_id)
            s.add(DiscordChannelBotMembership(
                user_id=binding.user_id,
                discord_text_channel_id=channel.id,
                discord_channel_room_binding_id=new_binding.id,
                provider_bot_id=bot_id,
                companion_channel_identity_id=identity.id,
                companion_id=identity.companion_id,
                participation_mode=old.participation_mode,
                membership_status="active",
                identity_revision=identity.revision,
                revision=1,
                activated_at=now,
                metadata_={"implementation_origin": "discord_room", "switched_from_binding_id": str(binding.id)},
            ))
        channel.revision += 1
        s.commit()
        s.refresh(new_binding)
        return _binding_bundle(s, new_binding)


def _cancel_pending_deliveries(s, binding_id: uuid.UUID, reason: str, now: datetime) -> None:
    rows = s.execute(select(DiscordChannelDelivery).where(
        DiscordChannelDelivery.discord_channel_room_binding_id == binding_id,
        DiscordChannelDelivery.delivery_status.in_(["queued", "retry_scheduled"]),
    ).with_for_update()).scalars().all()
    for row in rows:
        row.delivery_status = "cancelled"
        row.cancelled_at = now
        row.next_attempt_at = None
        row.lease_owner = None
        row.lease_expires_at = None
        row.last_error_json = {"code": reason, "message": "Binding state changed before delivery."}


def get_room_channel_projection(room_id: uuid.UUID) -> dict[str, Any] | None:
    with co_presence_service.get_session() as s:
        binding = s.execute(select(DiscordChannelRoomBinding).where(
            DiscordChannelRoomBinding.co_presence_session_id == room_id,
            DiscordChannelRoomBinding.binding_status.in_(["active", "paused", "conflict_paused"]),
        ).order_by(DiscordChannelRoomBinding.created_at.desc()).limit(1)).scalar_one_or_none()
        return _binding_bundle(s, binding) if binding else None


def _validate_binding_snapshot(s, binding, memberships) -> None:
    room = s.get(CoPresenceSession, binding.co_presence_session_id)
    active_members = list(s.execute(select(CoPresenceParticipant).where(
        CoPresenceParticipant.co_presence_session_id == binding.co_presence_session_id,
        CoPresenceParticipant.participant_type == "companion", CoPresenceParticipant.join_status == "active",
    )).scalars().all())
    current_ids = {item.participant_companion_id for item in active_members if item.participant_companion_id}
    mapped_ids = set()
    for member in memberships:
        identity = s.get(CompanionChannelIdentity, member.companion_channel_identity_id)
        if identity is None or identity.channel_status != "active" or identity.provider_bot_id != member.provider_bot_id or identity.companion_id != member.companion_id or identity.revision != member.identity_revision:
            raise CompanionRoomChannelError("DISCORD_ROOM_IDENTITY_DRIFT", "Bot/Companion 映射已变化，请重新建立精确 roster 绑定。")
        mapped_ids.add(member.companion_id)
    if room is None or room.session_status != "active" or current_ids != mapped_ids or room.roster_revision != binding.room_roster_revision:
        raise CompanionRoomChannelError("DISCORD_ROOM_ROSTER_DRIFT", "聊天室成员已变化，请重新建立精确 roster 绑定。")


def _binding_bundle(s, binding: DiscordChannelRoomBinding | None) -> dict[str, Any] | None:
    if binding is None:
        return None
    channel = s.get(DiscordTextChannel, binding.discord_text_channel_id)
    guild = s.get(DiscordGuild, channel.discord_guild_id) if channel else None
    memberships = list(s.execute(select(DiscordChannelBotMembership).where(
        DiscordChannelBotMembership.discord_channel_room_binding_id == binding.id,
        DiscordChannelBotMembership.membership_status != "revoked",
    ).order_by(DiscordChannelBotMembership.created_at.desc())).scalars().all())
    projections = []
    seen = set()
    for item in memberships:
        if item.provider_bot_id in seen: continue
        seen.add(item.provider_bot_id)
        bot = s.get(ChannelBotRegistry, item.provider_bot_id); companion = s.get(Companion, item.companion_id)
        projections.append({
            "membership_id": str(item.id), "provider_bot_id": str(item.provider_bot_id),
            "bot_display_name": bot.bot_display_name if bot else "Discord Bot",
            "companion_id": str(item.companion_id), "companion_name": companion.name if companion else "Companion",
            "participation_mode": item.participation_mode, "membership_status": item.membership_status,
            "identity_revision": item.identity_revision,
        })
    return {
        "id": str(binding.id), "room_id": str(binding.co_presence_session_id),
        "channel_id": str(binding.discord_text_channel_id),
        "channel_display_name": channel.channel_display_name if channel else None,
        "channel_ref_hash_prefix": channel.provider_channel_ref_hash[:10] if channel else None,
        "guild_id": str(guild.id) if guild else None,
        "guild_display_name": guild.guild_display_name if guild else None,
        "binding_status": binding.binding_status, "mention_policy": binding.mention_policy,
        "roster_fingerprint": binding.roster_fingerprint, "room_roster_revision": binding.room_roster_revision,
        "revision": binding.revision, "bot_projections": projections,
    }


def _channel_bundle(s, row: DiscordTextChannel) -> dict[str, Any]:
    live_binding = s.execute(select(DiscordChannelRoomBinding).where(
        DiscordChannelRoomBinding.discord_text_channel_id == row.id,
        DiscordChannelRoomBinding.binding_status.in_(["active", "paused", "conflict_paused"]),
    ).limit(1)).scalar_one_or_none()
    return {
        "id": str(row.id), "guild_id": str(row.discord_guild_id),
        "channel_display_name": row.channel_display_name,
        "channel_ref_hash_prefix": row.provider_channel_ref_hash[:10],
        "channel_status": row.channel_status, "permission_status": row.permission_status,
        "revision": row.revision, "binding": _binding_bundle(s, live_binding) if live_binding else None,
    }


def _guild_to_dict(row: DiscordGuild) -> dict[str, Any]:
    return {
        "id": str(row.id), "user_id": str(row.user_id),
        "guild_display_name": row.guild_display_name,
        "guild_ref_hash_prefix": row.provider_guild_ref_hash[:10],
        "guild_status": row.guild_status, "revision": row.revision,
    }


def _roster_fingerprint(companion_ids, identities) -> str:
    tokens = [f"companion:{item}" for item in sorted(str(value) for value in companion_ids)]
    tokens.extend(f"identity:{item.provider_bot_id}:{item.companion_id}:{item.revision}" for item in sorted(identities, key=lambda value: str(value.provider_bot_id)))
    return _hash("|".join(tokens))


def _require_exact_roster(room_companion_ids, bot_ids, identities) -> None:
    mapped_companion_ids = {item.companion_id for item in identities}
    if len(bot_ids) == len(room_companion_ids) and len(identities) == len(bot_ids) and mapped_companion_ids == room_companion_ids:
        return
    raise CompanionRoomChannelError(
        "DISCORD_ROOM_ROSTER_MISMATCH",
        "Bot 数量或 Bot 当前映射的伙伴与聊天室 active roster 不一致。",
        {
            "room_companion_ids": sorted(str(item) for item in room_companion_ids),
            "mapped_companion_ids": sorted(str(item) for item in mapped_companion_ids),
            "bot_count": len(bot_ids), "room_companion_count": len(room_companion_ids),
        },
    )


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
