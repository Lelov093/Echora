"""Load one Companion-scoped context contract before response planning."""

from app.agents.state import ConversationAgentState
from app.services.companion_context_snapshot_service import (
    build_companion_context_snapshot,
)


def companion_context_snapshot_node(
    state: ConversationAgentState,
) -> ConversationAgentState:
    snapshot = build_companion_context_snapshot(state)
    state["companion_context_snapshot"] = snapshot

    unavailable = [
        key
        for key, availability in snapshot["availability"].items()
        if availability in {"unavailable", "scope_mismatch"}
    ]
    if unavailable:
        state.setdefault("warnings", []).append(
            "Companion context unavailable for: " + ", ".join(unavailable)
        )

    state.setdefault("trace_steps", []).append({
        "step": "companion_context_snapshot",
        "order": 5,
        "status": "completed",
        "contract_version": snapshot["contract_version"],
        "scope": snapshot["scope"],
        "availability": snapshot["availability"],
        "sources": {
            key: snapshot[key]["source"]
            for key in snapshot["availability"]
        },
    })
    return state
