"""Runtime-only entry points for the Conversation Agent Graph."""

from __future__ import annotations

from app.agents.graphs.conversation_graph import get_conversation_graph
from app.agents.state import ConversationAgentState


def build_initial_state(
    user_id: str,
    companion_id: str,
    conversation_id: str,
    content: str,
    mode_key: str,
    *,
    user_message_id: str | None = None,
    trace_run_id: str | None = None,
    turn_idempotency_key: str | None = None,
    room_turn_id: str | None = None,
    room_turn_step_id: str | None = None,
    stream_response: bool = False,
    defer_post_turn_effects: bool = False,
    reasoning_mode: str = "auto",
) -> ConversationAgentState:
    """Create the JSON-serializable runtime state for one validated turn."""
    return {
        "user_id": user_id,
        "companion_id": companion_id,
        "conversation_id": conversation_id,
        "user_input": content,
        "current_mode": mode_key,
        "user_message_id": user_message_id,
        "trace_run_id": trace_run_id,
        "turn_idempotency_key": turn_idempotency_key,
        "room_turn_id": room_turn_id,
        "room_turn_step_id": room_turn_step_id,
        "memory_candidates": [],
        "growth_candidates": [],
        "presence_opportunities": [],
        "trace_steps": [],
        "turn_stage_timings": [],
        "errors": [],
        "warnings": [],
        "provider_mode": "uninitialized",
        "provider_timing": {},
        "requested_reasoning_mode": reasoning_mode,
        "memory_usage_event_ids": [],
        "memory_lifecycle_event_ids": [],
        "memory_impact_summary": {},
        "continuity_snapshot_id": None,
        "continuity_summary": {},
        "user_state_snapshot_id": None,
        "relationship_explanation_ids": [],
        "relationship_candidates": [],
        "recent_feedback_events": [],
        "feedback_summary": {},
        "review_batch_id": None,
        "review_summary": {},
        "embedding_provider": "uninitialized",
        "tool_runs": [],
        "tool_run_ids": [],
        "tool_context": {},
        "tool_intent": {},
        "tool_observations": [],
        "tool_loop": {},
        "retrieval_tool_context": {},
        "task_run": {},
        "task_context": {},
        "task_runtime_handled": False,
        "file_evidence": [],
        "file_context_usage_ids": [],
        "evidence_sufficiency_events": [],
        "evidence_sufficiency_event_ids": [],
        "project_task_updates": [],
        "outdated_memory_flags": [],
        "outdated_memory_flag_ids": [],
        "growth_consistency_checks": [],
        "growth_consistency_check_ids": [],
        "bad_case_signals": [],
        "bad_case_signal_ids": [],
        "evaluation_signals": [],
        "evaluation_signal_ids": [],
        "memory_reranker_run_ids": [],
        "presence_policy_run_ids": [],
        "llm_call_record_ids": [],
        "execution_signal_summary": {},
        "active_companion": {},
        "co_present_companions": [],
        "co_presence_session": {},
        "participant_awareness": {},
        "shared_scene": {},
        "companion_memory_scope": {},
        "shared_memory_candidates": [],
        "cross_companion_memory_reviews": [],
        "persona_guard_result": {},
        "delegation_intent": {},
        "companion_context_summary": {},
        "post_turn_effects": {},
        "post_turn_effect_errors": [],
        "context_document_ids": [],
        "stream_response": stream_response,
        "defer_post_turn_effects": defer_post_turn_effects,
        "turn_cancelled": False,
    }


def execute_agent_turn(
    user_id: str,
    companion_id: str,
    conversation_id: str,
    content: str,
    mode_key: str = "project",
    *,
    user_message_id: str | None = None,
    trace_run_id: str | None = None,
    turn_idempotency_key: str | None = None,
    room_turn_id: str | None = None,
    room_turn_step_id: str | None = None,
    stream_response: bool = False,
    defer_post_turn_effects: bool = False,
    reasoning_mode: str = "auto",
) -> ConversationAgentState:
    """Execute the Graph only; application validation/projection live elsewhere."""
    state = build_initial_state(
        user_id, companion_id, conversation_id, content, mode_key,
        user_message_id=user_message_id,
        trace_run_id=trace_run_id,
        turn_idempotency_key=turn_idempotency_key,
        room_turn_id=room_turn_id,
        room_turn_step_id=room_turn_step_id,
        stream_response=stream_response,
        defer_post_turn_effects=defer_post_turn_effects,
        reasoning_mode=reasoning_mode,
    )
    return get_conversation_graph().invoke(state)


def run_agent(
    user_id: str,
    companion_id: str,
    conversation_id: str,
    content: str,
    mode_key: str = "project",
) -> dict:
    """Compatibility wrapper for internal callers using the former runner API."""
    state = execute_agent_turn(
        user_id, companion_id, conversation_id, content, mode_key,
    )
    from app.services.conversation_application_service import project_conversation_turn

    return project_conversation_turn(state, content)
