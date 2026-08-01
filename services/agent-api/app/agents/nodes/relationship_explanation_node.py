"""RelationshipExplanationNode — creates explanation events from correction/growth signals."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import relationship_explanation_service


def relationship_explanation_node(state: ConversationAgentState) -> ConversationAgentState:
    """Check growth candidates and relationship candidates for explanation events.

    If growth_candidates have correction signals or relationship_candidates exist,
    create relationship_explanation_events for each qualifying candidate.
    """
    explanation_ids: list[str] = []
    failed_count = 0
    growth_candidates = state.get("growth_candidates", [])
    relationship_candidates = state.get("relationship_candidates", [])

    # Process growth candidates with correction signals
    for gc in growth_candidates:
        # Use correction factors from growth triggers
        # If the growth candidate exists, check if it has correction-related attributes
        content = gc.get("content", "")
        gc_type = gc.get("type", "")

        # Simple rule: if correction or understanding update, create explanation
        if "correction" in content.lower() or "修正" in content or "不对" in content:
            failed_count += not _create_explanation(
                state, gc, "understanding",
                f"User provided a correction: {content[:200]}",
                explanation_ids,
            )
        elif gc_type == "understanding_update":
            failed_count += not _create_explanation(
                state, gc, "understanding",
                f"Understanding update detected: {content[:200]}",
                explanation_ids,
            )

    # Relationship candidates deliberately remain unlinked pending evidence.
    # Their explanation events are created atomically only when a user commits
    # the candidate, so Chronicle never presents a proposal as relationship truth.

    state["relationship_explanation_ids"] = explanation_ids

    state.setdefault("trace_steps", []).append({
        "step": "relationship_explanation",
        "order": 11,
        "status": "warning" if failed_count else "completed",
        "explanation_ids": explanation_ids,
        "explanations_generated": len(explanation_ids),
        "growth_candidates_checked": len(growth_candidates),
        "relationship_candidates_checked": len(relationship_candidates),
        "failed_count": failed_count,
    })
    return state


def _create_explanation(
    state: ConversationAgentState,
    candidate: dict,
    dimension: str,
    explanation: str,
    explanation_ids: list[str],
) -> bool:
    """Create a relationship explanation event and collect its ID."""
    try:
        data = {
            "user_id": state["user_id"],
            "companion_id": state["companion_id"],
            "conversation_id": state.get("conversation_id"),
            "trace_run_id": state.get("trace_run_id"),
            "dimension": dimension,
            "explanation": explanation,
            "title": f"{dimension.capitalize()} update from agent run",
            "confidence": candidate.get("confidence", 0.7),
            "user_visible": True,
            "user_confirmed": False,
            "evidence_growth_record_ids": [candidate.get("id")] if candidate.get("id") else [],
        }
        result = relationship_explanation_service.create_explanation(data)
        explanation_ids.append(result["id"])
        return True
    except Exception:
        return False
