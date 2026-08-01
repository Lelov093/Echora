"""Application orchestration for one validated Companion conversation turn."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.agents.runner import execute_agent_turn
from app.agents.state import ConversationAgentState
from app.agents.providers.reasoning_policy import REASONING_MODES
from app.db.models import Companion, Conversation, Message
from app.services import (
    conversation_turn_event_service,
    conversation_turn_journal_service,
    post_turn_effects_service,
    response_ready_hook_service,
)
from app.services.conversation_service import (
    ConversationTurnError,
    get_conversation,
    get_session,
    is_companion_room_conversation,
    is_temporary_conversation_expired,
)
from app.services.conversation_turn_journal_service import ConversationTurnClaim
from app.services.memory_service import get_memory_candidate
from app.services.presence_service import get_opportunity


TURN_CONTRACT_VERSION = "conversation-turn.v1"
ALLOWED_MODE_KEYS = {
    "project", "creative", "daily", "learning", "game", "character", "virtual_world",
}


@dataclass(frozen=True)
class ConversationTurnCommand:
    conversation_id: uuid.UUID
    content: str
    requested_companion_id: uuid.UUID | None = None
    requested_user_id: uuid.UUID | None = None
    mode_key: str | None = None
    reasoning_mode: str | None = None
    idempotency_key: str | None = None
    continuation_of_trace_run_id: uuid.UUID | None = None
    transport_mode: str = "sync"
    response_ready_hook: response_ready_hook_service.ResponseReadyHook | None = None


@dataclass(frozen=True)
class ConversationTurnContext:
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    mode_key: str
    reasoning_mode: str = "auto"


def execute_conversation_turn(command: ConversationTurnCommand) -> dict[str, Any]:
    """Validate scope, execute the Graph, then project the exact current turn."""
    content = _validate_content(command.content)
    context = _resolve_turn_context(command)
    claim = _claim_turn(context, content, command.idempotency_key)
    if claim.replay_response is not None:
        replay = claim.replay_response
        replay.setdefault("turn", {})["idempotent_replay"] = True
        return replay
    return _execute_claimed_turn(
        context,
        content,
        claim,
        response_ready_hook=command.response_ready_hook,
    )


def accept_conversation_turn(command: ConversationTurnCommand) -> dict[str, Any]:
    """Persist a Web turn and return its durable runtime status without running the Graph."""
    content = _validate_content(command.content)
    context = _resolve_turn_context(command)
    claim = _claim_turn(
        context,
        content,
        command.idempotency_key,
        transport_mode="async_web",
        allow_incomplete_replay=True,
        continuation_of_trace_run_id=command.continuation_of_trace_run_id,
    )
    status = conversation_turn_journal_service.get_turn_status(
        conversation_id=context.conversation_id,
        companion_id=context.companion_id,
        trace_run_id=claim.trace_run_id,
    )
    if status is None:
        raise ConversationTurnError(
            "CONVERSATION_TURN_RECOVERY_REQUIRED",
            "The accepted Conversation turn could not be projected.",
            {"trace_run_id": str(claim.trace_run_id)},
        )
    status["idempotent_replay"] = claim.existing_claim
    return status


def get_conversation_turn_status(
    conversation_id: uuid.UUID,
    trace_run_id: uuid.UUID,
    requested_companion_id: uuid.UUID,
) -> dict[str, Any]:
    """Return one async Web turn inside its validated Companion scope."""
    conversation = get_conversation(conversation_id, requested_companion_id)
    if conversation is None:
        raise ConversationTurnError(
            "CONVERSATION_NOT_FOUND",
            "Conversation not found in the requested Companion scope.",
        )
    status = conversation_turn_journal_service.get_turn_status(
        conversation_id=conversation.id,
        companion_id=conversation.companion_id,
        trace_run_id=trace_run_id,
    )
    if status is None:
        raise ConversationTurnError(
            "CONVERSATION_TURN_NOT_FOUND",
            "The async Conversation turn was not found in this Companion scope.",
        )
    return status


def get_latest_conversation_turn_status(
    conversation_id: uuid.UUID,
    requested_companion_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Recover the most recent async Web turn after navigation or refresh."""
    conversation = get_conversation(conversation_id, requested_companion_id)
    if conversation is None:
        raise ConversationTurnError(
            "CONVERSATION_NOT_FOUND",
            "Conversation not found in the requested Companion scope.",
        )
    return conversation_turn_journal_service.get_latest_turn_status(
        conversation_id=conversation.id,
        companion_id=conversation.companion_id,
    )


def cancel_conversation_turn(
    conversation_id: uuid.UUID,
    trace_run_id: uuid.UUID,
    requested_companion_id: uuid.UUID,
) -> dict[str, Any]:
    """Request cancellation while preserving any already-persisted successful response."""
    conversation = get_conversation(conversation_id, requested_companion_id)
    if conversation is None:
        raise ConversationTurnError(
            "CONVERSATION_NOT_FOUND",
            "Conversation not found in the requested Companion scope.",
        )
    status = conversation_turn_journal_service.request_turn_cancellation(
        conversation_id=conversation.id,
        companion_id=conversation.companion_id,
        trace_run_id=trace_run_id,
    )
    if status is None:
        raise ConversationTurnError(
            "CONVERSATION_TURN_NOT_FOUND",
            "The async Conversation turn was not found in this Companion scope.",
        )
    if status.get("cancellation_accepted"):
        event_status = str(status.get("status") or "cancellation_requested")
        conversation_turn_event_service.publish(
            trace_run_id,
            "cancelled" if event_status == "cancelled" else "lifecycle",
            {"status": event_status},
        )
    return status


def retry_failed_provider_turn(
    conversation_id: uuid.UUID,
    trace_run_id: uuid.UUID,
    requested_companion_id: uuid.UUID,
) -> dict[str, Any]:
    """Retry Provider generation against the original durable user-message claim."""
    context = _resolve_turn_context(
        ConversationTurnCommand(
            conversation_id=conversation_id,
            requested_companion_id=requested_companion_id,
            content="provider retry",
        )
    )
    claim, content = conversation_turn_journal_service.prepare_provider_retry(
        conversation_id=context.conversation_id,
        companion_id=context.companion_id,
        trace_run_id=trace_run_id,
    )
    return _execute_claimed_turn(context, content, claim, provider_retry=True)


def _execute_claimed_turn(
    context: ConversationTurnContext,
    content: str,
    claim: ConversationTurnClaim,
    *,
    provider_retry: bool = False,
    response_ready_hook: response_ready_hook_service.ResponseReadyHook | None = None,
) -> dict[str, Any]:
    try:
        with response_ready_hook_service.bind_response_ready_hook(response_ready_hook):
            agent_kwargs = {
                "user_id": str(context.user_id),
                "companion_id": str(context.companion_id),
                "conversation_id": str(context.conversation_id),
                "content": content,
                "mode_key": context.mode_key,
                "user_message_id": str(claim.user_message_id),
                "trace_run_id": str(claim.trace_run_id),
                "turn_idempotency_key": claim.idempotency_key,
                "reasoning_mode": claim.reasoning_mode,
            }
            if claim.transport_mode == "async_web":
                agent_kwargs["stream_response"] = True
                agent_kwargs["defer_post_turn_effects"] = True
            state = execute_agent_turn(
                **agent_kwargs,
            )
        result = project_conversation_turn(state, content)
        result["turn"]["idempotency_key"] = claim.idempotency_key
        result["turn"]["idempotent_replay"] = False
        result["turn"]["provider_retry"] = provider_retry
        _store_turn_response(claim.trace_run_id, result)
        if claim.transport_mode == "async_web":
            deferred_effects = (
                bool(state.get("assistant_message_id"))
                and not state.get("turn_cancelled")
                and not result.get("_run_errors")
            )
            if deferred_effects:
                from app.agents.nodes.post_turn_effects_node import EFFECT_DEFINITIONS

                post_turn_effects_service.enqueue_job(
                    claim.trace_run_id,
                    state,
                    planned_effects=[definition.name for definition in EFFECT_DEFINITIONS],
                )
                return result
            conversation_turn_journal_service.finalize_turn_runtime(
                claim.trace_run_id,
                result=result,
                stage_timings=state.get("turn_stage_timings", []),
                provider_timing=state.get("provider_timing", {}),
            )
            terminal_status = (
                "cancelled" if state.get("turn_cancelled")
                else "failed" if result.get("_run_errors")
                else "completed"
            )
            conversation_turn_event_service.publish(
                claim.trace_run_id,
                terminal_status,
                {"status": terminal_status},
            )
        return result
    except Exception as exc:
        try:
            _mark_claim_failed(claim.trace_run_id, exc)
        except Exception:
            # Preserve the original runtime failure if failure journaling is unavailable.
            pass
        raise


def recover_conversation_turn_effects(
    conversation_id: uuid.UUID,
    trace_run_id: uuid.UUID,
    requested_companion_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Retry only failed no-ref effects from the durable checkpoint."""
    _resolve_turn_context(
        ConversationTurnCommand(
            conversation_id=conversation_id,
            requested_companion_id=requested_companion_id,
            content="post-turn recovery",
        )
    )
    journal = post_turn_effects_service.load_journal(trace_run_id)
    if journal is None:
        raise ConversationTurnError(
            "POST_TURN_JOURNAL_NOT_FOUND", "Post-turn Effects journal not found.",
        )
    state = journal.get("recovery_state") or {}
    if state.get("conversation_id") != str(conversation_id):
        raise ConversationTurnError(
            "CONVERSATION_SCOPE_MISMATCH",
            "Post-turn journal does not belong to this Conversation.",
        )
    if requested_companion_id and state.get("companion_id") != str(requested_companion_id):
        raise ConversationTurnError(
            "CONVERSATION_SCOPE_MISMATCH",
            "Post-turn journal does not belong to the requested Companion.",
        )
    from app.agents.nodes.post_turn_effects_node import (
        recoverable_effect_names,
        run_post_turn_effects,
    )

    recoverable = recoverable_effect_names(journal.get("contract") or {})
    if not recoverable:
        contract = journal.get("contract") or {}
        partial_refs = [
            item.get("effect")
            for item in contract.get("receipts", [])
            if item.get("status") == "partial_failed" and item.get("refs")
        ]
        return {
            "trace_run_id": str(trace_run_id),
            "recovery_status": (
                "manual_reconciliation_required" if partial_refs else "nothing_to_recover"
            ),
            "manual_reconciliation_effects": partial_refs,
            "post_turn_effects": contract,
        }
    recovered = run_post_turn_effects(state, only_effects=recoverable)
    return {
        "trace_run_id": str(trace_run_id),
        "recovery_status": (
            "completed"
            if (recovered.get("post_turn_effects") or {}).get("status") == "completed"
            else "partial_failed"
        ),
        "retried_effects": sorted(recoverable),
        "post_turn_effects": recovered.get("post_turn_effects") or {},
    }


def project_conversation_turn(
    state: ConversationAgentState,
    content: str,
) -> dict[str, Any]:
    """Build the stable API projection from one completed runtime state."""
    user_message = _load_message(state.get("user_message_id"))
    assistant_message = _load_message(state.get("assistant_message_id"))
    memory_candidates = _resolve_memory_candidates(state)
    presence_opportunities = _resolve_presence_opportunities(state)
    execution_signal_summary = state.get("execution_signal_summary") or _execution_signal_summary(state)
    companion_context_summary = (
        state.get("companion_context_summary")
        or _companion_context_summary(state)
    )
    turn_contract = _build_turn_contract(state)

    return {
        "turn": turn_contract,
        "post_turn_effects": state.get("post_turn_effects", {}),
        "conversation": {
            "id": state.get("conversation_id"),
            "current_topic": state.get("conversation", {}).get("current_topic"),
            "current_goal": state.get("conversation", {}).get("current_goal"),
            "co_presence_session_id": state.get("conversation", {}).get("co_presence_session_id"),
            "shared_scene_id": state.get("conversation", {}).get("shared_scene_id"),
        },
        "user_message": _message_projection(
            user_message,
            fallback_id=state.get("user_message_id"),
            fallback_role="user",
            fallback_content=content,
        ) if user_message or state.get("user_message_id") else None,
        "assistant_message": _message_projection(
            assistant_message,
            fallback_id=state.get("assistant_message_id"),
            fallback_role="assistant",
            fallback_content=state.get("assistant_response", ""),
        ) if assistant_message or state.get("assistant_response") else None,
        "related_memories": state.get("selected_memories", []),
        "memory_candidates": memory_candidates,
        "growth_candidates": state.get("growth_candidates", []),
        "presence_opportunities": presence_opportunities,
        "tool_runs": state.get("tool_runs", []),
        "task_run": state.get("task_run", {}),
        "file_evidence": state.get("file_evidence", []),
        "evidence_sufficiency": state.get("evidence_sufficiency_events", []),
        "project_task_updates": state.get("project_task_updates", []),
        "outdated_memory_flags": state.get("outdated_memory_flags", []),
        "growth_consistency_checks": state.get("growth_consistency_checks", []),
        "bad_case_signals": state.get("bad_case_signals", []),
        "evaluation_signals": state.get("evaluation_signals", []),
        "execution_signal_summary": execution_signal_summary,
        "companion_context_summary": companion_context_summary,
        "active_companion": state.get("active_companion", {}),
        "co_present_companions": state.get("co_present_companions", []),
        "co_presence_session": state.get("co_presence_session", {}),
        "participant_awareness": state.get("participant_awareness", {}),
        "shared_scene": state.get("shared_scene", {}),
        "companion_memory_scope": state.get("companion_memory_scope", {}),
        "shared_memory_candidates": state.get("shared_memory_candidates", []),
        "cross_companion_memory_reviews": state.get("cross_companion_memory_reviews", []),
        "persona_guard_result": state.get("persona_guard_result", {}),
        "delegation_intent": state.get("delegation_intent", {}),
        "trace": {
            "trace_run_id": state.get("trace_run_id"),
            "status": (
                "cancelled" if state.get("turn_cancelled")
                else "completed" if not state.get("errors")
                else "completed_with_errors"
            ),
            "step_count": len(state.get("trace_steps", [])),
            "signals": execution_signal_summary,
            "companion_context": companion_context_summary,
            "steps": [
                {"step": step.get("step"), "order": step.get("order"), "status": step.get("status")}
                for step in state.get("trace_steps", [])
            ],
        },
        "suggested_next_step": _next_step_text(state),
        "agent_graph_status": (
            "cancelled" if state.get("turn_cancelled")
            else "failed" if state.get("errors")
            else "completed"
        ),
        "provider_mode": state.get("provider_mode", "uninitialized"),
        "provider_name": state.get("provider_name"),
        "model_name": state.get("model_name"),
        "warnings": state.get("warnings", []),
        "memory_impact_summary": state.get("memory_impact_summary", {}),
        "continuity_snapshot_id": state.get("continuity_snapshot_id"),
        "continuity_summary": state.get("continuity_summary", {}),
        "user_state_snapshot_id": state.get("user_state_snapshot_id"),
        "relationship_explanation_ids": state.get("relationship_explanation_ids", []),
        "review_batch_id": state.get("review_batch_id"),
        "review_summary": state.get("review_summary", {}),
        "memory_usage_event_ids": state.get("memory_usage_event_ids", []),
        "lifecycle_event_ids": state.get("memory_lifecycle_event_ids", []),
        "embedding_provider": state.get("embedding_provider", "uninitialized"),
        "_run_errors": state.get("errors", []),
    }


def _resolve_turn_context(command: ConversationTurnCommand) -> ConversationTurnContext:
    with get_session() as session:
        conversation = session.get(Conversation, command.conversation_id)
        if conversation is None or conversation.deleted_at is not None:
            raise ConversationTurnError(
                "CONVERSATION_NOT_FOUND", "Conversation not found",
            )
        if is_temporary_conversation_expired(conversation):
            raise ConversationTurnError(
                "TEMPORARY_CONVERSATION_EXPIRED",
                "Temporary Conversation retention window has expired.",
                {"retention_expires_at": conversation.retention_expires_at.isoformat()},
            )
        if is_companion_room_conversation(conversation):
            raise ConversationTurnError(
                "ROOM_CONVERSATION_REQUIRES_COORDINATOR",
                "Room turns must be executed through the Room coordinator.",
            )
        if command.requested_user_id and command.requested_user_id != conversation.user_id:
            raise ConversationTurnError(
                "CONVERSATION_SCOPE_MISMATCH",
                "Conversation does not belong to the requested owner.",
            )
        if (
            command.requested_companion_id
            and command.requested_companion_id != conversation.companion_id
        ):
            raise ConversationTurnError(
                "CONVERSATION_SCOPE_MISMATCH",
                "Conversation does not belong to the requested Companion.",
            )
        if conversation.status != "active":
            raise ConversationTurnError(
                "CONVERSATION_NOT_ACTIVE",
                "Conversation must be active before a new turn can run.",
                {"status": conversation.status},
            )

        companion = session.get(Companion, conversation.companion_id)
        if companion is None or companion.deleted_at is not None:
            raise ConversationTurnError(
                "COMPANION_NOT_FOUND", "The Conversation Companion is unavailable.",
            )
        if companion.user_id != conversation.user_id:
            raise ConversationTurnError(
                "CONVERSATION_SCOPE_MISMATCH",
                "Conversation owner and Companion owner do not match.",
            )
        if companion.current_status == "archived":
            raise ConversationTurnError(
                "COMPANION_ARCHIVED",
                "Restore the Companion before continuing this conversation.",
            )

        mode_key = command.mode_key or companion.current_mode or conversation.mode_key
        if mode_key not in ALLOWED_MODE_KEYS:
            raise ConversationTurnError(
                "INVALID_CONVERSATION_MODE",
                "The requested Companion mode is not supported.",
                {"mode_key": mode_key},
            )
        stored_reasoning_mode = str(
            (getattr(conversation, "metadata_", None) or {}).get("reasoning_mode") or "auto"
        )
        reasoning_mode = command.reasoning_mode or stored_reasoning_mode
        if reasoning_mode not in REASONING_MODES:
            raise ConversationTurnError(
                "INVALID_REASONING_MODE",
                "The requested Conversation reasoning mode is not supported.",
                {"reasoning_mode": reasoning_mode},
            )
        return ConversationTurnContext(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            companion_id=conversation.companion_id,
            mode_key=mode_key,
            reasoning_mode=reasoning_mode,
        )


def _validate_content(content: Any) -> str:
    if not isinstance(content, str) or not content.strip():
        raise ConversationTurnError(
            "CONVERSATION_CONTENT_REQUIRED",
            "A non-empty message is required to run a conversation turn.",
        )
    return content.strip()


def _claim_turn(
    context: ConversationTurnContext,
    content: str,
    requested_key: str | None,
    *,
    transport_mode: str = "sync",
    allow_incomplete_replay: bool = False,
    continuation_of_trace_run_id: uuid.UUID | None = None,
) -> ConversationTurnClaim:
    return conversation_turn_journal_service.claim_turn(
        conversation_id=context.conversation_id,
        user_id=context.user_id,
        companion_id=context.companion_id,
        mode_key=context.mode_key,
        content=content,
        requested_key=requested_key,
        turn_contract_version=TURN_CONTRACT_VERSION,
        transport_mode=transport_mode,
        allow_incomplete_replay=allow_incomplete_replay,
        continuation_of_trace_run_id=continuation_of_trace_run_id,
        reasoning_mode=context.reasoning_mode,
    )


def _store_turn_response(trace_run_id: uuid.UUID, result: dict[str, Any]) -> None:
    conversation_turn_journal_service.store_turn_response(trace_run_id, result)


def _mark_claim_failed(trace_run_id: uuid.UUID, exc: Exception) -> None:
    conversation_turn_journal_service.mark_claim_failed(trace_run_id, exc)


def _load_message(message_id: str | None) -> Message | None:
    if not message_id:
        return None
    with get_session() as session:
        return session.get(Message, uuid.UUID(message_id))


def _message_projection(
    message: Message | None,
    *,
    fallback_id: str | None,
    fallback_role: str,
    fallback_content: str,
) -> dict[str, Any]:
    return {
        "id": str(message.id) if message else fallback_id,
        "role": message.role if message else fallback_role,
        "content": message.content if message else fallback_content,
        "content_format": message.content_format if message else "text",
        "model_provider": message.model_provider if message else None,
        "model_name": message.model_name if message else None,
        "created_at": (
            message.created_at.isoformat() if message and message.created_at else None
        ),
    }


def _resolve_memory_candidates(state: ConversationAgentState) -> list[dict[str, Any]]:
    items = []
    for candidate in state.get("memory_candidates", []):
        if not candidate.get("id"):
            continue
        persisted = get_memory_candidate(uuid.UUID(candidate["id"]))
        if persisted:
            items.append({
                "id": str(persisted.id),
                "content": persisted.content,
                "suggested_type": persisted.suggested_type,
                "score": persisted.score,
                "status": persisted.status,
                "needs_user_confirmation": persisted.needs_user_confirmation,
            })
    return items


def _resolve_presence_opportunities(state: ConversationAgentState) -> list[dict[str, Any]]:
    items = []
    for opportunity in state.get("presence_opportunities", []):
        if not opportunity.get("id"):
            continue
        persisted = get_opportunity(uuid.UUID(opportunity["id"]))
        if persisted:
            items.append({
                "id": str(persisted.id),
                "type": persisted.type,
                "title": persisted.title,
                "priority": persisted.priority,
                "recommended_surface": persisted.recommended_surface,
                "status": persisted.status,
            })
    return items


def _build_turn_contract(state: ConversationAgentState) -> dict[str, Any]:
    errors = state.get("errors", [])
    response_status = (
        "interrupted" if state.get("turn_cancelled") and state.get("assistant_message_id") else
        "generated" if state.get("assistant_message_id") else
        "provider_failed" if any(error.get("step") == "response_generation" for error in errors) else
        "not_generated"
    )
    tool_runs = state.get("tool_runs", [])
    tool_status = tool_runs[-1].get("status") if tool_runs else None
    delegation = state.get("delegation_intent") or {}
    presence = state.get("presence_opportunities", [])
    suppression = next(
        (
            step.get("suppression") for step in reversed(state.get("trace_steps", []))
            if step.get("step") == "presence_priority"
        ),
        None,
    )
    effect_refs = {
        "memory_candidate_ids": [item.get("id") for item in state.get("memory_candidates", []) if item.get("id")],
        "growth_candidate_ids": [item.get("id") for item in state.get("growth_candidates", []) if item.get("id")],
        "continuity_snapshot_id": state.get("continuity_snapshot_id"),
        "relationship_explanation_ids": state.get("relationship_explanation_ids", []),
        "presence_opportunity_ids": [item.get("id") for item in presence if item.get("id")],
    }
    return {
        "contract_version": TURN_CONTRACT_VERSION,
        "scope": {
            "user_id": state.get("user_id"),
            "companion_id": state.get("companion_id"),
            "conversation_id": state.get("conversation_id"),
        },
        "outcome": "cancelled" if state.get("turn_cancelled") else "failed" if errors else "completed",
        "response": {
            "status": response_status,
            "assistant_message_id": state.get("assistant_message_id"),
            "provider_mode": state.get("provider_mode", "uninitialized"),
            "provider_name": state.get("provider_name"),
            "model_name": state.get("model_name"),
            "reasoning": state.get("reasoning_policy") or {
                "requested_mode": state.get("requested_reasoning_mode") or "auto",
            },
        },
        "extensions": {
            "tool_execution": {
                "status": tool_status or ("planned" if delegation else "not_requested"),
                "tool_run_ids": state.get("tool_run_ids", []),
                "delegation_intent_id": delegation.get("id"),
            },
            "meaningful_silence": {
                "status": "not_evaluated_by_current_graph",
            },
            "proactive_continuation": {
                "status": "queued" if presence else ("suppressed" if suppression and suppression.get("suppress") else "not_created"),
                "suppression_reason": suppression.get("reason") if suppression else None,
            },
            "post_turn_effects": {
                "status": (state.get("post_turn_effects") or {}).get("status") or ("recorded_by_existing_nodes" if any(_has_effect(value) for value in effect_refs.values()) else "none_recorded"),
                "refs": effect_refs,
                "transaction_contract": (state.get("post_turn_effects") or {}).get("transaction_mode") or "domain_local_with_durable_trace_journal",
            },
        },
    }


def _has_effect(value: Any) -> bool:
    return bool(value)


def _next_step_text(state: ConversationAgentState) -> str:
    memory_count = len(state.get("memory_candidates", []))
    shared_count = len(state.get("shared_memory_candidates", []))
    presence_count = len(state.get("presence_opportunities", []))
    delegation_id = (state.get("delegation_intent") or {}).get("id")
    tool_status = (state.get("tool_runs") or [{}])[-1].get("status")
    parts = []
    if memory_count:
        parts.append(f"{memory_count} new memory suggestion(s) await your confirmation")
    if shared_count:
        parts.append(f"{shared_count} shared-memory suggestion(s) await your confirmation")
    if presence_count:
        parts.append("A future check-in was prepared under your Presence settings")
    if tool_status == "awaiting_input":
        parts.append("The tool needs the missing details shown in the conversation")
    elif tool_status == "awaiting_confirmation":
        parts.append("A side-effecting tool action awaits your explicit confirmation")
    elif tool_status == "retry_scheduled":
        parts.append("The tool is scheduled for an isolated retry")
    elif tool_status in {"failed", "timed_out", "blocked"}:
        parts.append("The tool did not complete; review its structured failure before retrying")
    elif delegation_id:
        parts.append("A tool or delegated action is ready for confirmation")
    return ". ".join(parts) + "." if parts else "Continue the conversation when ready."


def _execution_signal_summary(state: ConversationAgentState) -> dict[str, Any]:
    return {
        "tool_run_count": len(state.get("tool_runs", [])),
        "file_evidence_count": len(state.get("file_evidence", [])),
        "evidence_sufficiency_count": len(state.get("evidence_sufficiency_events", [])),
        "project_task_update_count": len(state.get("project_task_updates", [])),
        "outdated_memory_flag_count": len(state.get("outdated_memory_flags", [])),
        "growth_consistency_check_count": len(state.get("growth_consistency_checks", [])),
        "bad_case_signal_count": len(state.get("bad_case_signals", [])),
        "evaluation_signal_count": len(state.get("evaluation_signals", [])),
        "llm_call_record_count": len(state.get("llm_call_record_ids", [])),
        "strategy_mode": "shadow",
        "graph_version": "v3",
    }


def _companion_context_summary(state: ConversationAgentState) -> dict[str, Any]:
    return {
        "graph_version": "v4_reoriented",
        "active_companion_id": state.get("companion_id"),
        "co_presence_session_id": (state.get("co_presence_session") or {}).get("id"),
        "shared_scene_id": (state.get("shared_scene") or {}).get("id"),
        "co_present_companion_count": len(state.get("co_present_companions", [])),
        "shared_memory_candidate_count": len(state.get("shared_memory_candidates", [])),
        "cross_companion_review_count": len(state.get("cross_companion_memory_reviews", [])),
        "delegation_intent_id": (state.get("delegation_intent") or {}).get("id"),
        "persona_guard_status": (state.get("persona_guard_result") or {}).get("check_status"),
    }
