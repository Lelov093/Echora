"""Persist separate low-risk EWMA user-state signals."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import user_state_service


def user_state_snapshot_node(state: ConversationAgentState) -> ConversationAgentState:
    mc_count = len(state.get("memory_candidates", []))
    gc_count = len(state.get("growth_candidates", []))
    po_count = len(state.get("presence_opportunities", []))
    selected_count = len(state.get("selected_memories", []))
    tool_count = len(state.get("tool_runs", []))
    mode = state.get("current_mode", "project")
    user_input = state.get("user_input", "")
    interaction = user_state_service.observe_interaction_acceptance(
        uuid.UUID(state["companion_id"])
    )

    observations = [
        {
            "signal_type": "project_activity",
            "observed_value": min(
                1.0,
                (0.25 if mode == "project" else 0.05)
                + (0.12 * mc_count)
                + (0.12 * gc_count)
                + (0.08 * tool_count),
            ),
            "confidence": min(0.9, 0.35 + 0.08 * (mc_count + gc_count + tool_count)),
            "source_event_count": max(1, mc_count + gc_count + tool_count),
            "reason": "Operational project activity from current graph events",
            "state_json": {"source": "conversation_graph", "low_risk_operational_signal": True},
        },
        {
            "signal_type": "creative_activity",
            "observed_value": min(
                1.0,
                (0.7 if mode == "creative" else 0.1)
                + (0.08 * po_count)
                + (
                    0.15
                    if (state.get("response_strategy") or {}).get("strategy") == "creative_expand"
                    else 0.0
                ),
            ),
            "confidence": min(0.85, 0.35 + 0.1 * po_count + (0.2 if mode == "creative" else 0.0)),
            "source_event_count": max(1, po_count),
            "reason": "Creative mode and creative response activity",
            "state_json": {"source": "conversation_graph", "low_risk_operational_signal": True},
        },
        {
            "signal_type": "interaction_acceptance",
            **interaction,
            "reason": "Explicit Companion-scoped feedback acceptance rate",
            "state_json": {
                "source": "explicit_feedback",
                "positive_count": interaction["positive_count"],
                "negative_count": interaction["negative_count"],
                "explicit_only": True,
            },
        },
        {
            "signal_type": "focus_load",
            "observed_value": min(
                1.0,
                (0.2 if mode in {"project", "learning"} else 0.1)
                + min(0.35, len(user_input) / 1200.0)
                + (0.08 * tool_count)
                + (0.04 * selected_count),
            ),
            "confidence": min(
                0.8,
                0.3 + min(0.25, len(user_input) / 2000.0) + (0.05 * tool_count),
            ),
            "source_event_count": max(1, 1 + tool_count + selected_count),
            "reason": "Task-density estimate only; not a psychological or medical inference",
            "state_json": {
                "source": "task_density",
                "low_risk_operational_signal": True,
                "not_diagnostic": True,
            },
        },
    ]

    snapshot_results = []
    errors = []
    for observation in observations:
        payload = {
            "user_id": state["user_id"],
            "companion_id": state["companion_id"],
            "conversation_id": state.get("conversation_id"),
            "trace_run_id": state.get("trace_run_id"),
            "mode_key": mode,
            "smoothing_factor": 0.8,
            "source_trace_run_ids": [state["trace_run_id"]] if state.get("trace_run_id") else [],
            **observation,
        }
        try:
            snapshot_results.append(user_state_service.create_snapshot(payload))
        except Exception as exc:
            errors.append({
                "signal_type": observation["signal_type"],
                "error": type(exc).__name__,
            })

    primary = next(
        (
            item
            for item in snapshot_results
            if item["signal_type"] == ("creative_activity" if mode == "creative" else "project_activity")
        ),
        snapshot_results[0] if snapshot_results else None,
    )
    state["user_state_snapshot_id"] = primary["id"] if primary else None

    state.setdefault("trace_steps", []).append({
        "step": "user_state_snapshot",
        "order": 10,
        "status": "completed" if len(snapshot_results) == len(observations) else "warning",
        "snapshot_id": primary["id"] if primary else None,
        "snapshot_ids": [item["id"] for item in snapshot_results],
        "signals": [
            {
                "signal_type": item["signal_type"],
                "observed_value": item["observed_value"],
                "previous_smoothed_value": item["previous_smoothed_value"],
                "smoothed_value": item["smoothed_value"],
                "smoothing_factor": item["smoothing_factor"],
                "confidence": item["confidence"],
                "source_event_count": item["source_event_count"],
            }
            for item in snapshot_results
        ],
        "errors": errors,
        "algorithm_version": "core-r8-user-state-ewma-v1",
        "sensitive_inference": False,
    })
    return state
