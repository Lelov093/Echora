"""WorkingMemoryNode — loads recent messages for context."""

import uuid
from datetime import datetime

from sqlalchemy import select

from app.agents.state import ConversationAgentState
from app.services.conversation_service import get_session, list_messages
from app.db.models import CompanionRoomTurnStep, CoPresenceParticipant, Message


def working_memory_node(state: ConversationAgentState) -> ConversationAgentState:
    conv_id = uuid.UUID(state["conversation_id"])
    room_result = _room_visible_messages(state, conv_id)
    if room_result is not None:
        items = room_result["items"]
    else:
        result = list_messages(
            conv_id,
            page=1,
            page_size=10,
            descending=True,
        )
        items = list(reversed(result["items"]))
    state["recent_messages"] = [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content[:1200],
            "content_format": m.content_format,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in items
    ]

    state.setdefault("trace_steps", []).append({
        "step": "working_memory",
        "order": 2,
        "status": "completed",
        "message": f"Loaded {len(state['recent_messages'])} recent messages",
    })
    return state


def _room_visible_messages(state: ConversationAgentState, conversation_id: uuid.UUID) -> dict | None:
    step_id = state.get("room_turn_step_id")
    if not step_id:
        return None
    with get_session() as s:
        step = s.get(CompanionRoomTurnStep, uuid.UUID(step_id))
        participant = s.get(CoPresenceParticipant, step.participant_id) if step else None
        if step is None or participant is None:
            return None
        joined_from = (participant.metadata_ or {}).get("joined_context_from")
        joined_at = None
        if joined_from:
            try:
                joined_at = datetime.fromisoformat(joined_from)
            except ValueError:
                joined_at = None
        if joined_at is None:
            joined_at = participant.joined_at or participant.created_at
        stmt = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
            Message.created_at >= joined_at,
        ).order_by(Message.created_at.desc()).limit(10)
        items = list(reversed(list(s.execute(stmt).scalars().all())))
        return {"items": items, "total": len(items)}
