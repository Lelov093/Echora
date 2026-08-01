"""Refresh bounded versioned Companion context documents after a completed turn."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import context_document_service


def context_document_refresh_node(state: ConversationAgentState) -> ConversationAgentState:
    result = context_document_service.refresh_context_documents(
        user_id=uuid.UUID(state["user_id"]),
        companion_id=uuid.UUID(state["companion_id"]),
        conversation_id=uuid.UUID(state["conversation_id"]),
        reason="post_turn_refresh",
    )
    state["context_document_ids"] = [item["id"] for item in result.get("documents", [])]
    state.setdefault("trace_steps", []).append({
        "step": "context_document_refresh",
        "order": 112,
        "status": "completed" if result.get("outcome") == "refreshed" else "skipped",
        "outcome": result.get("outcome"),
        "reason": result.get("reason"),
        "document_ids": state["context_document_ids"],
    })
    return state
