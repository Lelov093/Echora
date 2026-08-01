"""Companion Reoriented node: compute active companion memory scope under co-presence policy."""

import uuid

from sqlalchemy import select

from app.agents.state import ConversationAgentState
from app.db.models import CompanionMemoryScope
from app.services import companion_contract_service, companion_memory_service
from app.services.companion_memory_service import get_session


def companion_memory_scope_node(state: ConversationAgentState) -> ConversationAgentState:
    companion_id = uuid.UUID(state["companion_id"])
    boundary = companion_contract_service.get_boundary(companion_id) or {}
    session = state.get("co_presence_session") or {}
    policy = session.get("policy") or {}

    with get_session() as s:
        scope = s.execute(
            select(CompanionMemoryScope)
            .where(
                CompanionMemoryScope.companion_id == companion_id,
                CompanionMemoryScope.scope_status == "active",
            )
            .order_by(CompanionMemoryScope.created_at.asc())
        ).scalar_one_or_none()

    visible_memories = companion_memory_service.list_companion_memories(companion_id, page=1, page_size=3)
    participant_permission = _resolve_active_participant_permission(state)

    scope_bundle = {
        "companion_id": state["companion_id"],
        "scope_id": str(scope.id) if scope else None,
        "scope_type": scope.scope_type if scope else "private_companion",
        "scope_key": scope.scope_key if scope else "default",
        "default_write_policy": scope.default_write_policy if scope else "private_only",
        "private_memory_default": boundary.get("private_memory_default", "private_candidate"),
        "shared_memory_default": boundary.get("shared_memory_default", "candidate_review"),
        "global_memory_read_scope": policy.get("user_global_memory_scope")
        or boundary.get("global_memory_read_scope"),
        "cross_companion_private_read_policy": policy.get("cross_companion_private_read_policy")
        or boundary.get("cross_companion_read_policy"),
        "participant_memory_permission": participant_permission,
        "visible_memory_count": visible_memories.get("total", 0),
        "visible_memory_samples": [
            {
                "id": str(item.id),
                "type": item.type,
                "memory_scope_type": item.memory_scope_type,
                "summary": item.summary,
            }
            for item in visible_memories.get("items", [])
        ],
    }
    state["companion_memory_scope"] = scope_bundle

    state.setdefault("trace_steps", []).append({
        "step": "companion_memory_scope",
        "order": 105,
        "status": "completed",
        "scope_type": scope_bundle["scope_type"],
        "default_write_policy": scope_bundle["default_write_policy"],
        "global_memory_read_scope": scope_bundle["global_memory_read_scope"],
        "visible_memory_count": scope_bundle["visible_memory_count"],
    })
    return state


def _resolve_active_participant_permission(state: ConversationAgentState) -> dict:
    session = state.get("co_presence_session") or {}
    for participant in session.get("participants", []):
        if participant.get("participant_companion_id") == state.get("companion_id"):
            return participant.get("memory_permission") or {}
    return {}
