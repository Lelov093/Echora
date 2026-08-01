"""BoundaryCheckNode — checks settings before proceeding."""

from app.agents.state import ConversationAgentState


def boundary_check_node(state: ConversationAgentState) -> ConversationAgentState:
    bs = state.get("boundary_settings", {})
    check = {
        "allow_memory_candidates": bs.get("allow_memory_candidates", True),
        "allow_presence": bs.get("allow_presence", True),
        "trace_enabled": bs.get("trace_enabled", True),
        "proactive_level": bs.get("proactive_level", "medium"),
        "memory_save_policy": bs.get("memory_save_policy", "review_important"),
    }
    state["boundary_check"] = check

    state.setdefault("trace_steps", []).append({
        "step": "boundary_check",
        "order": 1,
        "status": "completed",
        "output": check,
    })
    return state
