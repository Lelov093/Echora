"""Trace compatibility-only realtime memory gate behavior."""

import uuid

from sqlalchemy import select

from app.agents.state import RealtimeAgentState
from app.agents.nodes.realtime_trace_utils import append_step, record_memory_gate, record_permission_audit, record_trace_event
from app.db.models import RealtimeMemoryBuffer
from app.services.trace_service import get_session


def realtime_memory_buffer_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        buffer = (
            s.execute(
                select(RealtimeMemoryBuffer)
                .where(RealtimeMemoryBuffer.realtime_session_id == uuid.UUID(state["realtime_session_id"]))
                .order_by(RealtimeMemoryBuffer.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        )
        event = record_trace_event(
            s,
            state,
            event_type="memory_gate",
            event_summary="Realtime memory gate blocked automatic long-term writes.",
            event_payload_json={
                "memory_buffer_id": str(buffer.id) if buffer else None,
                "review_required": True,
                "auto_write_private_memory": False,
                "auto_write_shared_memory": False,
            },
        )
        gate = record_memory_gate(
            s,
            state,
            realtime_trace_event_id=event.id,
            memory_buffer_id=buffer.id if buffer else None,
            gate_status="review_required",
            gate_payload_json={
                "buffer_scope": buffer.buffer_scope if buffer else "realtime_session",
                "auto_write_blocked": True,
                "observing_companion_default_memory": "disabled",
            },
        )
        record_permission_audit(
            s,
            state,
            audit_scope="memory",
            realtime_trace_event_id=event.id,
            audit_summary="Realtime memory gate requires review before private/shared writes.",
            audit_payload_json={"memory_gate_trace_id": str(gate.id), "auto_write_blocked": True},
        )
        state["realtime_memory_gate"] = {
            "memory_gate_trace_id": str(gate.id),
            "memory_buffer_id": str(buffer.id) if buffer else None,
            "gate_status": gate.gate_status,
            "auto_write_blocked": gate.auto_write_blocked,
            "pipeline": [
                "raw_event",
                "safe_summary",
                "salient_moment",
                "memory_candidate",
                "review",
            ],
            "raw_event_storage_allowed": False,
            "buffer_retention_policy": buffer.retention_policy if buffer else "ephemeral",
            "buffer_expires_at": buffer.expires_at.isoformat() if buffer and buffer.expires_at else None,
        }
        append_step(state, step="realtime_memory_buffer", order=208, realtime_trace_event_id=str(event.id), **state["realtime_memory_gate"])
        s.commit()
    return state
