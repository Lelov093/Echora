"""TraceLoggingNode — finalizes trace_run and writes trace_steps to DB.

Continuity enhanced: writes memory_usage_event_ids, lifecycle_event_ids,
impact_json, calibration_json, and user_visible_summary on the trace_run.
"""

import uuid
from datetime import datetime, timezone

from app.agents.state import ConversationAgentState
from app.services.trace_service import get_session
from app.db.models.trace import TraceRun, TraceStep


def trace_logging_node(state: ConversationAgentState) -> ConversationAgentState:
    s = get_session()
    tr_id_str = state.get("trace_run_id")
    if not tr_id_str:
        s.close()
        return state

    tr_id = uuid.UUID(tr_id_str)
    tr = s.query(TraceRun).get(tr_id)
    if not tr:
        s.close()
        return state

    now = datetime.now(timezone.utc)
    stage_timings = {
        item.get("stage"): item
        for item in state.get("turn_stage_timings", [])
        if item.get("stage")
    }

    # Write each trace_step to DB with Continuity fields
    for i, step_data in enumerate(state.get("trace_steps", [])):
        step_name = step_data.get("step", "unknown")
        timing = stage_timings.get(step_name) or {}

        output_json = {k: v for k, v in step_data.items() if k not in ("step", "order", "status")}

        ts = TraceStep(
            trace_run_id=tr_id,
            step_name=step_name,
            step_order=step_data.get("order", i),
            status=_persisted_step_status(step_data.get("status")),
            input_json=step_data.get("input_json", {}),
            output_json=output_json,
            score_json=step_data.get("score_json", {}),
            decision=step_data.get("decision"),
            started_at=_parse_datetime(timing.get("started_at")) or now,
            completed_at=_parse_datetime(timing.get("completed_at")) or now,
            elapsed_ms=timing.get("elapsed_ms"),
        )

        # Continuity: populate trace step extension fields from state
        if state.get("memory_usage_event_ids"):
            ts.memory_usage_event_ids = [
                uuid.UUID(eid) for eid in state["memory_usage_event_ids"]
            ]

        if state.get("memory_lifecycle_event_ids"):
            ts.lifecycle_event_ids = [
                uuid.UUID(lid) for lid in state["memory_lifecycle_event_ids"]
            ]

        # Write impact_json for memory_impact and retrieval steps
        if step_name in ("memory_impact", "retrieval_rerank") and state.get("memory_impact_summary"):
            ts.impact_json = state["memory_impact_summary"]

        # Write calibration_json for feedback-related steps
        if state.get("recent_feedback_events") or state.get("feedback_summary"):
            ts.calibration_json = {
                "feedback_events": state.get("recent_feedback_events", []),
                "feedback_summary": state.get("feedback_summary", {}),
            }

        # Agent execution: persist additive signal bundles on each step. The current
        # graph only emits a subset, but the persisted shape is stable for UI.
        ts.tool_json = step_data.get("tool_json", {"tool_runs": state.get("tool_runs", [])})
        ts.file_context_json = step_data.get("file_context_json", {"file_evidence": state.get("file_evidence", [])})
        ts.evidence_json = step_data.get("evidence_json", {"events": state.get("evidence_sufficiency_events", [])})
        ts.reranker_json = step_data.get("reranker_json", {"run_ids": state.get("memory_reranker_run_ids", [])})
        ts.presence_policy_json = step_data.get("presence_policy_json", {"run_ids": state.get("presence_policy_run_ids", [])})
        ts.bad_case_signal_json = step_data.get("bad_case_signal_json", {"signals": state.get("bad_case_signals", [])})
        ts.evaluation_signal_json = step_data.get("evaluation_signal_json", {"signals": state.get("evaluation_signals", [])})
        ts.provider_json = step_data.get("provider_json", {
            "provider_mode": state.get("provider_mode", "uninitialized"),
            "provider_name": state.get("provider_name"),
            "model_name": state.get("model_name"),
            "llm_call_record_ids": state.get("llm_call_record_ids", []),
        })
        ts.outdated_memory_json = step_data.get("outdated_memory_json", {"flags": state.get("outdated_memory_flags", [])})
        ts.growth_consistency_json = step_data.get("growth_consistency_json", {"checks": state.get("growth_consistency_checks", [])})

        s.add(ts)

    # Update trace_run
    has_errors = len(state.get("errors", [])) > 0
    tr.status = "cancelled" if state.get("turn_cancelled") else "failed" if has_errors else "completed"
    tr.model_provider = state.get("provider_name")
    tr.model_name = state.get("model_name")
    tr.output_summary = (state.get("assistant_response", "")[:200]) if state.get("assistant_response") else None
    timings = state.get("turn_stage_timings", [])
    tr.elapsed_ms = sum(
        int(item.get("elapsed_ms") or 0)
        for item in timings
    ) if timings else None

    # Continuity: write user_visible_summary on trace_run
    tr.user_visible_summary = _build_user_visible_summary(state)

    # Record generated candidate IDs
    mc_ids = [uuid.UUID(c["id"]) for c in state.get("memory_candidates", []) if c.get("id")]
    po_ids = [uuid.UUID(o["id"]) for o in state.get("presence_opportunities", []) if o.get("id")]
    gc_ids = [uuid.UUID(c["id"]) for c in state.get("growth_candidates", []) if c.get("id")]
    if mc_ids:
        tr.generated_memory_candidate_ids = mc_ids
    if po_ids:
        tr.generated_presence_opportunity_ids = po_ids
    if gc_ids:
        tr.generated_growth_candidate_ids = gc_ids

    tr.tool_run_ids = _uuid_list(state.get("tool_run_ids", []))
    tr.file_context_usage_ids = _uuid_list(state.get("file_context_usage_ids", []))
    tr.evidence_sufficiency_event_ids = _uuid_list(state.get("evidence_sufficiency_event_ids", []))
    tr.memory_reranker_run_ids = _uuid_list(state.get("memory_reranker_run_ids", []))
    tr.presence_policy_run_ids = _uuid_list(state.get("presence_policy_run_ids", []))
    tr.bad_case_signal_ids = _uuid_list(state.get("bad_case_signal_ids", []))
    tr.evaluation_signal_ids = _uuid_list(state.get("evaluation_signal_ids", []))
    tr.llm_call_record_ids = _uuid_list(state.get("llm_call_record_ids", []))
    state["execution_signal_summary"] = _build_execution_signal_summary(state)
    tr.execution_signal_summary = state["execution_signal_summary"]
    state["companion_context_summary"] = _build_companion_context_summary(state)
    metadata = dict(tr.metadata_ or {})
    metadata["companion_context"] = state["companion_context_summary"]
    metadata["turn_idempotency_key"] = state.get("turn_idempotency_key")
    metadata["post_turn_effects"] = state.get("post_turn_effects", {})
    metadata["turn_stage_timings"] = timings
    metadata["provider_timing"] = state.get("provider_timing", {})
    if (
        (state.get("post_turn_effects") or {}).get("status") == "completed"
        and not state.get("defer_post_turn_effects")
    ):
        metadata.pop("post_turn_recovery_state", None)
    tr.metadata_ = metadata

    s.commit()
    s.close()
    _safe_enqueue_quality_feedback(tr_id)

    return state


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _persisted_step_status(value: object) -> str:
    """Map runtime warning semantics into the existing persisted status contract."""
    status = str(value or "completed")
    return status if status in {"started", "completed", "failed", "skipped"} else "completed"


def _safe_enqueue_quality_feedback(trace_run_id: uuid.UUID) -> None:
    """Quality feedback is durable but may never roll back the core Trace."""
    try:
        from app.services import quality_feedback_service

        quality_feedback_service.enqueue_trace_feedback(trace_run_id)
    except Exception:
        # The bounded reconciler discovers recent terminal traces after transient
        # schema/startup failures. Trace completion remains authoritative.
        return


def _build_user_visible_summary(state: ConversationAgentState) -> str:
    """Build a brief user-visible summary of what happened in this run."""
    parts = []
    mc_count = len(state.get("memory_candidates", []))
    gc_count = len(state.get("growth_candidates", []))
    po_count = len(state.get("presence_opportunities", []))
    selected_count = len(state.get("selected_memories", []))

    if selected_count > 0:
        parts.append(f"Recalled {selected_count} related memories")
    if mc_count > 0:
        parts.append(f"Generated {mc_count} memory candidates for review")
    if gc_count > 0:
        parts.append(f"Detected {gc_count} growth signals")
    if po_count > 0:
        parts.append(f"Queued {po_count} presence opportunities")

    if state.get("assistant_response"):
        parts.append("Response generated")

    if not parts:
        return "Agent run completed"
    return ". ".join(parts) + "."


def _uuid_list(values: list) -> list[uuid.UUID]:
    result = []
    for value in values or []:
        try:
            result.append(value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)))
        except (TypeError, ValueError):
            continue
    return result


def _build_execution_signal_summary(state: ConversationAgentState) -> dict:
    return {
        "graph_version": "v3",
        "strategy_mode": "shadow",
        "tool_run_count": len(state.get("tool_runs", [])),
        "file_evidence_count": len(state.get("file_evidence", [])),
        "evidence_sufficiency_count": len(state.get("evidence_sufficiency_events", [])),
        "project_task_update_count": len(state.get("project_task_updates", [])),
        "outdated_memory_flag_count": len(state.get("outdated_memory_flags", [])),
        "growth_consistency_check_count": len(state.get("growth_consistency_checks", [])),
        "bad_case_signal_count": len(state.get("bad_case_signals", [])),
        "evaluation_signal_count": len(state.get("evaluation_signals", [])),
        "llm_call_record_count": len(state.get("llm_call_record_ids", [])),
    }


def _build_companion_context_summary(state: ConversationAgentState) -> dict:
    return {
        "graph_version": "v4_reoriented",
        "active_companion_id": state.get("companion_id"),
        "co_presence_session_id": (state.get("co_presence_session") or {}).get("id"),
        "shared_scene_id": (state.get("shared_scene") or {}).get("id"),
        "co_present_companion_count": len(state.get("co_present_companions", [])),
        "shared_memory_candidate_count": len(state.get("shared_memory_candidates", [])),
        "cross_companion_review_count": len(state.get("cross_companion_memory_reviews", [])),
        "persona_guard_status": (state.get("persona_guard_result") or {}).get("check_status"),
        "delegation_intent_id": (state.get("delegation_intent") or {}).get("id"),
    }
