"""Create review-gated Relationship candidates from cited, validated evidence."""

from __future__ import annotations

import uuid

from app.agents.state import ConversationAgentState
from app.services import relationship_candidate_extraction_service, relationship_service


def relationship_candidate_node(state: ConversationAgentState) -> ConversationAgentState:
    extraction = relationship_candidate_extraction_service.extract_relationship_candidate(
        state.get("user_input", ""),
        state.get("assistant_response", ""),
        state.get("selected_memories", []),
    )
    validation = relationship_candidate_extraction_service.validate_extraction(
        state.get("user_input", ""),
        state.get("assistant_response", ""),
        state.get("selected_memories", []),
        extraction,
    )
    candidates: list[dict] = []
    if validation["status"] == "passed":
        source_message_ids = [state["user_message_id"]] if state.get("user_message_id") else []
        if state.get("assistant_message_id") and any(item.get("assistant") for item in validation["evidence_quotes"]):
            source_message_ids.append(state["assistant_message_id"])
        result = relationship_service.create_relationship_candidate({
            "user_id": uuid.UUID(state["user_id"]),
            "companion_id": uuid.UUID(state["companion_id"]),
            "conversation_id": state.get("conversation_id"),
            "trace_run_id": state.get("trace_run_id"),
            "summary": extraction["summary"],
            "dimension_signals": validation["signals"],
            "source_message_ids": source_message_ids,
            "source_memory_ids": validation["source_memory_ids"],
            "evidence_quotes": validation["evidence_quotes"],
            "extraction": extraction,
            "validation": validation,
            "evidence_score": validation["evidence_score"],
            "confidence": validation["confidence"],
            "risk_level": validation["risk_level"],
            "provider_name": extraction.get("provider"),
            "model_name": extraction.get("model"),
            "idempotency_key": f"relationship:{state.get('turn_idempotency_key') or state.get('trace_run_id') or state.get('user_message_id')}",
        })
        candidates.append(result)
    state["relationship_candidates"] = candidates
    state.setdefault("trace_steps", []).append({
        "step": "relationship_candidate",
        "order": 8,
        "status": "warning" if extraction.get("status") in {"provider_failed", "invalid_response"} else "completed",
        "extraction_status": extraction.get("status"),
        "validation_status": validation["status"],
        "validation_reasons": validation["reasons"],
        "candidate_ids": [item["id"] for item in candidates],
        "algorithm_version": validation["algorithm_version"],
    })
    return state
