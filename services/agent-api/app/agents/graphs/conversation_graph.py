"""ConversationGraph — Continuity ConversationGraph.

Node order (Continuity):
  input → boundary_check → working_memory → memory_retrieval
  → retrieval_rerank → memory_impact → companion_context_snapshot
  → response_planning → response_generation
  → memory_candidate → growth_candidate → presence_opportunity
  → continuity_update → user_state_snapshot → relationship_explanation
  → review_commit_v2 → trace_logging

Uses langgraph.graph.StateGraph (compiled graph).
"""

from datetime import datetime, timezone
from time import perf_counter
from typing import Callable
import uuid

from langgraph.graph import StateGraph, END

from app.agents.state import ConversationAgentState
from app.agents.nodes.input_node import input_node
from app.agents.nodes.companion_identity_activation_node import companion_identity_activation_node
from app.agents.nodes.co_presence_context_node import co_presence_context_node
from app.agents.nodes.participant_awareness_node import participant_awareness_node
from app.agents.nodes.shared_scene_context_node import shared_scene_context_node
from app.agents.nodes.companion_memory_scope_node import companion_memory_scope_node
from app.agents.nodes.cross_companion_memory_boundary_node import cross_companion_memory_boundary_node
from app.agents.nodes.persona_guard_node import persona_guard_node
from app.agents.nodes.boundary_check_node import boundary_check_node
from app.agents.nodes.working_memory_node import working_memory_node
from app.agents.nodes.memory_retrieval_node import memory_retrieval_node
from app.agents.nodes.retrieval_rerank_node import retrieval_rerank_node
from app.agents.nodes.memory_impact_node import memory_impact_node
from app.agents.nodes.companion_context_snapshot_node import companion_context_snapshot_node
from app.agents.nodes.tool_runtime_node import tool_runtime_node
from app.agents.nodes.conversation_task_runtime_node import (
    conversation_task_runtime_node,
    conversation_task_reconcile_node,
)
from app.agents.nodes.response_planning_node import response_planning_node
from app.agents.nodes.response_generation_node import response_generation_node
from app.agents.nodes.post_turn_effects_node import post_turn_effects_node
from app.agents.nodes.trace_logging_node import trace_logging_node
from app.services import conversation_turn_event_service, conversation_turn_journal_service


def _timed_node(
    stage: str,
    node: Callable[[ConversationAgentState], ConversationAgentState],
    *,
    lifecycle_before: str | None = None,
    lifecycle_after: str | None = None,
):
    """Measure real node wall time and best-effort publish async lifecycle state."""
    def run(state: ConversationAgentState) -> ConversationAgentState:
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        _safe_lifecycle_update(state, lifecycle_before)
        result = state
        failed = False
        try:
            result = node(state)
            failed = _stage_failed(result, stage)
            if not failed:
                _safe_lifecycle_update(result, lifecycle_after)
            return result
        except Exception:
            failed = True
            raise
        finally:
            completed_at = datetime.now(timezone.utc)
            result.setdefault("turn_stage_timings", []).append({
                "stage": stage,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "elapsed_ms": round((perf_counter() - started) * 1000),
                "status": "failed" if failed else "completed",
            })

    return run


def _safe_lifecycle_update(state: ConversationAgentState, status: str | None) -> None:
    trace_run_id = state.get("trace_run_id")
    if not status or not trace_run_id:
        return
    try:
        updated = conversation_turn_journal_service.update_turn_lifecycle(
            uuid.UUID(str(trace_run_id)),
            status,
        )
        if updated:
            conversation_turn_event_service.publish(
                uuid.UUID(str(trace_run_id)),
                "lifecycle",
                {"status": status},
            )
    except Exception:
        # Observability must never break the authoritative Conversation turn.
        return


def _stage_failed(state: ConversationAgentState, stage: str) -> bool:
    return any(item.get("step") == stage for item in state.get("errors", []))


def _route_after_response_generation(state: ConversationAgentState) -> str:
    if state.get("errors"):
        return "failed"
    if state.get("defer_post_turn_effects"):
        return "deferred"
    return "completed"


def build_conversation_graph() -> StateGraph:
    """Build and compile the Continuity ConversationGraph.

    Returns a compiled StateGraph ready for .invoke(state).
    """
    builder = StateGraph(ConversationAgentState)

    # Register nodes
    builder.add_node("input", _timed_node("input", input_node, lifecycle_before="context_preparing"))
    builder.add_node("companion_identity_activation", _timed_node("companion_identity_activation", companion_identity_activation_node))
    builder.add_node("co_presence_context", _timed_node("co_presence_context", co_presence_context_node))
    builder.add_node("participant_awareness", _timed_node("participant_awareness", participant_awareness_node))
    builder.add_node("shared_scene_context", _timed_node("shared_scene_context", shared_scene_context_node))
    builder.add_node("companion_memory_scope", _timed_node("companion_memory_scope", companion_memory_scope_node))
    builder.add_node("cross_companion_memory_boundary", _timed_node("cross_companion_memory_boundary", cross_companion_memory_boundary_node))
    builder.add_node("persona_guard", _timed_node("persona_guard", persona_guard_node))
    builder.add_node("boundary_check", _timed_node("boundary_check", boundary_check_node))
    builder.add_node("working_memory", _timed_node("working_memory", working_memory_node))
    builder.add_node("memory_retrieval", _timed_node("memory_retrieval", memory_retrieval_node))
    builder.add_node("retrieval_rerank", _timed_node("retrieval_rerank", retrieval_rerank_node))
    builder.add_node("memory_impact", _timed_node("memory_impact", memory_impact_node))
    builder.add_node("companion_context_snapshot", _timed_node("companion_context_snapshot", companion_context_snapshot_node))
    builder.add_node("conversation_task_runtime", _timed_node("conversation_task_runtime", conversation_task_runtime_node))
    builder.add_node("tool_runtime", _timed_node("tool_runtime", tool_runtime_node))
    builder.add_node("conversation_task_reconcile", _timed_node("conversation_task_reconcile", conversation_task_reconcile_node))
    builder.add_node("response_planning", _timed_node("response_planning", response_planning_node))
    builder.add_node("response_generation", _timed_node("response_generation", response_generation_node, lifecycle_before="provider_waiting", lifecycle_after="response_persisted"))
    builder.add_node("post_turn_effects", _timed_node("post_turn_effects", post_turn_effects_node, lifecycle_before="effects_processing"))
    builder.add_node("trace_logging", trace_logging_node)

    # Set entry point
    builder.set_entry_point("input")

    # Define edges (Continuity sequential pipeline)
    builder.add_conditional_edges(
        "input",
        lambda state: "failed" if state.get("errors") else "ready",
        {"failed": "trace_logging", "ready": "companion_identity_activation"},
    )
    builder.add_edge("companion_identity_activation", "co_presence_context")
    builder.add_edge("co_presence_context", "participant_awareness")
    builder.add_edge("participant_awareness", "shared_scene_context")
    builder.add_edge("shared_scene_context", "companion_memory_scope")
    builder.add_edge("companion_memory_scope", "cross_companion_memory_boundary")
    builder.add_edge("cross_companion_memory_boundary", "persona_guard")
    builder.add_edge("persona_guard", "boundary_check")
    builder.add_edge("boundary_check", "working_memory")
    builder.add_edge("working_memory", "memory_retrieval")
    builder.add_edge("memory_retrieval", "retrieval_rerank")
    builder.add_edge("retrieval_rerank", "memory_impact")
    builder.add_edge("memory_impact", "companion_context_snapshot")
    builder.add_edge("companion_context_snapshot", "conversation_task_runtime")
    builder.add_edge("conversation_task_runtime", "tool_runtime")
    builder.add_edge("tool_runtime", "conversation_task_reconcile")
    builder.add_edge("conversation_task_reconcile", "response_planning")
    builder.add_edge("response_planning", "response_generation")
    builder.add_conditional_edges(
        "response_generation",
        _route_after_response_generation,
        {"failed": "trace_logging", "deferred": END, "completed": "post_turn_effects"},
    )
    builder.add_edge("post_turn_effects", "trace_logging")
    builder.add_edge("trace_logging", END)

    return builder.compile()


# Singleton instance
_conversation_graph = None


def get_conversation_graph():
    """Get or create the compiled ConversationGraph singleton."""
    global _conversation_graph
    if _conversation_graph is None:
        _conversation_graph = build_conversation_graph()
    return _conversation_graph
