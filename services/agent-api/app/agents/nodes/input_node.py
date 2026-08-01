"""InputNode — entry point of ConversationRun.

Validates conversation, creates user message + trace_run.
"""

import uuid
from datetime import datetime, timezone

from app.agents.state import ConversationAgentState
from app.services.conversation_service import create_message
from app.services.trace_service import get_session as trace_session
from app.db.models import (
    TraceRun, Memory, Conversation, Message, CompanionRoomTurn, CompanionRoomTurnStep,
    CoPresenceParticipant,
)
from app.db.models.user import User
from app.db.models.companion import Companion
from app.db.models.settings import BoundarySetting


def input_node(state: ConversationAgentState) -> ConversationAgentState:
    now = datetime.now(timezone.utc)
    uid = uuid.UUID(state["user_id"])
    cid = uuid.UUID(state["companion_id"])
    conv_id = uuid.UUID(state["conversation_id"])

    s = trace_session()

    # Load conversation
    conv = s.query(Conversation).get(conv_id)
    if not conv:
        state.setdefault("errors", []).append({"step": "input", "message": "Conversation not found"})
        s.close()
        return state
    if conv.deleted_at is not None or conv.status != "active":
        state.setdefault("errors", []).append({
            "step": "input",
            "code": "CONVERSATION_NOT_ACTIVE",
            "message": "Conversation is not active",
        })
        s.close()
        return state
    room_scope_valid = _valid_room_turn_scope(s, state, conv, uid, cid)
    if conv.user_id != uid or (conv.companion_id != cid and not room_scope_valid):
        state.setdefault("errors", []).append({
            "step": "input",
            "code": "CONVERSATION_SCOPE_MISMATCH",
            "message": "Conversation owner or Companion scope mismatch",
        })
        s.close()
        return state

    # durable turn application service atomically claims the user message and Trace.
    # Direct compatibility runner calls retain the former creation path.
    if state.get("user_message_id") and state.get("trace_run_id"):
        user_msg = s.get(Message, uuid.UUID(state["user_message_id"]))
        tr = s.get(TraceRun, uuid.UUID(state["trace_run_id"]))
        if (
            user_msg is None or tr is None
            or user_msg.user_id != uid
            or (user_msg.companion_id != cid and not room_scope_valid)
            or user_msg.conversation_id != conv_id or tr.message_id != user_msg.id
        ):
            state.setdefault("errors", []).append({
                "step": "input",
                "code": "TURN_CLAIM_SCOPE_MISMATCH",
                "message": "Preclaimed turn scope mismatch",
            })
            s.close()
            return state
    else:
        user_msg = create_message({
            "user_id": uid, "companion_id": cid, "conversation_id": conv_id,
            "role": "user", "content": state["user_input"],
        })
        state["user_message_id"] = str(user_msg.id)
        tr = TraceRun(
            user_id=uid, companion_id=cid, conversation_id=conv_id,
            message_id=user_msg.id,
            agent_graph_name="conversation_graph",
            status="started",
            input_summary=state["user_input"][:200] if state["user_input"] else None,
            metadata_={"turn_idempotency_key": state.get("turn_idempotency_key")},
        )
        s.add(tr)
        s.flush()
        state["trace_run_id"] = str(tr.id)

    # Load boundary settings
    bs = s.query(BoundarySetting).filter(
        BoundarySetting.companion_id == cid
    ).first()
    state["boundary_settings"] = {
        "memory_save_policy": bs.memory_save_policy if bs else "review_important",
        "proactive_level": bs.proactive_level if bs else "medium",
        "notification_surface": bs.notification_surface if bs else "hub_queue_only",
        "allow_memory_candidates": conv.retention_mode != "temporary" and conv.cross_session_memory_enabled,
        "allow_proactive_presence": bs.allow_proactive_presence if bs else True,
        "allow_presence": bs.allow_proactive_presence if bs else True,
        "suppressed_presence_types": list(bs.suppressed_presence_types or []) if bs else [],
        "quiet_hours": dict(bs.quiet_hours or {}) if bs else {},
        "max_presence_per_day": bs.max_presence_per_day if bs else None,
        "min_presence_interval_minutes": bs.min_presence_interval_minutes if bs else None,
        "meaningful_silence_enabled": bs.meaningful_silence_enabled if bs else True,
        "trace_enabled": True,
    }

    # Load companion
    comp = s.query(Companion).get(cid)
    state["companion_profile"] = {
        "name": comp.name if comp else "Echora",
        "current_mode": comp.current_mode if comp else "project",
        "base_personality": comp.base_personality if comp else "warm, precise, structured",
    }

    # Conversation summary
    state["conversation"] = {
        "title": conv.title, "current_topic": conv.current_topic,
        "current_goal": conv.current_goal,
        "co_presence_session_id": str(conv.co_presence_session_id) if conv.co_presence_session_id else None,
        "shared_scene_id": str(conv.shared_scene_id) if conv.shared_scene_id else None,
        "retention_mode": conv.retention_mode,
        "cross_session_memory_enabled": conv.cross_session_memory_enabled,
        "retention_expires_at": conv.retention_expires_at.isoformat() if conv.retention_expires_at else None,
        "room_continuation_capsule": (conv.continuity_state or {}).get("room_continuation_capsule"),
    }

    # Mode
    state["current_mode"] = state.get("current_mode") or "project"

    # Trace step
    state.setdefault("trace_steps", []).append({
        "step": "input",
        "order": 0,
        "status": "completed",
        "message": "Input validated, user message and trace_run created",
    })

    s.commit()
    s.close()
    return state


def _valid_room_turn_scope(s, state, conversation, user_id, companion_id) -> bool:
    """Permit a non-primary Companion only through a durable Room Turn Step."""
    turn_id = state.get("room_turn_id")
    step_id = state.get("room_turn_step_id")
    if not turn_id or not step_id or conversation.co_presence_session_id is None:
        return False
    try:
        turn = s.get(CompanionRoomTurn, uuid.UUID(turn_id))
        step = s.get(CompanionRoomTurnStep, uuid.UUID(step_id))
    except (TypeError, ValueError):
        return False
    if (
        turn is None or step is None or step.room_turn_id != turn.id
        or turn.user_id != user_id or turn.conversation_id != conversation.id
        or turn.co_presence_session_id != conversation.co_presence_session_id
        or step.user_id != user_id or step.companion_id != companion_id
        or step.status not in {"planned", "running"}
    ):
        return False
    participant = s.get(CoPresenceParticipant, step.participant_id)
    return bool(
        participant
        and participant.co_presence_session_id == turn.co_presence_session_id
        and participant.participant_companion_id == companion_id
        and participant.join_status == "active"
        and participant.can_speak
        and participant.participant_role != "observing_companion"
    )
