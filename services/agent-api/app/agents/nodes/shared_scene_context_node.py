"""Companion Reoriented node: load shared scene context for the active conversation."""

import uuid

from app.agents.state import ConversationAgentState
from app.db.models import Conversation
from app.services.shared_scene_service import get_shared_scene_bundle
from app.services.trace_service import get_session


def shared_scene_context_node(state: ConversationAgentState) -> ConversationAgentState:
    conversation_id = uuid.UUID(state["conversation_id"])

    with get_session() as s:
        conversation = s.get(Conversation, conversation_id)
        scene_id = conversation.shared_scene_id if conversation else None

    if scene_id is None:
        session = state.get("co_presence_session") or {}
        scene_ids = session.get("shared_scene_ids") or []
        if scene_ids:
            scene_id = uuid.UUID(scene_ids[-1])

    if scene_id is None:
        state["shared_scene"] = {}
        state.setdefault("trace_steps", []).append({
            "step": "shared_scene_context",
            "order": 104,
            "status": "skipped",
            "reason": "conversation_has_no_shared_scene",
        })
        return state

    scene_bundle = get_shared_scene_bundle(scene_id) or {}
    state["shared_scene"] = scene_bundle

    conversation_state = dict(state.get("conversation") or {})
    conversation_state["shared_scene_id"] = str(scene_id)
    if scene_bundle.get("focal_topic") and not conversation_state.get("current_topic"):
        conversation_state["current_topic"] = scene_bundle.get("focal_topic")
    state["conversation"] = conversation_state

    state.setdefault("trace_steps", []).append({
        "step": "shared_scene_context",
        "order": 104,
        "status": "completed",
        "shared_scene_id": scene_bundle.get("id"),
        "scene_status": scene_bundle.get("scene_status"),
        "event_count": len(scene_bundle.get("events", [])),
        "shared_experience_count": len(scene_bundle.get("shared_experiences", [])),
    })
    return state
