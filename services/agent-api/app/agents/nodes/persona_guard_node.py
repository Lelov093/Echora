"""Companion Reoriented node: run persona guard against co-presence context."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import companion_persona_guard_service


def persona_guard_node(state: ConversationAgentState) -> ConversationAgentState:
    co_presence_session = state.get("co_presence_session") or {}
    shared_scene = state.get("shared_scene") or {}
    if not co_presence_session and not shared_scene:
        state["persona_guard_result"] = {}
        state.setdefault("trace_steps", []).append({
            "step": "persona_guard",
            "order": 107,
            "status": "skipped",
            "reason": "no_companion_context",
        })
        return state

    memory_permission = (state.get("companion_memory_scope") or {}).get("participant_memory_permission") or {}
    payload = {
        "source_trace_run_id": state.get("trace_run_id"),
        "co_presence_session_id": co_presence_session.get("id"),
        "shared_scene_id": shared_scene.get("id"),
        "cross_companion_private_read": len(state.get("co_present_companions", [])) > 1,
        "participant_memory_permission_id": memory_permission.get("id"),
    }
    result = companion_persona_guard_service.check_persona_drift(uuid.UUID(state["companion_id"]), payload) or {}
    state["persona_guard_result"] = result
    if result.get("requires_review"):
        state.setdefault("warnings", []).append("Persona guard marked this co-presence context for review.")

    state.setdefault("trace_steps", []).append({
        "step": "persona_guard",
        "order": 107,
        "status": "completed",
        "check_status": result.get("check_status"),
        "drift_risk_level": result.get("drift_risk_level"),
        "requires_review": result.get("requires_review"),
        "blocks_auto_apply": result.get("blocks_auto_apply"),
    })
    return state
