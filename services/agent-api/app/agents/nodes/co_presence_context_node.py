"""Companion Reoriented node: load co-presence session context for a conversation."""

import uuid

from app.agents.state import ConversationAgentState
from app.db.models import Conversation
from app.services.co_presence_service import get_co_presence_session_bundle
from app.services.trace_service import get_session


def co_presence_context_node(state: ConversationAgentState) -> ConversationAgentState:
    conversation_id = uuid.UUID(state["conversation_id"])

    with get_session() as s:
        conversation = s.get(Conversation, conversation_id)
        if conversation is None or conversation.co_presence_session_id is None:
            state["co_presence_session"] = {}
            state.setdefault("trace_steps", []).append({
                "step": "co_presence_context",
                "order": 102,
                "status": "skipped",
                "reason": "conversation_has_no_co_presence_session",
            })
            return state
        session_bundle = get_co_presence_session_bundle(conversation.co_presence_session_id) or {}
        state["co_presence_session"] = session_bundle

        conversation_state = dict(state.get("conversation") or {})
        conversation_state["co_presence_session_id"] = str(conversation.co_presence_session_id)
        state["conversation"] = conversation_state

    state.setdefault("trace_steps", []).append({
        "step": "co_presence_context",
        "order": 102,
        "status": "completed",
        "co_presence_session_id": state["co_presence_session"].get("id"),
        "participant_count": len(state["co_presence_session"].get("participants", [])),
        "session_status": state["co_presence_session"].get("session_status"),
    })
    return state
