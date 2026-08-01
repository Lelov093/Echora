"""Realtime compatibility session graph.

This graph is an additive trace graph for realtime co-presence. It does not
replace ConversationGraph V4 Reoriented and does not implement media transport.
"""

from langgraph.graph import END, StateGraph

from app.agents.state import RealtimeAgentState
from app.agents.nodes.multimodal_permission_node import multimodal_permission_node
from app.agents.nodes.participant_awareness_realtime_node import participant_awareness_realtime_node
from app.agents.nodes.realtime_channel_event_node import realtime_channel_event_node
from app.agents.nodes.realtime_memory_buffer_node import realtime_memory_buffer_node
from app.agents.nodes.realtime_algorithm_decision_node import realtime_algorithm_decision_node
from app.agents.nodes.realtime_session_start_node import realtime_session_start_node
from app.agents.nodes.realtime_speaker_turn_node import realtime_speaker_turn_node
from app.agents.nodes.realtime_trace_logging_node import realtime_trace_logging_node
from app.agents.nodes.resident_presence_node import resident_presence_node
from app.agents.nodes.realtime_hard_stop_gate_node import realtime_hard_stop_gate_node
from app.agents.nodes.shared_moment_candidate_node import shared_moment_candidate_node


def build_realtime_session_graph() -> StateGraph:
    builder = StateGraph(RealtimeAgentState)

    builder.add_node("realtime_session_start", realtime_session_start_node)
    builder.add_node("participant_awareness_realtime", participant_awareness_realtime_node)
    builder.add_node("realtime_channel_event", realtime_channel_event_node)
    builder.add_node("multimodal_permission", multimodal_permission_node)
    builder.add_node("scoped_hard_stop", realtime_hard_stop_gate_node)
    builder.add_node("realtime_algorithm_decision", realtime_algorithm_decision_node)
    builder.add_node("companion_voice_turn", realtime_speaker_turn_node)
    builder.add_node("realtime_memory_buffer", realtime_memory_buffer_node)
    builder.add_node("shared_moment_candidate", shared_moment_candidate_node)
    builder.add_node("resident_presence", resident_presence_node)
    builder.add_node("realtime_trace_logging", realtime_trace_logging_node)

    builder.set_entry_point("realtime_session_start")
    builder.add_edge("realtime_session_start", "participant_awareness_realtime")
    builder.add_edge("participant_awareness_realtime", "realtime_channel_event")
    builder.add_edge("realtime_channel_event", "multimodal_permission")
    builder.add_edge("multimodal_permission", "scoped_hard_stop")
    builder.add_edge("scoped_hard_stop", "realtime_algorithm_decision")
    builder.add_edge("realtime_algorithm_decision", "companion_voice_turn")
    builder.add_edge("companion_voice_turn", "realtime_memory_buffer")
    builder.add_conditional_edges(
        "realtime_memory_buffer",
        _memory_candidate_route,
        {
            "candidate": "shared_moment_candidate",
            "blocked": "resident_presence",
        },
    )
    builder.add_edge("shared_moment_candidate", "resident_presence")
    builder.add_edge("resident_presence", "realtime_trace_logging")
    builder.add_edge("realtime_trace_logging", END)

    return builder.compile()


def _memory_candidate_route(state: RealtimeAgentState) -> str:
    decision = (state.get("realtime_session") or {}).get("realtime_algorithm_decision") or {}
    return "blocked" if decision.get("reason") in {"hard_stop", "revoked"} else "candidate"


_realtime_session_graph = None


def get_realtime_session_graph():
    global _realtime_session_graph
    if _realtime_session_graph is None:
        _realtime_session_graph = build_realtime_session_graph()
    return _realtime_session_graph
