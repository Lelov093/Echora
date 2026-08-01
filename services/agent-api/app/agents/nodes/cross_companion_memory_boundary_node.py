"""Companion Reoriented node: surface cross-companion memory review boundaries."""

import uuid

from sqlalchemy import or_, select

from app.agents.state import ConversationAgentState
from app.db.models import CrossCompanionMemoryEvent, CrossCompanionMemoryReview
from app.services.cross_companion_review_service import get_session


def cross_companion_memory_boundary_node(state: ConversationAgentState) -> ConversationAgentState:
    companion_ids = {
        state.get("companion_id"),
        *[
            item.get("companion_id")
            for item in state.get("co_present_companions", [])
            if item.get("companion_id")
        ],
    }
    companion_ids.discard(None)
    if len(companion_ids) <= 1:
        state["cross_companion_memory_reviews"] = []
        state.setdefault("trace_steps", []).append({
            "step": "cross_companion_memory_boundary",
            "order": 106,
            "status": "skipped",
            "reason": "single_companion_context",
        })
        return state

    companion_uuid_ids = [uuid.UUID(item) for item in companion_ids]
    with get_session() as s:
        rows = s.execute(
            select(CrossCompanionMemoryReview, CrossCompanionMemoryEvent)
            .join(
                CrossCompanionMemoryEvent,
                CrossCompanionMemoryReview.cross_companion_memory_event_id == CrossCompanionMemoryEvent.id,
            )
            .where(
                or_(
                    CrossCompanionMemoryEvent.source_companion_id.in_(companion_uuid_ids),
                    CrossCompanionMemoryEvent.target_companion_id.in_(companion_uuid_ids),
                )
            )
            .order_by(CrossCompanionMemoryReview.created_at.desc())
            .limit(10)
        ).all()

    reviews = [
        {
            "review_id": str(review.id),
            "event_id": str(event.id),
            "decision": review.decision,
            "event_status": event.status,
            "source_companion_id": str(event.source_companion_id),
            "target_companion_id": str(event.target_companion_id),
            "event_type": event.event_type,
            "review_required": event.review_required,
            "review_reason": review.review_reason,
            "policy_json": event.policy_json or {},
            "approved_policy_json": review.approved_policy_json or {},
        }
        for review, event in rows
    ]
    state["cross_companion_memory_reviews"] = reviews
    if any(item.get("decision") == "pending" for item in reviews):
        state.setdefault("warnings", []).append("Cross-companion memory reviews are pending.")

    state.setdefault("trace_steps", []).append({
        "step": "cross_companion_memory_boundary",
        "order": 106,
        "status": "completed",
        "review_count": len(reviews),
        "pending_review_count": len([item for item in reviews if item.get("decision") == "pending"]),
    })
    return state
