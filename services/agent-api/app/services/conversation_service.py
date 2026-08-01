"""Conversation & Message service layer."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select, func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Companion, Conversation, Message

_engine = None
ROOM_PRODUCT_KIND = "companion_room"


class ConversationTurnError(Exception):
    """A user-actionable application error raised before Graph execution."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def is_temporary_conversation_expired(
    conversation: Conversation,
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether a temporary Conversation is beyond its access window."""
    if (
        getattr(conversation, "retention_mode", "standard") != "temporary"
        or getattr(conversation, "retention_expires_at", None) is None
    ):
        return False
    current_time = now or datetime.now(timezone.utc)
    expires_at = conversation.retention_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= current_time


def is_companion_room_conversation(conversation: Conversation) -> bool:
    """Keep Room-owned Conversations off the Single-Companion surface."""
    return (getattr(conversation, "metadata_", None) or {}).get("product_kind") == ROOM_PRODUCT_KIND


# ── Conversation CRUD ────────────────────────────────────────────────

def list_conversations(companion_id: uuid.UUID | None = None, status: str | None = None,
                       page: int = 1, page_size: int = 20) -> dict:
    with get_session() as s:
        stmt = select(Conversation).where(
            Conversation.deleted_at.is_(None),
            Conversation.history_visible.is_(True),
            or_(
                Conversation.metadata_["product_kind"].astext.is_(None),
                Conversation.metadata_["product_kind"].astext != ROOM_PRODUCT_KIND,
            ),
        )
        if companion_id:
            stmt = stmt.where(Conversation.companion_id == companion_id)
        if status:
            stmt = stmt.where(Conversation.status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(Conversation.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def get_conversation(
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID | None = None,
    *,
    include_archived: bool = True,
    include_companion_room: bool = False,
) -> Conversation | None:
    with get_session() as s:
        conversation = s.get(Conversation, conversation_id)
        if (
            conversation is None
            or conversation.deleted_at is not None
            or is_temporary_conversation_expired(conversation)
            or (is_companion_room_conversation(conversation) and not include_companion_room)
        ):
            return None
        if companion_id is not None and conversation.companion_id != companion_id:
            return None
        if not include_archived and conversation.status != "active":
            return None
        return conversation


def create_conversation(data: dict) -> Conversation:
    data = dict(data)
    with get_session() as s:
        reasoning_mode = str(data.pop("reasoning_mode", "auto"))
        metadata = dict(data.pop("metadata_", {}) or {})
        metadata.setdefault("reasoning_mode", reasoning_mode)
        companion = s.get(Companion, data["companion_id"])
        if companion is None or companion.deleted_at is not None:
            raise ConversationTurnError("COMPANION_NOT_FOUND", "Companion not found.")
        if companion.user_id != data["user_id"]:
            raise ConversationTurnError(
                "CONVERSATION_SCOPE_MISMATCH",
                "The Companion does not belong to the requested owner.",
            )
        retention_mode = data.get("retention_mode", "standard")
        if retention_mode == "temporary":
            data = {
                **data,
                "cross_session_memory_enabled": False,
                "history_visible": False,
                "retention_expires_at": datetime.now(timezone.utc) + timedelta(days=30),
            }
        else:
            data = {**data, "history_visible": True, "retention_expires_at": None}
        c = Conversation(
            **data,
            metadata_=metadata,
        )
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


def update_conversation(
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID,
    data: dict,
    *,
    include_companion_room: bool = False,
) -> Conversation | None:
    with get_session() as s:
        c = s.get(Conversation, conversation_id)
        if (
            not c
            or c.deleted_at is not None
            or c.companion_id != companion_id
            or is_temporary_conversation_expired(c)
            or (is_companion_room_conversation(c) and not include_companion_room)
        ):
            return None
        for k, v in data.items():
            if k == "cross_session_memory_enabled" and v is not None:
                if c.retention_mode == "temporary" and v:
                    raise ConversationTurnError(
                        "TEMPORARY_CONVERSATION_POLICY_LOCKED",
                        "Temporary Conversations cannot enable cross-session Memory.",
                    )
                c.cross_session_memory_enabled = bool(v)
            elif k in {"title", "mode_key", "current_topic", "current_goal"} and v is not None:
                setattr(c, k, v)
            elif k == "reasoning_mode" and v is not None:
                metadata = dict(c.metadata_ or {})
                metadata["reasoning_mode"] = str(v)
                c.metadata_ = metadata
        c.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(c)
        return c


# ── Message ──────────────────────────────────────────────────────────

def set_conversation_archived(
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID,
    archived: bool,
    *,
    include_companion_room: bool = False,
) -> Conversation | None:
    with get_session() as s:
        c = s.get(Conversation, conversation_id)
        if (
            not c
            or c.deleted_at is not None
            or c.companion_id != companion_id
            or is_temporary_conversation_expired(c)
            or (is_companion_room_conversation(c) and not include_companion_room)
        ):
            return None
        c.status = "archived" if archived else "active"
        c.updated_at = datetime.now(timezone.utc)
        metadata = dict(c.metadata_ or {})
        metadata["lifecycle"] = {
            "operation": "archive" if archived else "restore",
            "at": c.updated_at.isoformat(),
        }
        c.metadata_ = metadata
        s.commit()
        s.refresh(c)
        return c


def list_messages(
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
    *,
    descending: bool = False,
) -> dict:
    with get_session() as s:
        conversation = s.get(Conversation, conversation_id)
        if (
            conversation is None
            or conversation.deleted_at is not None
            or is_temporary_conversation_expired(conversation)
            or (companion_id is not None and conversation.companion_id != companion_id)
            or (companion_id is not None and is_companion_room_conversation(conversation))
        ):
            return {"items": [], "total": 0}
        stmt = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
        )
        if companion_id is not None:
            stmt = stmt.where(Message.companion_id == companion_id)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        ordering = (
            (Message.created_at.desc(), Message.id.desc())
            if descending
            else (Message.created_at.asc(), Message.id.asc())
        )
        stmt = stmt.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def create_message(data: dict) -> Message:
    with get_session() as s:
        conversation = s.get(Conversation, data["conversation_id"])
        if (
            conversation is None
            or conversation.deleted_at is not None
            or is_temporary_conversation_expired(conversation)
        ):
            raise ConversationTurnError("CONVERSATION_NOT_FOUND", "Conversation not found.")
        if conversation.status != "active":
            raise ConversationTurnError(
                "CONVERSATION_NOT_ACTIVE", "Restore the Conversation before adding a message."
            )
        room_scope_valid = _valid_room_message_scope(s, conversation, data)
        if is_companion_room_conversation(conversation) and not room_scope_valid:
            raise ConversationTurnError(
                "ROOM_CONVERSATION_REQUIRES_COORDINATOR",
                "Room messages must be written through the Room coordinator.",
            )
        if (
            data.get("user_id") != conversation.user_id
            or (data.get("companion_id") != conversation.companion_id and not room_scope_valid)
        ):
            raise ConversationTurnError("CONVERSATION_SCOPE_MISMATCH", "Message scope does not match Conversation scope.")
        m = Message(**data)
        s.add(m)
        s.commit()
        s.refresh(m)
        return m


def _valid_room_message_scope(s: Session, conversation: Conversation, data: dict) -> bool:
    """Allow assistant writes from a validated running Room Turn Step only."""
    from app.db.models import CompanionRoomTurn, CompanionRoomTurnStep, CoPresenceParticipant

    metadata = data.get("metadata_") or {}
    step_value = metadata.get("room_turn_step_id")
    turn_value = metadata.get("room_turn_id")
    if data.get("role") != "assistant" or not step_value or not turn_value:
        return False
    try:
        step = s.get(CompanionRoomTurnStep, uuid.UUID(str(step_value)))
        turn = s.get(CompanionRoomTurn, uuid.UUID(str(turn_value)))
    except (TypeError, ValueError):
        return False
    if (
        step is None or turn is None or step.room_turn_id != turn.id
        or turn.conversation_id != conversation.id
        or turn.co_presence_session_id != conversation.co_presence_session_id
        or step.companion_id != data.get("companion_id")
        or step.user_id != data.get("user_id")
        or step.status != "running"
    ):
        return False
    participant = s.get(CoPresenceParticipant, step.participant_id)
    return bool(
        participant
        and participant.co_presence_session_id == turn.co_presence_session_id
        and participant.participant_companion_id == step.companion_id
        and participant.join_status == "active"
        and participant.can_speak
        and participant.participant_role != "observing_companion"
    )


def get_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> Message | None:
    with get_session() as s:
        conversation = s.get(Conversation, conversation_id)
        if (
            conversation is None
            or conversation.deleted_at is not None
            or conversation.companion_id != companion_id
            or is_temporary_conversation_expired(conversation)
            or is_companion_room_conversation(conversation)
        ):
            return None
        message = s.get(Message, message_id)
        if (
            message is None
            or message.deleted_at is not None
            or message.conversation_id != conversation_id
            or message.companion_id != companion_id
        ):
            return None
        return message


def correct_user_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    companion_id: uuid.UUID,
    content: str,
    reason: str | None,
) -> Message | None:
    with get_session() as s:
        conversation = s.get(Conversation, conversation_id)
        if (
            conversation is None
            or conversation.deleted_at is not None
            or conversation.companion_id != companion_id
            or is_temporary_conversation_expired(conversation)
            or is_companion_room_conversation(conversation)
        ):
            return None
        message = s.get(Message, message_id)
        if (
            message is None
            or message.deleted_at is not None
            or message.conversation_id != conversation_id
            or message.companion_id != companion_id
            or message.role != "user"
        ):
            return None
        metadata = dict(message.metadata_ or {})
        revisions = list(metadata.get("content_revisions") or [])
        revisions.append({
            "previous_content": message.content,
            "reason": reason,
            "corrected_at": datetime.now(timezone.utc).isoformat(),
        })
        metadata["content_revisions"] = revisions
        message.metadata_ = metadata
        message.content = content
        message.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(message)
        return message


def withdraw_user_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    companion_id: uuid.UUID,
    reason: str | None,
) -> Message | None:
    with get_session() as s:
        conversation = s.get(Conversation, conversation_id)
        if (
            conversation is None
            or conversation.deleted_at is not None
            or conversation.companion_id != companion_id
            or is_temporary_conversation_expired(conversation)
            or is_companion_room_conversation(conversation)
        ):
            return None
        message = s.get(Message, message_id)
        if (
            message is None
            or message.deleted_at is not None
            or message.conversation_id != conversation_id
            or message.companion_id != companion_id
            or message.role != "user"
        ):
            return None
        now = datetime.now(timezone.utc)
        metadata = dict(message.metadata_ or {})
        metadata["withdrawal"] = {"reason": reason, "withdrawn_at": now.isoformat()}
        message.metadata_ = metadata
        message.deleted_at = now
        message.updated_at = now
        s.commit()
        s.refresh(message)
        return message


# ── Conversation Run: real Agent Graph ───────────────────────────────

def run_conversation(
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    content: str,
    mode_key: str | None = None,
    idempotency_key: str | None = None,
    reasoning_mode: str | None = None,
    response_ready_hook=None,
) -> dict:
    """Execute a validated turn through the Conversation turn application service."""
    from app.services.conversation_application_service import (
        ConversationTurnCommand,
        execute_conversation_turn,
    )

    return execute_conversation_turn(
        ConversationTurnCommand(
            conversation_id=conversation_id,
            requested_companion_id=companion_id,
            requested_user_id=user_id,
            content=content,
            mode_key=mode_key,
            reasoning_mode=reasoning_mode,
            idempotency_key=idempotency_key,
            response_ready_hook=response_ready_hook,
        )
    )


# ── Serialization ────────────────────────────────────────────────────

def _conv_dict(c: Conversation | None) -> dict | None:
    if not c:
        return None
    metadata = c.metadata_ or {}
    return {
        "id": str(c.id), "user_id": str(c.user_id), "companion_id": str(c.companion_id),
        "title": c.title, "mode_key": c.mode_key, "status": c.status,
        "current_topic": c.current_topic, "current_goal": c.current_goal,
        "summary": c.summary,
        "retention_mode": c.retention_mode,
        "cross_session_memory_enabled": c.cross_session_memory_enabled,
        "history_visible": c.history_visible,
        "retention_expires_at": c.retention_expires_at.isoformat() if c.retention_expires_at else None,
        "continuity_state": c.continuity_state or {},
        "reasoning_mode": metadata.get("reasoning_mode", "auto"),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _msg_dict(m: Message) -> dict:
    updated_at = getattr(m, "updated_at", None)
    deleted_at = getattr(m, "deleted_at", None)
    metadata = getattr(m, "metadata_", {}) or {}
    return {
        "id": str(m.id), "role": m.role, "content": m.content,
        "content_format": m.content_format, "source_modality": m.source_modality,
        "model_provider": m.model_provider, "model_name": m.model_name,
        "generation_status": metadata.get("generation_status"),
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "lifecycle": {
            "withdrawn": deleted_at is not None,
            "has_corrections": bool(metadata.get("content_revisions")),
        },
    }
