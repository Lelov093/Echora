"""Trace the compatibility-only multimodal permission posture."""

import uuid

from sqlalchemy import select

from app.agents.state import RealtimeAgentState
from app.agents.nodes.realtime_trace_utils import append_step, record_permission_audit, record_trace_event
from app.db.models import MultimodalContextEvent, ParticipantContextPermission
from app.services.trace_service import get_session


def multimodal_permission_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        contexts = list(
            s.execute(
                select(MultimodalContextEvent)
                .where(MultimodalContextEvent.realtime_session_id == uuid.UUID(state["realtime_session_id"]))
                .order_by(MultimodalContextEvent.created_at.desc())
                .limit(10)
            ).scalars()
        )
        latest_context = contexts[0] if contexts else None
        permissions = []
        if latest_context is not None:
            permissions = list(
                s.execute(
                    select(ParticipantContextPermission)
                    .where(ParticipantContextPermission.context_event_id == latest_context.id)
                    .order_by(ParticipantContextPermission.created_at.desc())
                ).scalars()
            )
        event = record_trace_event(
            s,
            state,
            event_type="participant_permission",
            event_summary="Multimodal context permissions traced.",
            event_payload_json={
                "context_count": len(contexts),
                "latest_context_id": str(latest_context.id) if latest_context else None,
                "raw_data_storage_allowed": bool(latest_context.raw_data_storage_allowed) if latest_context else False,
                "permission_count": len(permissions),
            },
        )
        if latest_context is not None:
            record_permission_audit(
                s,
                state,
                audit_scope="context",
                realtime_trace_event_id=event.id,
                context_event_id=latest_context.id,
                audit_summary="Multimodal context remains permission and redaction gated.",
                audit_payload_json={
                    "context_type": latest_context.context_type,
                    "context_status": latest_context.context_status,
                    "raw_data_retention_policy": latest_context.raw_data_retention_policy,
                    "raw_data_storage_allowed": latest_context.raw_data_storage_allowed,
                },
            )
        state["multimodal_permission"] = {
            "context_count": len(contexts),
            "latest_context_id": str(latest_context.id) if latest_context else None,
            "raw_data_storage_allowed": bool(latest_context.raw_data_storage_allowed) if latest_context else False,
            "permission_count": len(permissions),
        }
        append_step(
            state,
            step="multimodal_permission",
            order=205,
            realtime_trace_event_id=str(event.id),
            **state["multimodal_permission"],
        )
        s.commit()
    return state
