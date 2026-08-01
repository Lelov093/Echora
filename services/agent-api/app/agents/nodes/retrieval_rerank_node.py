"""RetrievalRerankNode — records rerank details in trace steps.

The retrieval itself is done in MemoryRetrievalNode; this node records
trace details and applies basic reinforcement to selected memories.
"""

import uuid
from datetime import datetime, timezone

from app.agents.state import ConversationAgentState
from app.memory.reinforcement import apply_reinforcement
from app.services.memory_service import update_memory as update_mem


def retrieval_rerank_node(state: ConversationAgentState) -> ConversationAgentState:
    selected = state.get("selected_memories", [])

    # Apply light reinforcement for recalled memories
    for sel in selected:
        try:
            mid = uuid.UUID(sel["id"])
            curr_str = sel.get("memory_strength", 0.5)
            result = apply_reinforcement(
                current_strength=float(curr_str) if curr_str else 0.5,
                successful_recall=True,
            )
            update_mem(mid, {
                "memory_strength": result["new_strength"],
                "reactivation_count": None,  # handled separately
                "last_reactivated_at": datetime.now(timezone.utc),
            })
        except Exception:
            pass

    state.setdefault("trace_steps", []).append({
        "step": "retrieval_rerank",
        "order": 4,
        "status": "completed",
        "selected_memory_ids": [s.get("id") for s in selected],
        "scores": [s.get("retrieval_score") for s in selected],
        "rank_changes": [
            {
                "memory_id": item.get("id"),
                "rank_before": item.get("rank_before"),
                "rank_after": item.get("rank_after"),
                "candidate_source": item.get("candidate_source"),
            }
            for item in selected
        ],
        "score_json": [
            {
                "memory_id": item.get("id"),
                "score": item.get("score_json", {}),
            }
            for item in selected
        ],
        "learned_shadow": next(
            (
                step.get("learned_shadow")
                for step in reversed(state.get("trace_steps", []))
                if step.get("step") == "memory_retrieval"
            ),
            {
                "policy_mode": "shadow",
                "user_visible_policy": "heuristic",
                "fallback_reason": "missing_memory_retrieval_trace",
            },
        ),
    })
    return state
