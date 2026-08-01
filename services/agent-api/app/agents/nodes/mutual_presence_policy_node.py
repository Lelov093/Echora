"""Companion Reoriented node: create co-presence-aware presence guidance."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import (
    co_presence_service,
    group_persona_consistency_service,
    mutual_presence_service,
)


def mutual_presence_policy_node(state: ConversationAgentState) -> ConversationAgentState:
    co_presence_session = state.get("co_presence_session") or {}
    shared_scene = state.get("shared_scene") or {}
    if not co_presence_session and not shared_scene:
        state.setdefault("trace_steps", []).append({
            "step": "mutual_presence_policy",
            "order": 109,
            "status": "skipped",
            "reason": "no_companion_context",
        })
        return state

    if state.get("presence_opportunities"):
        state.setdefault("trace_steps", []).append({
            "step": "mutual_presence_policy",
            "order": 109,
            "status": "completed",
            "action": "reuse_existing_presence_opportunities",
            "presence_opportunity_count": len(state.get("presence_opportunities", [])),
        })
        return state

    utility = (
        (state.get("participant_awareness") or {}).get(
            "co_presence_utility"
        )
        or {}
    )
    group_gate = group_persona_consistency_service.check_group_persona_consistency(
        co_presence_session_id=(
            uuid.UUID(co_presence_session["id"])
            if co_presence_session.get("id")
            else None
        ),
        shared_scene_id=(
            uuid.UUID(shared_scene["id"])
            if shared_scene.get("id")
            else None
        ),
        payload={
            "source_trace_run_id": state.get("trace_run_id"),
            "interaction_samples": [state.get("user_input", "")],
            "consistency_scope": (
                "shared_scene" if shared_scene else "co_presence_session"
            ),
        },
    )
    gated_utility = co_presence_service.apply_group_persona_gate(
        utility,
        group_gate,
    )
    invite = gated_utility.get("invite_recommendation") or {}
    target_companion = next(
        (
            item
            for item in state.get("co_present_companions", [])
            if invite.get("allowed")
            and item.get("companion_id")
            == invite.get("target_companion_id")
        ),
        None,
    )
    persona_guard = state.get("persona_guard_result") or {}
    if (
        str(persona_guard.get("check_status") or "").lower() == "blocked"
        or bool(persona_guard.get("blocks_auto_apply"))
    ):
        target_companion = None
        invite = {
            **invite,
            "allowed": False,
            "target_companion_id": None,
            "reason": "active_companion_persona_guard_veto",
        }
        gated_utility["invite_recommendation"] = invite

    result = mutual_presence_service.create_companion_presence_opportunity(
        uuid.UUID(state["companion_id"]),
        {
            "user_id": state["user_id"],
            "conversation_id": state["conversation_id"],
            "trace_run_id": state.get("trace_run_id"),
            "co_presence_session_id": (
                co_presence_session.get("id")
                if target_companion
                else None
            ),
            "shared_scene_id": shared_scene.get("id"),
            "target_companion_id": target_companion.get("companion_id") if target_companion else None,
            "target_role": target_companion.get("participant_role") if target_companion else "active_companion",
            "type": "shared_reflection" if shared_scene else "co_presence_invite",
            "title": shared_scene.get("scene_title") or co_presence_session.get("session_title") or "Co-presence follow-up",
            "message": shared_scene.get("scene_summary")
            or co_presence_session.get("session_summary")
            or "Coordinate the next co-presence step.",
            "reason": invite.get("reason")
            or "co_presence_utility_no_expansion",
            "prefer_scene_surface": bool(shared_scene),
            "prefer_session_surface": bool(co_presence_session) and not bool(shared_scene),
            "requires_user_confirmation": bool(target_companion),
            "review_required": bool(
                (group_gate or {}).get("requires_review")
            ),
            "opportunity_origin": "manual",
            "mutuality_score": invite.get("utility", 0.0),
            "presence_value": invite.get("utility", 0.0),
            "rationale_summary": invite.get("reason"),
            "boundary_json": {
                "persona_guard_status": persona_guard.get("check_status"),
                "group_persona_gate_status": (
                    (group_gate or {}).get("check_status")
                ),
            },
            "signal_json": {
                "co_presence_utility": gated_utility,
            },
        },
    )
    if result:
        base_presence = result.get("base_presence_opportunity")
        if base_presence:
            state.setdefault("presence_opportunities", []).append(base_presence)
        policy_run = result.get("policy_run") or {}
        if policy_run.get("id"):
            state.setdefault("presence_policy_run_ids", []).append(policy_run["id"])

    state.setdefault("trace_steps", []).append({
        "step": "mutual_presence_policy",
        "order": 109,
        "status": "completed",
        "presence_opportunity_id": (result or {}).get("base_presence_opportunity", {}).get("id"),
        "selected_surface": (result or {}).get("base_presence_opportunity", {}).get("recommended_surface"),
        "policy_run_id": (result or {}).get("policy_run", {}).get("id"),
        "shadow_policy": (result or {}).get("shadow_policy", {}),
        "policy_mode": "shadow",
        "user_visible_policy": "heuristic",
        "co_presence_utility": gated_utility,
        "group_persona_gate": group_gate,
        "invited_companion_id": (
            target_companion.get("companion_id")
            if target_companion
            else None
        ),
        "invitation_reason": invite.get("reason"),
    })
    return state
