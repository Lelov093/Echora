"""Summarize a compatibility-only shared moment candidate without committing memory."""

from app.agents.state import RealtimeAgentState
from app.agents.nodes.realtime_trace_utils import append_step, record_trace_event
from app.services.trace_service import get_session


def shared_moment_candidate_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        candidate = {
            "candidate_status": "pending_review",
            "review_required": True,
            "auto_write_private_memory": False,
            "auto_write_shared_memory": False,
            "source": "realtime_graph_summary",
            "summary": "Realtime co-presence produced a review-gated shared moment candidate.",
        }
        event = record_trace_event(
            s,
            state,
            event_type="memory_gate",
            event_summary="Shared moment candidate kept review-gated.",
            event_payload_json=candidate,
        )
        state["shared_moment_candidate"] = candidate
        append_step(
            state,
            step="shared_moment_candidate",
            order=207,
            realtime_trace_event_id=str(event.id),
            **candidate,
        )
        s.commit()
    return state
