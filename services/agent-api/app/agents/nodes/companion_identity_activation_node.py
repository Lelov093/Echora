"""Companion Reoriented node: activate companion identity/persona/contract context."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import companion_contract_service, companion_identity_service


def companion_identity_activation_node(state: ConversationAgentState) -> ConversationAgentState:
    companion_id = uuid.UUID(state["companion_id"])

    identity = companion_identity_service.get_identity(companion_id) or {}
    persona = companion_identity_service.get_persona(companion_id) or {}
    contract = companion_contract_service.get_contract(companion_id) or {}
    boundary = companion_contract_service.get_boundary(companion_id) or {}

    state["active_companion"] = {
        "companion_id": state["companion_id"],
        "identity": identity,
        "persona": persona,
        "relationship_contract": contract,
        "boundary_profile": boundary,
    }

    companion_profile = dict(state.get("companion_profile") or {})
    base_personality_parts = [
        companion_profile.get("base_personality"),
        identity.get("identity_summary"),
        ", ".join(identity.get("core_traits_json") or []),
        persona.get("persona_summary"),
        persona.get("communication_style_summary"),
        ", ".join(persona.get("core_values_json") or []),
        f"presence_style={persona.get('presence_style')}" if persona.get("presence_style") else None,
        f"relationship_role={contract.get('relationship_role')}" if contract.get("relationship_role") else None,
        contract.get("collaboration_style_summary"),
    ]
    companion_profile.update({
        "name": identity.get("display_name") or companion_profile.get("name") or "Echora",
        "identity_summary": identity.get("identity_summary"),
        "origin_story": identity.get("origin_story"),
        "identity_labels": identity.get("identity_labels_json") or [],
        "voice_style_hint": identity.get("voice_style_hint"),
        "persona_summary": persona.get("persona_summary"),
        "response_preferences": persona.get("response_preferences_json") or {},
        "presence_style": persona.get("presence_style"),
        "relationship_role": contract.get("relationship_role"),
        "contract_summary": contract.get("contract_summary"),
        "support_scope": contract.get("support_scope_json") or [],
        "base_personality": " | ".join([part for part in base_personality_parts if part]),
    })
    state["companion_profile"] = companion_profile

    boundary_settings = dict(state.get("boundary_settings") or {})
    boundary_settings.update({
        "notification_surface": boundary_settings.get("notification_surface") or "hub_queue_only",
        "allow_presence": boundary.get("presence_interrupt_policy") != "silent_only",
        "allow_proactive_presence": boundary.get("presence_interrupt_policy") != "silent_only",
        "global_memory_read_scope": boundary.get("global_memory_read_scope"),
        "cross_companion_read_policy": boundary.get("cross_companion_read_policy"),
        "review_required_private_to_shared": boundary.get("review_required_private_to_shared", True),
        "review_required_shared_to_private": boundary.get("review_required_shared_to_private", True),
        "review_required_cross_companion_share": boundary.get("review_required_cross_companion_share", True),
    })
    state["boundary_settings"] = boundary_settings

    state.setdefault("trace_steps", []).append({
        "step": "companion_identity_activation",
        "order": 101,
        "status": "completed",
        "companion_name": companion_profile.get("name"),
        "presence_style": persona.get("presence_style"),
        "relationship_role": contract.get("relationship_role"),
        "global_memory_read_scope": boundary.get("global_memory_read_scope"),
    })
    return state
