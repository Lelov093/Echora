"""Companion Reoriented node: derive participant awareness and co-present companions."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import co_presence_service


def participant_awareness_node(state: ConversationAgentState) -> ConversationAgentState:
    session = state.get("co_presence_session") or {}
    participants = session.get("participants", [])
    if not participants:
        state["participant_awareness"] = {}
        state["co_present_companions"] = []
        state.setdefault("trace_steps", []).append({
            "step": "participant_awareness",
            "order": 103,
            "status": "skipped",
            "reason": "no_co_presence_participants",
        })
        return state

    awareness_summary = {
        "participant_count": len(participants),
        "active_participant_count": 0,
        "active_companion_count": 0,
        "observing_companion_count": 0,
        "participants": [],
    }
    co_present_companions: list[dict] = []

    for participant in participants:
        role = participant.get("participant_role")
        join_status = participant.get("join_status")
        memory_permission = participant.get("memory_permission") or {}
        awareness_states = participant.get("awareness_states") or []

        if join_status == "active":
            awareness_summary["active_participant_count"] += 1
        if participant.get("participant_type") == "companion" and join_status == "active":
            companion_summary = {
                "participant_id": participant.get("id"),
                "companion_id": participant.get("participant_companion_id"),
                "participant_role": role,
                "join_status": join_status,
                "visibility_scope": participant.get("visibility_scope"),
                "can_speak": participant.get("can_speak"),
                "can_delegate": participant.get("can_delegate"),
                "memory_permission": memory_permission,
            }
            co_present_companions.append(companion_summary)
            if role == "observing_companion":
                awareness_summary["observing_companion_count"] += 1
            else:
                awareness_summary["active_companion_count"] += 1

        awareness_summary["participants"].append({
            "participant_id": participant.get("id"),
            "participant_type": participant.get("participant_type"),
            "participant_role": role,
            "join_status": join_status,
            "participant_companion_id": participant.get("participant_companion_id"),
            "participant_user_id": participant.get("participant_user_id"),
            "memory_participation_override": memory_permission.get("memory_participation_override"),
            "allow_private_candidate": memory_permission.get("allow_private_candidate"),
            "allow_shared_candidate": memory_permission.get("allow_shared_candidate"),
            "allow_cross_companion_private_read": memory_permission.get("allow_cross_companion_private_read"),
            "review_required": memory_permission.get("review_required"),
            "awareness_states": awareness_states,
        })

    utility = co_presence_service.build_co_presence_utility_decision(
        uuid.UUID(state["companion_id"]),
        co_present_companions,
        context={
            "mode": state.get("current_mode", "conversation"),
            "has_goal": bool(
                (state.get("conversation") or {}).get("current_goal")
            ),
            "has_shared_scene": bool(state.get("shared_scene")),
            "shared_scene_id": (state.get("shared_scene") or {}).get("id"),
            "boundary_risk": 0.0,
        },
    )
    by_companion = {
        item["companion_id"]: item for item in utility["candidates"]
    }
    for companion in co_present_companions:
        scored = by_companion.get(companion.get("companion_id"), {})
        companion["speaker_status"] = scored.get(
            "speaker_status",
            "observing",
        )
        companion["co_presence_utility"] = scored.get("utility", 0.0)
        companion["utility_veto_reasons"] = scored.get("veto_reasons", [])
    awareness_summary["co_presence_utility"] = utility
    awareness_summary["selected_speaker_companion_id"] = utility.get(
        "selected_speaker_companion_id"
    )

    state["participant_awareness"] = awareness_summary
    state["co_present_companions"] = co_present_companions
    state.setdefault("trace_steps", []).append({
        "step": "participant_awareness",
        "order": 103,
        "status": "completed",
        "participant_count": awareness_summary["participant_count"],
        "active_companion_count": awareness_summary["active_companion_count"],
        "observing_companion_count": awareness_summary["observing_companion_count"],
        "selected_speaker_companion_id": utility.get(
            "selected_speaker_companion_id"
        ),
        "speaker_count": utility.get("speaker_count"),
        "co_presence_utility": utility,
    })
    return state
