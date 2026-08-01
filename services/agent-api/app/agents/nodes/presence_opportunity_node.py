"""PresenceOpportunityNode — uses scoring + boundary gate.

Core conversation: heuristic priority scoring with boundary check.
Only writes to queue/hub, never sends system notifications.
"""

import uuid

from app.agents.state import ConversationAgentState
from app.presence.scoring import personalize_presence_priority, score_presence_priority
from app.presence.boundary import check_boundary
from app.services.presence_service import (
    evaluate_presence_suppression,
    get_presence_feedback_profile,
    get_session,
)
from app.db.models.presence import PresenceOpportunity


def presence_opportunity_node(state: ConversationAgentState) -> ConversationAgentState:
    user_input = state.get("user_input", "")
    selected = state.get("selected_memories", [])
    growth = state.get("growth_candidates", [])
    bs = state.get("boundary_settings", {})

    # Score
    priority = score_presence_priority(
        user_input=user_input,
        selected_memories=selected,
        memory_importance=0.4 if selected else 0.1,
        growth_relevance=0.3 if growth else 0.0,
    )

    presence_type = "continuation"
    uid = uuid.UUID(state["user_id"])
    cid = uuid.UUID(state["companion_id"])
    conv_id_str = state.get("conversation_id")
    conv_id = uuid.UUID(conv_id_str) if conv_id_str else None
    feedback_profile = get_presence_feedback_profile(
        cid,
        presence_type,
        priority["recommended_surface"],
    )
    priority = personalize_presence_priority(
        priority,
        acceptance_rate=feedback_profile["acceptance_rate"],
        recent_dismissal_penalty=feedback_profile["recent_dismissal_penalty"],
    )
    suppression = evaluate_presence_suppression(
        uid,
        cid,
        presence_type,
        min_interval_seconds=1800,
    )

    # Boundary check
    boundary = check_boundary(
        boundary_settings=bs,
        priority_score=priority["score"],
        presence_type=presence_type,
        interruption_risk=0.1,
        sensitivity_risk=0.05,
        recent_dismissal_count=int(feedback_profile["negative_signals"]),
        recommended_surface=priority["recommended_surface"],
    )

    opportunities = []
    if priority["create_opportunity"] and boundary["allowed"] and not suppression["suppress"]:
        s = get_session()
        opp = PresenceOpportunity(
            user_id=uid, companion_id=cid, conversation_id=conv_id,
            type=presence_type,
            title=f"Continue: {user_input[:80]}",
            message=f"You mentioned wanting to continue: {user_input[:200]}",
            reason=priority["reason"],
            priority=priority["score"],
            urgency=0.3, sensitivity=0.05, interruption_risk=0.1,
            recommended_surface=boundary["surface"],
            status="queued",
            score_json={
                "priority": priority["score"],
                "factors": priority["factors"],
                "boundary": boundary,
                "feedback_profile": feedback_profile,
                "personalization": priority["personalization"],
            },
            calibration_json={
                "feedback_profile": feedback_profile,
                "personalization": priority["personalization"],
                "policy_mode": "heuristic",
            },
        )
        s.add(opp)
        s.commit()
        opportunities.append({
            "id": str(opp.id), "type": opp.type, "title": opp.title,
            "priority": opp.priority, "recommended_surface": opp.recommended_surface,
            "status": opp.status,
        })
        s.close()

    state["presence_opportunities"] = opportunities
    state.setdefault("trace_steps", []).append({
        "step": "presence_priority",
        "order": 8,
        "status": "completed",
        "score": priority["score"],
        "decision": priority["decision"],
        "factors": priority["factors"],
        "algorithm": priority["algorithm"],
        "score_json": {
            "score": priority["score"],
            "factors": priority["factors"],
            **priority["algorithm"],
        },
        "boundary": boundary,
        "feedback_profile": feedback_profile,
        "personalization": priority["personalization"],
        "suppression": suppression,
        "meaningful_silence_reason": suppression["reason"],
        "recent_same_type_negative_signals": int(feedback_profile["negative_signals"]),
        "opportunities_generated": len(opportunities),
    })
    return state
