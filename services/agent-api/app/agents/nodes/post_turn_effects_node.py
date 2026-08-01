"""Coordinate existing domain writers under one durable Post-turn Effects contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable

from app.agents.nodes.continuity_update_node import continuity_update_node
from app.agents.nodes.context_document_refresh_node import context_document_refresh_node
from app.agents.nodes.delegated_execution_planning_node import delegated_execution_planning_node
from app.agents.nodes.growth_candidate_node import growth_candidate_node
from app.agents.nodes.memory_candidate_node import memory_candidate_node
from app.agents.nodes.mutual_presence_policy_node import mutual_presence_policy_node
from app.agents.nodes.presence_opportunity_node import presence_opportunity_node
from app.agents.nodes.relationship_explanation_node import relationship_explanation_node
from app.agents.nodes.relationship_candidate_node import relationship_candidate_node
from app.agents.nodes.review_resolution_node import review_resolution_node
from app.agents.nodes.shared_episodic_memory_candidate_node import shared_episodic_memory_candidate_node
from app.agents.nodes.user_state_snapshot_node import user_state_snapshot_node
from app.agents.nodes.affect_appraisal_node import affect_appraisal_node
from app.agents.state import ConversationAgentState
from app.services import post_turn_effects_service


@dataclass(frozen=True)
class EffectDefinition:
    name: str
    disposition: str
    handler: Callable[[ConversationAgentState], ConversationAgentState]
    refs: Callable[[ConversationAgentState], list[str]]


EFFECT_DEFINITIONS = (
    EffectDefinition("memory_candidate", "contextual_user_confirmation", memory_candidate_node, lambda s: _ids(s, "memory_candidates")),
    EffectDefinition("growth_candidate", "review_gated", growth_candidate_node, lambda s: _ids(s, "growth_candidates")),
    EffectDefinition("relationship_candidate", "review_gated", relationship_candidate_node, lambda s: _ids(s, "relationship_candidates")),
    EffectDefinition("affect", "immediate_bounded_private_write", affect_appraisal_node, lambda s: _ids(s, "affect_events")),
    EffectDefinition("presence_opportunity", "immediate_policy_gated", presence_opportunity_node, lambda s: _ids(s, "presence_opportunities")),
    EffectDefinition("shared_memory_candidate", "review_gated", shared_episodic_memory_candidate_node, lambda s: _ids(s, "shared_memory_candidates")),
    EffectDefinition("mutual_presence_policy", "trace_and_policy_only", mutual_presence_policy_node, lambda s: list(s.get("presence_policy_run_ids", []))),
    EffectDefinition("delegated_execution", "contextual_user_confirmation", delegated_execution_planning_node, lambda s: _single_id((s.get("delegation_intent") or {}).get("id"))),
    EffectDefinition("continuity", "immediate_domain_write", continuity_update_node, lambda s: _single_id(s.get("continuity_snapshot_id"))),
    EffectDefinition("context_documents", "evidence_grounded_versioned_write", context_document_refresh_node, lambda s: list(s.get("context_document_ids", []))),
    EffectDefinition("user_state", "immediate_low_risk_write", user_state_snapshot_node, lambda s: _single_id(s.get("user_state_snapshot_id"))),
    EffectDefinition("relationship_explanation", "trace_only_no_relationship_mutation", relationship_explanation_node, lambda s: list(s.get("relationship_explanation_ids", []))),
    EffectDefinition("review_batch", "background_review_gated", review_resolution_node, lambda s: _single_id(s.get("review_batch_id"))),
)


def post_turn_effects_node(
    state: ConversationAgentState,
) -> ConversationAgentState:
    return run_post_turn_effects(state)


def run_post_turn_effects(
    state: ConversationAgentState,
    *,
    only_effects: set[str] | None = None,
) -> ConversationAgentState:
    """Run independent domain-local effects and persist a recovery receipt after each."""
    existing = state.get("post_turn_effects") or {}
    previous_receipts = {
        item.get("effect"): item
        for item in existing.get("receipts", [])
        if item.get("effect")
    }
    contract = {
        "contract_version": post_turn_effects_service.CONTRACT_VERSION,
        "trace_run_id": state.get("trace_run_id"),
        "idempotency_key": state.get("turn_idempotency_key"),
        "transaction_mode": "domain_local_with_durable_trace_journal",
        "version_guard": {
            "policy": "snapshot_versions_recorded_no_direct_profile_overwrite",
            "sources": _snapshot_versions(state),
        },
        "receipts": [],
        "status": "running",
    }
    errors: list[dict[str, Any]] = [
        item for item in state.get("post_turn_effect_errors", [])
        if only_effects is None or item.get("effect") not in only_effects
    ]
    _persist(state, contract)

    for definition in EFFECT_DEFINITIONS:
        previous = previous_receipts.get(definition.name)
        if only_effects is not None and definition.name not in only_effects:
            if previous:
                contract["receipts"].append(previous)
            continue
        if previous and previous.get("status") in {"completed", "skipped"}:
            contract["receipts"].append(previous)
            continue
        effect_started_at = datetime.now(timezone.utc)
        effect_started = perf_counter()
        if _retention_suppresses(state, definition.name):
            effect_completed_at = datetime.now(timezone.utc)
            contract["receipts"].append({
                "effect": definition.name,
                "disposition": definition.disposition,
                "status": "skipped",
                "refs": [],
                "error": None,
                "reason": "conversation_retention_policy",
                "started_at": effect_started_at.isoformat(),
                "completed_at": effect_completed_at.isoformat(),
                "elapsed_ms": round((perf_counter() - effect_started) * 1000),
            })
            contract["status"] = _contract_status(contract["receipts"])
            state["post_turn_effects"] = contract
            _persist(state, contract)
            continue

        trace_count = len(state.get("trace_steps", []))
        receipt = {
            "effect": definition.name,
            "disposition": definition.disposition,
            "status": "running",
            "refs": [],
            "error": None,
            "started_at": effect_started_at.isoformat(),
        }
        try:
            state = definition.handler(state)
            receipt["refs"] = definition.refs(state)
            step = _latest_effect_step(state, trace_count)
            step_status = step.get("status") if step else "completed"
            if step_status in {"failed", "warning"}:
                receipt["status"] = "partial_failed" if receipt["refs"] else "failed"
                receipt["error"] = {
                    "code": "DOMAIN_EFFECT_WARNING",
                    "step": step.get("step") if step else definition.name,
                }
            else:
                receipt["status"] = "skipped" if step_status == "skipped" else "completed"
        except Exception as exc:
            receipt["refs"] = definition.refs(state)
            receipt["status"] = "partial_failed" if receipt["refs"] else "failed"
            receipt["error"] = {
                "code": "DOMAIN_EFFECT_FAILED",
                "error_type": type(exc).__name__,
            }
        if receipt["error"]:
            errors.append({"effect": definition.name, **receipt["error"]})
        receipt["completed_at"] = datetime.now(timezone.utc).isoformat()
        receipt["elapsed_ms"] = round((perf_counter() - effect_started) * 1000)
        contract["receipts"].append(receipt)
        contract["status"] = _contract_status(contract["receipts"])
        state["post_turn_effects"] = contract
        state["post_turn_effect_errors"] = errors
        _persist(state, contract)

    contract["status"] = _contract_status(contract["receipts"])
    state["post_turn_effects"] = contract
    state["post_turn_effect_errors"] = errors
    _persist(state, contract)
    state.setdefault("trace_steps", []).append({
        "step": "post_turn_effects",
        "order": 120,
        "status": "completed" if contract["status"] == "completed" else "warning",
        "contract_version": contract["contract_version"],
        "transaction_mode": contract["transaction_mode"],
        "effect_status": contract["status"],
        "receipts": contract["receipts"],
        "errors": errors,
    })
    return state


def recoverable_effect_names(contract: dict[str, Any]) -> set[str]:
    """Only retry failed effects with no persisted refs; never risk duplicating partial writes."""
    return {
        item["effect"]
        for item in contract.get("receipts", [])
        if item.get("status") == "failed" and not item.get("refs")
    }


def _persist(state: ConversationAgentState, contract: dict[str, Any]) -> None:
    trace_run_id = state.get("trace_run_id")
    if trace_run_id:
        post_turn_effects_service.persist_checkpoint(trace_run_id, state, contract)


def _ids(state: ConversationAgentState, key: str) -> list[str]:
    return [str(item["id"]) for item in state.get(key, []) if item.get("id")]


def _single_id(value: Any) -> list[str]:
    return [str(value)] if value else []


def _latest_effect_step(state: ConversationAgentState, previous_count: int) -> dict[str, Any]:
    new_steps = state.get("trace_steps", [])[previous_count:]
    return new_steps[-1] if new_steps else {}


def _contract_status(receipts: list[dict[str, Any]]) -> str:
    failed = [item for item in receipts if item.get("status") in {"failed", "partial_failed"}]
    return "partial_failed" if failed else "completed"


def _snapshot_versions(state: ConversationAgentState) -> dict[str, Any]:
    snapshot = state.get("companion_context_snapshot") or {}
    return {
        key: (snapshot.get(key) or {}).get("source", {}).get("version")
        for key in ("identity", "persona", "relationship_contract", "boundary", "relationship", "continuity")
    }


def _retention_suppresses(state: ConversationAgentState, effect_name: str) -> bool:
    conversation = state.get("conversation") or {}
    restricted = (
        conversation.get("retention_mode") == "temporary"
        or not conversation.get("cross_session_memory_enabled", True)
    )
    return restricted and effect_name in {
        "memory_candidate", "growth_candidate", "relationship_candidate", "presence_opportunity",
        "affect",
        "shared_memory_candidate", "mutual_presence_policy", "continuity",
        "context_documents", "user_state", "relationship_explanation", "review_batch",
    }
