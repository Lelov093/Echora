"""MemoryImpactNode — records memory usage events for selected memories.

Placed AFTER retrieval_rerank, BEFORE response_planning.
"""

import uuid

from app.agents.state import ConversationAgentState
from app.services import memory_usage_service


def memory_impact_node(state: ConversationAgentState) -> ConversationAgentState:
    selected = state.get("selected_memories", [])
    usage_event_ids: list[str] = []

    for mem in selected:
        try:
            data = {
                "user_id": state["user_id"],
                "companion_id": state["companion_id"],
                "conversation_id": state.get("conversation_id"),
                "trace_run_id": state.get("trace_run_id"),
                "memory_id": mem["id"],
                "event_type": "used_in_response",
                "retrieval_score": mem.get("retrieval_score"),
                "selected_for_context": True,
                "used_in_response": True,
                "why_selected": f"Selected for retrieval at rank {mem.get('retrieval_score', 'N/A')}",
                "score_json": {
                    "source": "retrieval_rerank",
                    "scores": mem.get("scores", {}),
                },
            }
            result = memory_usage_service.create_memory_usage_event(data)
            usage_event_ids.append(result["id"])
        except Exception as e:
            logger.warning(f"Failed to create memory usage event for memory {mem.get('id')}: {e}")

    impact_summary = {
        "used_count": len(selected),
        "selected_memory_ids": [s.get("id") for s in selected],
        "usage_event_ids": usage_event_ids,
        "impact_note": (
            f"{len(usage_event_ids)} usage event(s) recorded "
            f"for {len(selected)} selected memor{'y' if len(selected) == 1 else 'ies'}"
        ),
    }

    state["memory_usage_event_ids"] = usage_event_ids
    state["memory_impact_summary"] = impact_summary

    state.setdefault("trace_steps", []).append({
        "step": "memory_impact",
        "order": 5,
        "status": "completed",
        "usage_event_ids": usage_event_ids,
        "selected_memory_count": len(selected),
        "impact_note": impact_summary["impact_note"],
    })
    return state
