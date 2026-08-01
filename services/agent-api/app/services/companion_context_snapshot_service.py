"""Build the read-only Companion Context Snapshot used by a conversation turn."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.agents.state import ConversationAgentState
from app.services import affect_service, context_document_service, continuity_service, growth_service, presence_service
from app.services.relationship_service import get_relationship_state


CONTRACT_VERSION = "companion-context-snapshot.v1"


def build_companion_context_snapshot(
    state: ConversationAgentState,
) -> dict[str, Any]:
    """Assemble already-approved Companion state without persisting a new record."""
    scope = {
        "user_id": state["user_id"],
        "companion_id": state["companion_id"],
        "conversation_id": state["conversation_id"],
        "visibility": "companion_private",
        "cross_companion_content_included": False,
    }
    active = state.get("active_companion") or {}
    identity = _profile_section(
        active.get("identity"),
        source_type="companion_identity_profile",
        priority_layer="core_identity",
        fields=(
            "display_name",
            "identity_summary",
            "origin_story",
            "self_continuity_summary",
            "core_traits_json",
            "identity_labels_json",
            "voice_style_hint",
            "profile_status",
        ),
        scope=scope,
    )
    persona = _profile_section(
        active.get("persona"),
        source_type="companion_persona_profile",
        priority_layer="core_persona_and_owner_configuration",
        fields=(
            "persona_summary",
            "communication_style_summary",
            "tone_descriptors_json",
            "core_values_json",
            "response_preferences_json",
            "persona_lock_level",
            "drift_guard_level",
            "presence_style",
        ),
        scope=scope,
    )
    contract = _profile_section(
        active.get("relationship_contract"),
        source_type="companion_relationship_contract",
        priority_layer="owner_configuration",
        fields=(
            "relationship_role",
            "contract_status",
            "contract_summary",
            "collaboration_style_summary",
            "support_scope_json",
            "shared_memory_policy",
            "cross_companion_disclosure_policy",
            "contract_json",
        ),
        scope=scope,
    )
    boundary = _profile_section(
        active.get("boundary_profile"),
        source_type="companion_boundary_profile",
        priority_layer="non_bypassable_safety",
        fields=(
            "private_memory_default",
            "shared_memory_default",
            "global_memory_read_scope",
            "cross_companion_read_policy",
            "review_required_private_to_shared",
            "review_required_shared_to_private",
            "review_required_cross_companion_share",
            "presence_interrupt_policy",
            "boundary_json",
        ),
        scope=scope,
    )

    retention = state.get("conversation") or {}
    cross_session_allowed = (
        retention.get("retention_mode") != "temporary"
        and retention.get("cross_session_memory_enabled", True)
    )
    relationship = _load_relationship(scope) if cross_session_allowed else _suppressed_section("relationship_state", scope)
    affect = _load_affect(scope) if cross_session_allowed else _suppressed_section("companion_affect", scope)
    continuity = _load_continuity(scope) if cross_session_allowed else _suppressed_section("continuity_snapshot", scope)
    growth = _load_growth(scope) if cross_session_allowed else _suppressed_section("growth_records", scope)
    memories = _memory_section(state, scope) if cross_session_allowed else _suppressed_section("memory_retrieval", scope)
    context_documents = _load_context_documents(scope) if cross_session_allowed else _suppressed_section("context_documents", scope)
    presence = _presence_section(state, persona, boundary, scope)

    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "priority_order": [
            "non_bypassable_safety",
            "core_identity",
            "core_persona_and_owner_configuration",
            "owner_configuration",
            "reviewed_growth",
            "relationship_and_continuity",
            "bounded_affect_expression",
            "versioned_context_documents",
            "retrieved_turn_context",
        ],
        "identity": identity,
        "persona": persona,
        "relationship_contract": contract,
        "boundary": boundary,
        "relationship": relationship,
        "affect": affect,
        "growth": growth,
        "continuity": continuity,
        "memories": memories,
        "context_documents": context_documents,
        "retention": {
            "mode": retention.get("retention_mode", "standard"),
            "cross_session_memory_enabled": cross_session_allowed,
        },
        "presence": presence,
        "availability": {
            key: value["availability"]
            for key, value in {
                "identity": identity,
                "persona": persona,
                "relationship_contract": contract,
                "boundary": boundary,
                "relationship": relationship,
                "affect": affect,
                "growth": growth,
                "continuity": continuity,
                "memories": memories,
                "context_documents": context_documents,
                "presence": presence,
            }.items()
        },
    }


def _suppressed_section(source_type: str, scope: dict[str, Any]) -> dict[str, Any]:
    return _section(source_type, "conversation_retention_policy", scope, "suppressed", {}, None, None)


def _load_context_documents(scope: dict[str, Any]) -> dict[str, Any]:
    try:
        rows = context_document_service.list_context_documents(
            uuid.UUID(scope["companion_id"]), include_history=False,
        ).get("items", [])
    except Exception:
        rows = []
    items = [
        {
            "id": row["id"],
            "type": row["document_kind"],
            "content": row["content"],
            "version": row["version"],
            "confidence": row["confidence"],
            "source_message_ids": row["source_message_ids"],
            "source_memory_ids": row["source_memory_ids"],
        }
        for row in rows
    ]
    return _section(
        "companion_context_documents", "versioned_context_documents", scope,
        "available" if items else "empty", {"items": items}, None,
        str(max((item["version"] for item in items), default=0)),
    )


def _profile_section(
    payload: dict[str, Any] | None,
    *,
    source_type: str,
    priority_layer: str,
    fields: tuple[str, ...],
    scope: dict[str, Any],
) -> dict[str, Any]:
    if not payload:
        return _section(source_type, priority_layer, scope, "unavailable", {}, None, None)
    if not _matches_scope(payload, scope):
        return _section(source_type, priority_layer, scope, "scope_mismatch", {}, None, None)
    data = {field: payload.get(field) for field in fields if payload.get(field) is not None}
    return _section(
        source_type,
        priority_layer,
        scope,
        "available",
        data,
        str(payload.get("id")) if payload.get("id") else None,
        _as_text(payload.get("updated_at")),
    )


def _load_relationship(scope: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = get_relationship_state(uuid.UUID(scope["companion_id"]))
    except Exception:
        payload = None
    if not payload:
        return _section(
            "relationship_state", "relationship_and_continuity", scope,
            "unavailable", {}, None, None,
        )
    if not _matches_scope(payload, scope):
        return _section(
            "relationship_state", "relationship_and_continuity", scope,
            "scope_mismatch", {}, None, None,
        )
    data = {
        key: payload.get(key)
        for key in (
            "familiarity", "understanding", "collaboration", "trust",
            "emotional_closeness", "boundary_awareness", "continuity", "summary",
            "revision", "uncertainty", "last_evidence_at",
        )
        if payload.get(key) is not None
    }
    return _section(
        "relationship_state", "relationship_and_continuity", scope,
        "available", data, payload.get("id"),
        f"revision:{payload.get('revision', 0)}:{payload.get('updated_at') or ''}",
    )


def _load_continuity(scope: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = continuity_service.get_conversation_continuity(
            uuid.UUID(scope["conversation_id"])
        )
    except Exception:
        payload = None
    if not payload:
        return _section(
            "continuity_snapshot", "relationship_and_continuity", scope,
            "unavailable", {}, None, None,
        )
    if not _matches_scope(payload, scope, include_conversation=True):
        return _section(
            "continuity_snapshot", "relationship_and_continuity", scope,
            "scope_mismatch", {}, None, None,
        )
    data = {
        key: payload.get(key)
        for key in (
            "current_topic", "current_goal", "current_phase", "last_user_intent",
            "last_assistant_summary", "open_threads", "unresolved_decisions",
            "suggested_next_steps", "continuity_score", "freshness_score", "user_confirmed",
            "trace_run_id", "snapshot_json",
        )
        if payload.get(key) not in (None, [], {})
    }
    return _section(
        "continuity_snapshot", "relationship_and_continuity", scope,
        "available", data, payload.get("id"), payload.get("updated_at") or payload.get("created_at"),
    )


def _load_affect(scope: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = affect_service.get_affect_state(uuid.UUID(scope["companion_id"]))
    except Exception:
        payload = None
    if not payload:
        return _section("companion_affect", "bounded_affect_expression", scope, "empty", {}, None, None)
    if str(payload.get("user_id")) != scope["user_id"] or str(payload.get("companion_id")) != scope["companion_id"]:
        return _section("companion_affect", "bounded_affect_expression", scope, "scope_mismatch", {}, None, None)
    data = {
        "expression": payload.get("expression") or {},
        "expression_enabled": payload.get("expression_enabled", True),
        "expression_intensity": payload.get("expression_intensity", "subtle"),
        "safety_contract": "boundary_and_presence_controls_always_override",
        "ontological_claim": "simulated_companion_expression_not_conscious_feeling",
    }
    return _section("companion_affect", "bounded_affect_expression", scope, "available", data,
                    payload.get("current_event_id"), f"revision:{payload.get('revision', 0)}")


def _load_growth(scope: dict[str, Any]) -> dict[str, Any]:
    load_failed = False
    try:
        records = growth_service.list_growth_records(
            companion_id=uuid.UUID(scope["companion_id"]), page=1, page_size=10,
        ).get("items", [])
    except Exception:
        records = []
        load_failed = True
    items = []
    for record in records:
        if str(getattr(record, "user_id", "")) != scope["user_id"]:
            continue
        if str(getattr(record, "companion_id", "")) != scope["companion_id"]:
            continue
        if getattr(record, "status", None) != "committed" or getattr(record, "reverted_at", None):
            continue
        items.append({
            "id": str(record.id),
            "type": record.type,
            "content": record.content,
            "reason": record.reason,
            "impact_scope": list(record.impact_scope or []),
            "applied_to_profile": bool(record.applied_to_profile),
            "updated_at": _as_text(record.updated_at or record.created_at),
        })
        if len(items) >= 5:
            break
    availability = "unavailable" if load_failed else ("available" if items else "empty")
    version = max((item["updated_at"] for item in items if item["updated_at"]), default=None)
    return _section(
        "growth_records", "reviewed_growth", scope, availability,
        {"items": items}, None, version,
    )


def _memory_section(
    state: ConversationAgentState, scope: dict[str, Any]
) -> dict[str, Any]:
    items = []
    for memory in state.get("selected_memories", [])[:5]:
        items.append({
            "id": str(memory.get("id")),
            "type": memory.get("type", "memory"),
            "content": str(memory.get("content") or memory.get("summary") or "")[:300],
            "retrieval_score": memory.get("retrieval_score"),
            "memory_layer": memory.get("memory_layer"),
        })
    retrieval_trace = next(
        (
            step for step in reversed(state.get("trace_steps", []))
            if step.get("step") == "memory_retrieval"
        ),
        {},
    )
    return _section(
        "memory_retrieval", "retrieved_turn_context", scope,
        "available" if items else "empty", {"items": items},
        state.get("trace_run_id"),
        str((retrieval_trace.get("algorithm") or {}).get("version") or "runtime"),
    )


def _presence_section(
    state: ConversationAgentState,
    persona: dict[str, Any],
    boundary: dict[str, Any],
    scope: dict[str, Any],
) -> dict[str, Any]:
    settings = state.get("boundary_settings") or {}
    try:
        suppression = presence_service.evaluate_presence_suppression(
            uuid.UUID(scope["user_id"]),
            uuid.UUID(scope["companion_id"]),
            "companion_context_snapshot",
            min_interval_seconds=0,
        )
    except Exception:
        suppression = None
    data = {
        "presence_style": persona.get("data", {}).get("presence_style"),
        "presence_interrupt_policy": boundary.get("data", {}).get("presence_interrupt_policy"),
        "proactive_level": settings.get("proactive_level"),
        "allow_presence": settings.get("allow_presence", True),
        "allow_proactive_presence": settings.get("allow_proactive_presence", True),
        "notification_surface": settings.get("notification_surface"),
        "suppressed_presence_types": list(settings.get("suppressed_presence_types") or []),
        "quiet_hours": dict(settings.get("quiet_hours") or {}),
        "max_presence_per_day": settings.get("max_presence_per_day"),
        "min_presence_interval_minutes": settings.get("min_presence_interval_minutes"),
        "meaningful_silence_enabled": settings.get("meaningful_silence_enabled", True),
        "proactive_presence_suppressed": suppression.get("suppress") if suppression else None,
        "proactive_suppression_reason": suppression.get("reason") if suppression else None,
    }
    data = {key: value for key, value in data.items() if value is not None}
    version = boundary.get("source", {}).get("version") or persona.get("source", {}).get("version")
    return _section(
        "presence_configuration", "non_bypassable_safety", scope,
        "available" if suppression is not None else "partial", data,
        str(suppression.get("event_id")) if suppression and suppression.get("event_id") else None,
        version,
    )


def _section(
    source_type: str,
    priority_layer: str,
    scope: dict[str, Any],
    availability: str,
    data: dict[str, Any],
    source_id: str | None,
    version: str | None,
) -> dict[str, Any]:
    return {
        "availability": availability,
        "priority_layer": priority_layer,
        "source": {"type": source_type, "id": source_id, "version": version},
        "scope": scope,
        "data": data,
    }


def _matches_scope(
    payload: dict[str, Any],
    scope: dict[str, Any],
    *,
    include_conversation: bool = False,
) -> bool:
    if str(payload.get("user_id")) != scope["user_id"]:
        return False
    if str(payload.get("companion_id")) != scope["companion_id"]:
        return False
    if include_conversation and str(payload.get("conversation_id")) != scope["conversation_id"]:
        return False
    return True


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)
