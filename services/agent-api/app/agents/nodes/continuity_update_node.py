"""ContinuityUpdateNode — refreshes continuity snapshot after presence."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import continuity_service


def continuity_update_node(state: ConversationAgentState) -> ConversationAgentState:
    companion_id = state["companion_id"]
    conversation_id = state.get("conversation_id")

    snapshot_data = {
        "user_id": state["user_id"],
        "companion_id": companion_id,
        "conversation_id": conversation_id,
        "trace_run_id": state.get("trace_run_id"),
        "snapshot_type": "agent_run",
        "mode_key": state.get("current_mode", "project"),
        "current_topic": state.get("conversation", {}).get("current_topic"),
        "current_goal": state.get("conversation", {}).get("current_goal"),
        "last_user_intent": state.get("user_input", "")[:200],
        "last_assistant_summary": (state.get("assistant_response", "")[:200])
        if state.get("assistant_response") else None,
        "relevant_memory_ids": [m.get("id") for m in state.get("selected_memories", []) if m.get("id")],
        "relevant_presence_opportunity_ids": [
            o.get("id") for o in state.get("presence_opportunities", []) if o.get("id")
        ],
        "continuity_score": _estimate_continuity(state),
        "freshness_score": 0.7,
        "snapshot_json": {
            "summary_through_message_id": state.get("user_message_id"),
            "source_trace_run_id": state.get("trace_run_id"),
            "scope": {
                "user_id": state.get("user_id"),
                "companion_id": companion_id,
                "conversation_id": conversation_id,
            },
        },
    }

    try:
        result = continuity_service.refresh_continuity(snapshot_data)
        snapshot_id = result["id"]
    except Exception:
        snapshot_id = None

    state["continuity_snapshot_id"] = snapshot_id
    state["continuity_summary"] = {
        "snapshot_id": snapshot_id,
        "snapshot_type": "agent_run",
        "mode_key": state.get("current_mode", "project"),
        "current_topic": state.get("conversation", {}).get("current_topic"),
        "current_goal": state.get("conversation", {}).get("current_goal"),
        "selected_memory_count": len(state.get("selected_memories", [])),
        "presence_opportunity_count": len(state.get("presence_opportunities", [])),
    }

    state.setdefault("trace_steps", []).append({
        "step": "continuity_update",
        "order": 9,
        "status": "completed" if snapshot_id else "warning",
        "snapshot_id": snapshot_id,
        "continuity_score": _estimate_continuity(state),
    })
    return state


def _estimate_continuity(state: ConversationAgentState) -> float:
    """Simple heuristic for continuity score."""
    score = 0.5
    selected_count = len(state.get("selected_memories", []))
    po_count = len(state.get("presence_opportunities", []))
    if selected_count > 0:
        score += min(0.2, selected_count * 0.05)
    if po_count > 0:
        score += 0.1
    if state.get("assistant_response"):
        score += 0.1
    return min(1.0, score)
