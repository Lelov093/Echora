"""Persist a bounded Companion affect transition from grounded appraisal evidence."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import affect_extraction_service, affect_service


def affect_appraisal_node(state: ConversationAgentState) -> ConversationAgentState:
    extraction = affect_extraction_service.extract_appraisal(state.get("user_input", ""), state.get("assistant_response", ""))
    validation = affect_extraction_service.validate_extraction(state.get("user_input", ""), extraction)
    events = []
    if validation["status"] == "passed" and state.get("user_message_id"):
        result = affect_service.apply_validated_appraisal({
            "user_id": uuid.UUID(state["user_id"]), "companion_id": uuid.UUID(state["companion_id"]),
            "conversation_id": state.get("conversation_id"), "trace_run_id": state.get("trace_run_id"),
            "source_message_ids": [state["user_message_id"]], "summary": extraction["summary"],
            "evidence_quote": extraction["evidence_quote"], "extraction": extraction, "validation": validation,
            "provider_name": extraction.get("provider"), "model_name": extraction.get("model"),
            "idempotency_key": f"affect:{state.get('turn_idempotency_key') or state.get('trace_run_id') or state['user_message_id']}",
        })
        events.append(result["event"])
        state["affect_state"] = result["state"]
    state["affect_events"] = events
    state.setdefault("trace_steps", []).append({
        "step": "affect_appraisal", "order": 9,
        "status": "warning" if extraction.get("status") in {"provider_failed", "invalid_response"} else "completed",
        "extraction_status": extraction.get("status"), "validation_status": validation["status"],
        "validation_reasons": validation["reasons"], "event_ids": [item["id"] for item in events],
        "algorithm_version": "affect-mean-reversion.v1",
    })
    return state
