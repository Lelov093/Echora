"""Discord DM durable Discord DM and Web Conversation continuity runtime."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, create_engine, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    ChannelBinding,
    ChannelBotRegistry,
    ChannelDeliveryEvent,
    ChannelFailureEvent,
    ChannelMessageEvent,
    Companion,
    CompanionChannelIdentity,
    Conversation,
    DiscordDmConversationBinding,
    DiscordDmDelivery,
    Message,
)
from app.services import channel_message_service, conversation_service, presence_service


logger = logging.getLogger(__name__)
_engine = None
_BLOCKING_BOUNDARY_REASONS = {
    "companion_archived",
    "hard_stop",
    "resident_hard_stopped",
    "resident_paused",
    "focus_mode",
    "quiet_hours",
    "boundary_quiet_hours",
    "profile_quiet_hours",
    "interrupt_policy_silent_only",
    "presence_type_suppressed",
}
_TERMINAL_DELIVERY_STATES = {"delivered", "failed", "cancelled", "suppressed"}


class DiscordDmError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def hash_provider_ref(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def list_bindings(
    *, user_id: uuid.UUID | None = None, companion_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    with get_session() as s:
        stmt = select(DiscordDmConversationBinding)
        if user_id is not None:
            stmt = stmt.where(DiscordDmConversationBinding.user_id == user_id)
        if companion_id is not None:
            stmt = stmt.where(DiscordDmConversationBinding.companion_id == companion_id)
        rows = list(s.execute(stmt.order_by(DiscordDmConversationBinding.updated_at.desc())).scalars())
        return [_binding_dict(s, row) for row in rows]


def list_deliveries(
    *, dm_binding_id: uuid.UUID | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    with get_session() as s:
        stmt = select(DiscordDmDelivery)
        if dm_binding_id is not None:
            stmt = stmt.where(DiscordDmDelivery.dm_binding_id == dm_binding_id)
        rows = list(s.execute(stmt.order_by(DiscordDmDelivery.created_at.desc()).limit(limit)).scalars())
        return [_delivery_dict(row) for row in rows]


def handle_binding_command(
    *, bot_key: str, author_id: str, action: str, conversation_id: str | None = None
) -> str:
    """Execute an explicit Discord slash-command binding transition."""
    snapshot = _find_binding_for_author(bot_key, author_id)
    if snapshot is None:
        return "尚未建立 Discord 私信连续性。请先向这位 Companion 发送一条私信。"
    if action == "status":
        return (
            f"当前状态：{snapshot['binding_status']}；Web Conversation："
            f"{snapshot.get('conversation_title') or snapshot['conversation_id'][:8]}；revision {snapshot['revision']}。"
        )
    if action == "list":
        choices = list_binding_conversation_choices(bot_key=bot_key, author_id=author_id, query="", limit=10)
        if not choices:
            return "当前没有可切换的活跃 Web Conversation。"
        lines = [f"• {item['name']} · {item['value'][:8]}" for item in choices]
        return "可切换的 Web Conversation：\n" + "\n".join(lines)
    if action == "switch" and not conversation_id:
        return "切换需要提供 Web Conversation ID。"
    try:
        changed = transition_binding(
            uuid.UUID(snapshot["id"]),
            action,
            expected_revision=int(snapshot["revision"]),
            conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
            source="slash_command",
        )
    except (ValueError, DiscordDmError) as exc:
        return f"操作未完成：{getattr(exc, 'message', 'Conversation ID 无效或状态已变化。')}"
    labels = {"new": "已新建并切换", "switch": "已切换", "pause": "已暂停", "resume": "已恢复", "revoke": "已撤销"}
    return f"{labels[action]}。当前状态：{changed['binding_status']}；revision {changed['revision']}。"


def list_binding_conversation_choices(
    *,
    bot_key: str,
    author_id: str,
    query: str = "",
    limit: int = 25,
) -> list[dict[str, str]]:
    """Return safe same-owner, same-Companion active Conversation choices."""
    snapshot = _find_binding_for_author(bot_key, author_id)
    if snapshot is None or snapshot["binding_status"] == "revoked":
        return []
    normalized = query.strip().casefold()
    with get_session() as s:
        rows = list(
            s.execute(
                select(Conversation).where(
                    Conversation.user_id == uuid.UUID(snapshot["user_id"]),
                    Conversation.companion_id == uuid.UUID(snapshot["companion_id"]),
                    Conversation.status == "active",
                    Conversation.deleted_at.is_(None),
                    Conversation.history_visible.is_(True),
                ).order_by(Conversation.updated_at.desc()).limit(100)
            ).scalars()
        )
    choices = []
    for row in rows:
        title = (row.title or "未命名对话").strip()
        short_id = str(row.id)[:8]
        if normalized and normalized not in title.casefold() and normalized not in str(row.id).casefold():
            continue
        current = "当前 · " if str(row.id) == snapshot["conversation_id"] else ""
        choices.append({"name": f"{current}{title} · {short_id}"[:100], "value": str(row.id)})
        if len(choices) >= max(1, min(limit, 25)):
            break
    return choices


def _find_binding_for_author(bot_key: str, author_id: str) -> dict[str, Any] | None:
    with get_session() as s:
        row = (
            s.execute(
                select(DiscordDmConversationBinding)
                .join(ChannelBotRegistry, ChannelBotRegistry.id == DiscordDmConversationBinding.provider_bot_id)
                .where(
                    ChannelBotRegistry.bot_key == bot_key,
                    DiscordDmConversationBinding.external_user_ref_hash == hash_provider_ref(author_id),
                )
                .order_by(DiscordDmConversationBinding.updated_at.desc())
                .limit(1)
            )
            .scalar_one_or_none()
        )
        return _binding_dict(s, row) if row is not None else None


def route_inbound_dm(
    *,
    bot_key: str,
    author_id: str,
    author_name: str,
    content: str,
    channel_id: str,
    message_id: str,
) -> dict[str, Any]:
    normalized = content.strip()
    if not normalized:
        raise DiscordDmError("DM_EMPTY", "Empty Discord DM was ignored.")
    if not all((bot_key, author_id, channel_id, message_id)):
        raise DiscordDmError("DM_EVENT_INVALID", "Discord DM routing identifiers are incomplete.")

    binding = _get_or_create_binding(
        bot_key=bot_key,
        author_id=author_id,
        author_name=author_name,
        channel_id=channel_id,
    )
    if binding["binding_status"] != "active":
        raise DiscordDmError(
            "DM_BINDING_NOT_ACTIVE",
            f"Discord DM binding is {binding['binding_status']}.",
        )

    inbound_hash = hash_provider_ref(message_id)
    idempotency_key = f"discord-dm:{binding['provider_bot_id']}:{inbound_hash}"
    existing = _find_delivery_by_idempotency(idempotency_key)
    if existing is not None:
        return {**existing, "idempotent_replay": True}

    inbound_evidence = _find_inbound_evidence(idempotency_key) or channel_message_service.ingest_inbound(
        {
            "channel_binding_id": binding["channel_binding_id"],
            "summary": f"Discord DM received ({len(normalized)} characters)",
            "external_message_ref_hash": inbound_hash,
            "external_conversation_ref_hash": binding["external_channel_ref_hash_prefix"],
            "idempotency_key": idempotency_key,
            "safe_payload_json": {"source": "discord_dm", "content_length": len(normalized)},
        }
    )

    boundary = presence_service.evaluate_presence_suppression(
        uuid.UUID(binding["user_id"]),
        uuid.UUID(binding["companion_id"]),
        "discord_dm_reply",
        min_interval_seconds=0,
    )
    if boundary.get("suppress") and boundary.get("reason") in _BLOCKING_BOUNDARY_REASONS:
        _persist_suppressed_inbound(binding, normalized, inbound_hash, boundary)
        _record_suppressed_delivery(binding, message_id, boundary)
        raise DiscordDmError("DM_BOUNDARY_SUPPRESSED", f"Reply suppressed by {boundary['reason']}.")

    early_dispatch: dict[str, Any] = {}

    def queue_persisted_response(payload: dict[str, Any]) -> None:
        early_dispatch.update(
            _queue_reply_delivery(
                binding=binding,
                inbound_evidence=inbound_evidence,
                inbound_hash=inbound_hash,
                idempotency_key=idempotency_key,
                assistant_message_id=str(payload["assistant_message_id"]),
                user_message_id=str(payload.get("user_message_id") or "") or None,
                reply=str(payload["content"]),
                trace_run_id=str(payload.get("trace_run_id") or "") or None,
            )
        )

    try:
        result = conversation_service.run_conversation(
            uuid.UUID(binding["conversation_id"]),
            uuid.UUID(binding["companion_id"]),
            uuid.UUID(binding["user_id"]),
            normalized,
            "project",
            idempotency_key,
            response_ready_hook=queue_persisted_response,
        )
    except Exception as exc:
        dispatched = early_dispatch or _find_delivery_by_idempotency(idempotency_key)
        if dispatched is not None:
            logger.warning(
                "Discord DM post-response graph failed after durable dispatch trace_run_id=%s type=%s",
                dispatched.get("trace_run_id"),
                type(exc).__name__,
            )
            return {**dispatched, "binding": binding, "post_response_status": "failed_after_dispatch"}
        _record_turn_failure(binding, inbound_evidence, exc)
        raise DiscordDmError(
            "DM_CONVERSATION_RUN_FAILED",
            "The Discord DM was saved to Web, but the Companion reply failed.",
            retryable=True,
        ) from exc

    assistant = result.get("assistant_message") or {}
    assistant_message_id = assistant.get("id")
    reply = str(assistant.get("content") or "")
    if not assistant_message_id or not reply.strip():
        _record_turn_failure(binding, inbound_evidence, RuntimeError("assistant_message_missing"))
        raise DiscordDmError("DM_REPLY_MISSING", "The Conversation run did not produce a reply.", retryable=True)

    trace_run_id = (result.get("trace") or {}).get("trace_run_id")
    dispatched = early_dispatch or _find_delivery_by_idempotency(idempotency_key)
    if not dispatched:
        dispatched = _queue_reply_delivery(
            binding=binding,
            inbound_evidence=inbound_evidence,
            inbound_hash=inbound_hash,
            idempotency_key=idempotency_key,
            assistant_message_id=str(assistant_message_id),
            user_message_id=str((result.get("user_message") or {}).get("id") or "") or None,
            reply=reply,
            trace_run_id=trace_run_id,
        )
    with get_session() as s:
        _tag_conversation_messages(s, result, inbound_hash)
        dm_binding = s.get(DiscordDmConversationBinding, uuid.UUID(binding["id"]))
        s.commit()
        current_binding = _binding_dict(s, dm_binding) if dm_binding else binding
    return {
        **dispatched,
        "binding": current_binding,
        "idempotent_replay": bool((result.get("turn") or {}).get("idempotent_replay")),
        "post_response_status": "completed",
    }


def _queue_reply_delivery(
    *,
    binding: dict[str, Any],
    inbound_evidence: dict[str, Any] | None,
    inbound_hash: str,
    idempotency_key: str,
    assistant_message_id: str,
    user_message_id: str | None,
    reply: str,
    trace_run_id: str | None,
) -> dict[str, Any]:
    """Create the durable Discord outbox as soon as the assistant Message exists."""
    replay = _find_delivery_by_idempotency(idempotency_key)
    if replay is not None:
        return replay
    outbound_evidence = channel_message_service.queue_outbound(
        {
            "channel_binding_id": binding["channel_binding_id"],
            "reply_to_message_event_id": (inbound_evidence or {}).get("message", {}).get("id"),
            "trace_run_id": trace_run_id,
            "summary": f"Discord DM reply queued ({len(reply)} characters)",
            "external_conversation_ref_hash": binding["external_channel_ref_hash_prefix"],
            "idempotency_key": f"{idempotency_key}:reply",
            "safe_payload_json": {"source": "discord_dm", "content_length": len(reply)},
            "safe_delivery_payload_json": {"durable_outbox": True, "queued_on_response_persisted": True},
        }
    )
    if not outbound_evidence or outbound_evidence.get("policy_decision") != "allowed":
        reason = (outbound_evidence or {}).get("policy_reason", "channel_policy_suppressed")
        raise DiscordDmError("DM_OUTBOUND_SUPPRESSED", f"Discord reply was suppressed: {reason}.")
    try:
        with get_session() as s:
            row = DiscordDmDelivery(
                user_id=uuid.UUID(binding["user_id"]),
                companion_id=uuid.UUID(binding["companion_id"]),
                dm_binding_id=uuid.UUID(binding["id"]),
                channel_delivery_event_id=uuid.UUID(outbound_evidence["delivery"]["id"]),
                conversation_id=uuid.UUID(binding["conversation_id"]),
                assistant_message_id=uuid.UUID(assistant_message_id),
                trace_run_id=uuid.UUID(trace_run_id) if trace_run_id else None,
                inbound_message_ref_hash=inbound_hash,
                idempotency_key=idempotency_key,
                delivery_status="queued",
                attempt_count=0,
                max_attempts=5,
                next_attempt_at=_now(),
                metadata_={
                    "implementation_origin": "discord_dm",
                    "source": "discord_dm",
                    "terminal_monotonic": True,
                    "queued_on_response_persisted": True,
                },
            )
            s.add(row)
            dm_binding = s.get(DiscordDmConversationBinding, uuid.UUID(binding["id"]))
            if dm_binding is not None:
                dm_binding.last_inbound_at = _now()
                dm_binding.updated_at = _now()
            _tag_message_ids(s, user_message_id, assistant_message_id, inbound_hash)
            s.commit()
            s.refresh(row)
            return {
                "delivery": _delivery_dict(row),
                "conversation_id": binding["conversation_id"],
                "reply": reply[:2000],
                "trace_run_id": trace_run_id,
            }
    except IntegrityError:
        replay = _find_delivery_by_idempotency(idempotency_key)
        if replay is not None:
            return replay
        raise


def claim_due_deliveries(bot_key: str, worker_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    now = _now()
    lease_until = now + timedelta(seconds=45)
    with get_session() as s:
        stmt = (
            select(DiscordDmDelivery)
            .join(DiscordDmConversationBinding, DiscordDmConversationBinding.id == DiscordDmDelivery.dm_binding_id)
            .join(ChannelBotRegistry, ChannelBotRegistry.id == DiscordDmConversationBinding.provider_bot_id)
            .where(
                ChannelBotRegistry.bot_key == bot_key,
                DiscordDmConversationBinding.binding_status == "active",
                DiscordDmDelivery.delivery_status.in_(["queued", "retry_scheduled", "leased"]),
                or_(DiscordDmDelivery.next_attempt_at.is_(None), DiscordDmDelivery.next_attempt_at <= now),
                or_(DiscordDmDelivery.lease_expires_at.is_(None), DiscordDmDelivery.lease_expires_at <= now),
            )
            .order_by(DiscordDmDelivery.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        rows = list(s.execute(stmt).scalars())
        claimed: list[dict[str, Any]] = []
        for row in rows:
            if row.delivery_status in _TERMINAL_DELIVERY_STATES:
                continue
            row.delivery_status = "leased"
            row.attempt_count += 1
            row.lease_owner = worker_id
            row.lease_expires_at = lease_until
            row.updated_at = now
            binding = s.get(DiscordDmConversationBinding, row.dm_binding_id)
            message = s.get(Message, row.assistant_message_id)
            if binding is None or message is None:
                row.delivery_status = "failed"
                row.last_error_code = "delivery_reference_missing"
                row.last_error_summary = "Delivery binding or assistant message is missing."
                row.lease_owner = None
                row.lease_expires_at = None
                continue
            claimed.append(
                {
                    "id": str(row.id),
                    "bot_key": bot_key,
                    "channel_id": binding.provider_channel_ref,
                    "content": message.content[:2000],
                    "attempt_count": row.attempt_count,
                    "max_attempts": row.max_attempts,
                }
            )
        s.commit()
        return claimed


def mark_delivered(delivery_id: uuid.UUID, provider_message_id: str) -> dict[str, Any] | None:
    with get_session() as s:
        row = s.get(DiscordDmDelivery, delivery_id)
        if row is None:
            return None
        if row.delivery_status == "delivered":
            return _delivery_dict(row)
        if row.delivery_status in {"failed", "cancelled", "suppressed"}:
            return _delivery_dict(row)
        now = _now()
        row.delivery_status = "delivered"
        row.provider_message_ref_hash = hash_provider_ref(provider_message_id)
        row.delivered_at = now
        row.lease_owner = None
        row.lease_expires_at = None
        row.next_attempt_at = None
        row.last_error_code = None
        row.last_error_summary = None
        row.updated_at = now
        binding = s.get(DiscordDmConversationBinding, row.dm_binding_id)
        if binding is not None:
            binding.last_outbound_at = now
            binding.updated_at = now
        if row.channel_delivery_event_id:
            evidence = s.get(ChannelDeliveryEvent, row.channel_delivery_event_id)
            if evidence is not None and evidence.delivery_status != "sent":
                evidence.delivery_status = "sent"
                evidence.delivered_at = now
                evidence.delivery_attempt = row.attempt_count
                evidence.external_delivery_ref_hash = row.provider_message_ref_hash
                evidence.delivery_summary = "Discord DM reply delivered"
                evidence.metadata_ = {**(evidence.metadata_ or {}), "real_provider_send": True, "implementation_origin": "discord_dm"}
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
        row = s.get(DiscordDmDelivery, delivery_id)
        if row is None:
            return None
        if row.delivery_status in _TERMINAL_DELIVERY_STATES:
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
        row.updated_at = now
        binding = s.get(DiscordDmConversationBinding, row.dm_binding_id)
        provider_bot_id = binding.provider_bot_id if binding else None
        channel_binding_id = binding.channel_binding_id if binding else None
        if provider_bot_id is not None and binding is not None:
            bot = s.get(ChannelBotRegistry, provider_bot_id)
            failure = ChannelFailureEvent(
                provider_id=bot.provider_id if bot else None,
                provider_bot_id=provider_bot_id,
                channel_binding_id=channel_binding_id,
                channel_delivery_event_id=row.channel_delivery_event_id,
                failure_type="discord_delivery",
                failure_status="retry_scheduled" if can_retry else "recorded",
                safe_error_summary=row.last_error_summary,
                safe_error_json={"error_code": row.last_error_code, "retryable": can_retry, "attempt": row.attempt_count},
                occurred_at=now,
                metadata_={"implementation_origin": "discord_dm"},
            )
            s.add(failure)
        if row.channel_delivery_event_id:
            evidence = s.get(ChannelDeliveryEvent, row.channel_delivery_event_id)
            if evidence is not None and evidence.delivery_status != "sent":
                evidence.delivery_status = "rate_limited" if can_retry else "failed"
                evidence.delivery_attempt = row.attempt_count
                evidence.delivery_summary = "Discord DM retry scheduled" if can_retry else "Discord DM delivery failed"
        s.commit()
        return _delivery_dict(row)


def transition_binding(
    binding_id: uuid.UUID,
    action: str,
    *,
    expected_revision: int,
    conversation_id: uuid.UUID | None = None,
    source: str = "web",
) -> dict[str, Any]:
    if action not in {"pause", "resume", "revoke", "switch", "new"}:
        raise DiscordDmError("DM_BINDING_ACTION_INVALID", "Unsupported DM binding action.")
    with get_session() as s:
        row = s.execute(
            select(DiscordDmConversationBinding)
            .where(DiscordDmConversationBinding.id == binding_id)
            .with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise DiscordDmError("DM_BINDING_NOT_FOUND", "Discord DM binding not found.")
        if row.revision != expected_revision:
            raise DiscordDmError("DM_BINDING_REVISION_CONFLICT", "Discord DM binding changed; reload and retry.")
        if row.binding_status == "revoked" and action != "revoke":
            raise DiscordDmError("DM_BINDING_REVOKED", "A revoked Discord DM binding cannot be restored.")
        now = _now()
        if action == "switch":
            conversation = s.get(Conversation, conversation_id)
            if (
                conversation is None
                or conversation.deleted_at is not None
                or conversation.user_id != row.user_id
                or conversation.companion_id != row.companion_id
            ):
                raise DiscordDmError("DM_CONVERSATION_SCOPE_MISMATCH", "Conversation is outside this owner and Companion scope.")
            row.conversation_id = conversation.id
        elif action == "new":
            conversation = _new_conversation(s, row.user_id, row.companion_id, "Discord 私信")
            row.conversation_id = conversation.id
        elif action == "pause":
            row.binding_status = "paused"
        elif action == "resume":
            row.binding_status = "active"
        elif action == "revoke":
            row.binding_status = "revoked"
            row.revoked_at = now
            channel_binding = s.get(ChannelBinding, row.channel_binding_id)
            if channel_binding is not None:
                channel_binding.binding_status = "revoked"
                channel_binding.can_receive_inbound = False
                channel_binding.can_send_outbound = False
                channel_binding.revoked_at = now
            pending = list(
                s.execute(
                    select(DiscordDmDelivery).where(
                        DiscordDmDelivery.dm_binding_id == row.id,
                        DiscordDmDelivery.delivery_status.in_(["queued", "leased", "retry_scheduled"]),
                    )
                ).scalars()
            )
            for delivery in pending:
                delivery.delivery_status = "cancelled"
                delivery.cancelled_at = now
                delivery.lease_owner = None
                delivery.lease_expires_at = None
                delivery.next_attempt_at = None
        row.binding_source = source
        row.revision += 1
        row.updated_at = now
        s.commit()
        s.refresh(row)
        return _binding_dict(s, row)


def _get_or_create_binding(*, bot_key: str, author_id: str, author_name: str, channel_id: str) -> dict[str, Any]:
    user_hash = hash_provider_ref(author_id)
    channel_hash = hash_provider_ref(channel_id)
    with get_session() as s:
        bot = s.execute(
            select(ChannelBotRegistry)
            .where(ChannelBotRegistry.bot_key == bot_key)
            .with_for_update()
        ).scalar_one_or_none()
        if bot is None:
            raise DiscordDmError("DM_BOT_NOT_FOUND", "Discord bot is not registered.")
        identities = list(
            s.execute(
                select(CompanionChannelIdentity).where(
                    CompanionChannelIdentity.provider_bot_id == bot.id,
                    CompanionChannelIdentity.channel_status == "active",
                )
            ).scalars()
        )
        if len(identities) != 1:
            raise DiscordDmError("DM_COMPANION_BINDING_INVALID", "Discord bot must have exactly one active Companion binding.")
        identity = identities[0]
        if identity.companion_id is None:
            raise DiscordDmError("DM_COMPANION_NOT_FOUND", "Discord bot has no Companion.")
        existing = s.execute(
            select(DiscordDmConversationBinding).where(
                DiscordDmConversationBinding.provider_bot_id == bot.id,
                DiscordDmConversationBinding.external_user_ref_hash == user_hash,
                DiscordDmConversationBinding.binding_status.in_(["active", "paused"]),
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.companion_id != identity.companion_id:
                raise DiscordDmError("DM_COMPANION_SCOPE_CHANGED", "Bot-to-Companion binding changed; revoke and relink DM continuity.")
            existing.provider_channel_ref = channel_id
            existing.external_channel_ref_hash = channel_hash
            existing.updated_at = _now()
            s.commit()
            return _binding_dict(s, existing)

        owner_lock = s.execute(
            select(DiscordDmConversationBinding).where(
                DiscordDmConversationBinding.provider_bot_id == bot.id,
                DiscordDmConversationBinding.binding_status.in_(["active", "paused"]),
            )
        ).scalar_one_or_none()
        if owner_lock is not None:
            raise DiscordDmError("DM_OWNER_SCOPE_MISMATCH", "This bot is already locked to another Discord DM identity.")
        companion = s.get(Companion, identity.companion_id)
        if companion is None or companion.deleted_at is not None or companion.user_id != identity.user_id:
            raise DiscordDmError("DM_OWNER_SCOPE_INVALID", "Companion owner scope is invalid.")
        conversation = _new_conversation(s, identity.user_id, identity.companion_id, f"Discord · {author_name[:80]}")
        channel_binding = ChannelBinding(
            user_id=identity.user_id,
            companion_id=identity.companion_id,
            provider_id=bot.provider_id,
            provider_bot_id=bot.id,
            presence_channel_binding_id=identity.presence_channel_binding_id,
            binding_status="active",
            binding_scope="dm",
            permission_scope="reply_only",
            outbound_policy="reply_only",
            memory_policy="ephemeral_review_gated",
            requires_user_approval=True,
            can_receive_inbound=True,
            can_send_outbound=True,
            checkin_enabled=False,
            memory_write_requires_review=True,
            raw_message_storage_allowed=False,
            stores_plaintext_token=False,
            external_channel_ref_hash=channel_hash,
            external_user_ref_hash=user_hash,
            permission_snapshot_json={"reply_only": True, "owner_lock": "first_dm"},
            boundary_snapshot_json={"hard_stop_precedence": True, "channel_memory_review_gated": True},
            metadata_={"implementation_origin": "discord_dm", "provider_key": "discord", "owner_scope": "first_dm_locked"},
        )
        s.add(channel_binding)
        s.flush()
        row = DiscordDmConversationBinding(
            user_id=identity.user_id,
            companion_id=identity.companion_id,
            provider_bot_id=bot.id,
            companion_channel_identity_id=identity.id,
            channel_binding_id=channel_binding.id,
            conversation_id=conversation.id,
            external_user_ref_hash=user_hash,
            external_channel_ref_hash=channel_hash,
            provider_channel_ref=channel_id,
            binding_status="active",
            binding_source="first_dm",
            revision=1,
            metadata_={"implementation_origin": "discord_dm", "owner_scope": "first_dm_locked", "raw_refs_public": False},
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return _binding_dict(s, row)


def _new_conversation(s: Session, user_id: uuid.UUID, companion_id: uuid.UUID, title: str) -> Conversation:
    row = Conversation(
        user_id=user_id,
        companion_id=companion_id,
        title=title,
        mode_key="project",
        status="active",
        retention_mode="standard",
        cross_session_memory_enabled=True,
        history_visible=True,
        continuity_state={"source": "discord_dm", "web_superset": True},
        metadata_={"implementation_origin": "discord_dm", "source": "discord_dm"},
    )
    s.add(row)
    s.flush()
    return row


def _record_suppressed_delivery(binding: dict[str, Any], message_id: str, boundary: dict[str, Any]) -> None:
    logger.info(
        "Discord DM reply suppressed bot=%s companion=%s reason=%s message_hash=%s",
        binding.get("bot_key"),
        binding["companion_id"][:8],
        boundary.get("reason"),
        hash_provider_ref(message_id)[:12],
    )


def _find_inbound_evidence(idempotency_key: str) -> dict[str, Any] | None:
    with get_session() as s:
        row = s.execute(
            select(ChannelMessageEvent).where(ChannelMessageEvent.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {"message": {"id": str(row.id)}, "memory_write": "not_written_review_required"}


def _persist_suppressed_inbound(
    binding: dict[str, Any], content: str, inbound_hash: str, boundary: dict[str, Any]
) -> None:
    with get_session() as s:
        existing = s.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(binding["conversation_id"]),
                Message.role == "user",
                Message.metadata_["external_message_ref_hash"].astext == inbound_hash,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return
    conversation_service.create_message(
        {
            "user_id": uuid.UUID(binding["user_id"]),
            "companion_id": uuid.UUID(binding["companion_id"]),
            "conversation_id": uuid.UUID(binding["conversation_id"]),
            "role": "user",
            "content": content,
            "content_format": "text",
            "source_modality": "text",
            "metadata_": {
                "channel_source": "discord_dm",
                "channel_direction": "inbound",
                "external_message_ref_hash": inbound_hash,
                "reply_suppressed_reason": boundary.get("reason"),
                "meaningful_silence": True,
            },
        }
    )


def _record_turn_failure(binding: dict[str, Any], inbound: dict[str, Any] | None, exc: Exception) -> None:
    try:
        with get_session() as s:
            bot = s.get(ChannelBotRegistry, uuid.UUID(binding["provider_bot_id"]))
            s.add(
                ChannelFailureEvent(
                    provider_id=bot.provider_id if bot else None,
                    provider_bot_id=uuid.UUID(binding["provider_bot_id"]),
                    channel_binding_id=uuid.UUID(binding["channel_binding_id"]),
                    channel_message_event_id=uuid.UUID(inbound["message"]["id"]) if inbound else None,
                    failure_type="discord_conversation_run",
                    failure_status="recorded",
                    safe_error_summary="Discord DM Conversation run failed",
                    safe_error_json={"error_type": type(exc).__name__, "retryable": True},
                    occurred_at=_now(),
                    metadata_={"implementation_origin": "discord_dm"},
                )
            )
            s.commit()
    except Exception:
        logger.exception("Failed to persist Discord DM failure evidence")


def _find_delivery_by_idempotency(idempotency_key: str) -> dict[str, Any] | None:
    with get_session() as s:
        row = s.execute(
            select(DiscordDmDelivery).where(DiscordDmDelivery.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if row is None:
            return None
        message = s.get(Message, row.assistant_message_id)
        return {
            "delivery": _delivery_dict(row),
            "conversation_id": str(row.conversation_id),
            "reply": (message.content if message else "")[:2000],
            "trace_run_id": str(row.trace_run_id) if row.trace_run_id else None,
        }


def _tag_conversation_messages(s: Session, result: dict[str, Any], inbound_hash: str) -> None:
    for key, direction in (("user_message", "inbound"), ("assistant_message", "outbound")):
        message_id = (result.get(key) or {}).get("id")
        if not message_id:
            continue
        message = s.get(Message, uuid.UUID(message_id))
        if message is not None:
            message.metadata_ = {
                **(message.metadata_ or {}),
                "channel_source": "discord_dm",
                "channel_direction": direction,
                "external_message_ref_hash": inbound_hash,
            }


def _tag_message_ids(
    s: Session,
    user_message_id: str | None,
    assistant_message_id: str | None,
    inbound_hash: str,
) -> None:
    for message_id, direction in ((user_message_id, "inbound"), (assistant_message_id, "outbound")):
        if not message_id:
            continue
        message = s.get(Message, uuid.UUID(message_id))
        if message is not None:
            message.metadata_ = {
                **(message.metadata_ or {}),
                "channel_source": "discord_dm",
                "channel_direction": direction,
                "external_message_ref_hash": inbound_hash,
            }


def _binding_dict(s: Session, row: DiscordDmConversationBinding) -> dict[str, Any]:
    bot = s.get(ChannelBotRegistry, row.provider_bot_id)
    companion = s.get(Companion, row.companion_id)
    conversation = s.get(Conversation, row.conversation_id)
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "companion_id": str(row.companion_id),
        "companion_name": companion.name if companion else None,
        "provider_bot_id": str(row.provider_bot_id),
        "bot_key": bot.bot_key if bot else None,
        "bot_display_name": bot.bot_display_name if bot else None,
        "companion_channel_identity_id": str(row.companion_channel_identity_id),
        "channel_binding_id": str(row.channel_binding_id),
        "conversation_id": str(row.conversation_id),
        "conversation_title": conversation.title if conversation else None,
        "external_user_ref_hash_prefix": row.external_user_ref_hash[:12],
        "external_channel_ref_hash_prefix": row.external_channel_ref_hash[:12],
        "binding_status": row.binding_status,
        "binding_source": row.binding_source,
        "revision": row.revision,
        "last_inbound_at": row.last_inbound_at.isoformat() if row.last_inbound_at else None,
        "last_outbound_at": row.last_outbound_at.isoformat() if row.last_outbound_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "provider_channel_ref_exposed": False,
    }


def _delivery_dict(row: DiscordDmDelivery) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "dm_binding_id": str(row.dm_binding_id),
        "conversation_id": str(row.conversation_id),
        "assistant_message_id": str(row.assistant_message_id),
        "trace_run_id": str(row.trace_run_id) if row.trace_run_id else None,
        "delivery_status": row.delivery_status,
        "attempt_count": row.attempt_count,
        "max_attempts": row.max_attempts,
        "next_attempt_at": row.next_attempt_at.isoformat() if row.next_attempt_at else None,
        "last_error_code": row.last_error_code,
        "last_error_summary": row.last_error_summary,
        "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None,
        "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)
