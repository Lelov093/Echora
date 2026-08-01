"""Companion delegated execution layer built on Agent execution services."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Companion,
    CoPresenceSession,
    FileDocument,
    ProjectTask,
    SharedExperienceRecord,
    SharedScene,
    ToolDefinition,
    ToolPermission,
    ToolRun,
    TraceRun,
    TraceStep,
    User,
)
from app.services import project_service, tool_service

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_delegation_intents(
    *,
    user_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(TraceRun).where(TraceRun.agent_graph_name == "delegated_execution_graph")
        if user_id is not None:
            stmt = stmt.where(TraceRun.user_id == user_id)
        if status:
            stmt = stmt.where(TraceRun.status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(TraceRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            ).scalars().all()
        )
        return {"items": [_trace_to_bundle(s, item) for item in items], "total": total}


def create_delegation_intent(payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        user_id = _resolve_user_id(s, payload)
        companion_id = _resolve_companion_id(s, payload)
        if user_id is None or companion_id is None:
            return None

        boundary = define_task_boundary(payload)
        executor_type = select_executor_type(payload)
        boundary_check = check_delegation_boundary(payload, executor_type=executor_type, session=s)
        intent_title = payload.get("task_title") or "Delegated execution intent"
        intent_summary = payload.get("task_summary") or ""

        trace = TraceRun(
            user_id=user_id,
            companion_id=companion_id,
            conversation_id=_to_uuid(payload.get("conversation_id")),
            message_id=_to_uuid(payload.get("message_id")),
            agent_graph_name="delegated_execution_graph",
            model_provider="delegated_execution",
            model_name=payload.get("executor_label", executor_type),
            input_summary=intent_summary,
            output_summary=None,
            status="failed" if not boundary_check["allowed"] else "started",
            elapsed_ms=None,
            execution_signal_summary={
                "delegation_intent": {
                    "task_title": intent_title,
                    "task_summary": intent_summary,
                    "executor_type": executor_type,
                }
            },
            metadata_={
                "implementation_origin": "delegated_execution",
                "delegation": {
                    "task_title": intent_title,
                    "task_summary": intent_summary,
                    "requested_by_companion_id": str(payload.get("requested_by_companion_id") or companion_id),
                    "co_presence_session_id": str(payload["co_presence_session_id"]) if payload.get("co_presence_session_id") else None,
                    "shared_scene_id": str(payload["shared_scene_id"]) if payload.get("shared_scene_id") else None,
                    "memory_boundary_json": payload.get("memory_boundary_json") or {},
                    "tool_constraints": payload.get("tool_constraints") or {},
                    "boundary": boundary,
                    "boundary_check": boundary_check,
                    "executor_type": executor_type,
                    "linked_execution": {},
                },
            },
        )
        s.add(trace)
        s.flush()
        write_delegation_trace(
            trace.id,
            {
                "step_name": "create_delegation_intent",
                "decision": "created" if boundary_check["allowed"] else "blocked",
                "output_json": {
                    "task_title": intent_title,
                    "task_summary": intent_summary,
                    "boundary": boundary,
                    "boundary_check": boundary_check,
                    "executor_type": executor_type,
                },
            },
            session=s,
        )
        s.commit()
        return get_delegation_intent(trace.id)


def get_delegation_intent(trace_run_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        trace = s.get(TraceRun, trace_run_id)
        if trace is None or trace.agent_graph_name != "delegated_execution_graph":
            return None
        return _trace_to_bundle(s, trace)


def define_task_boundary(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    requested_tools = payload.get("tool_constraints") or {}
    return {
        "execution_scope": payload.get("execution_scope", "delegated_assist"),
        "result_memory_mode": "candidate_review_required",
        "allow_high_risk_direct_execution": False,
        "requires_tool_permission": True,
        "allowed_tool_definition_ids": requested_tools.get("allowed_tool_definition_ids") or [],
        "allowed_project_task_ids": requested_tools.get("allowed_project_task_ids") or [],
        "allowed_file_document_ids": requested_tools.get("allowed_file_document_ids") or [],
    }


def select_executor_type(payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    preferred = str(payload.get("preferred_executor_type") or "").strip().lower()
    if preferred in {"tool", "project", "file"}:
        return preferred
    if payload.get("tool_definition_id"):
        return "tool"
    if payload.get("project_task_id") or payload.get("project_task_title") or payload.get("milestone_id"):
        return "project"
    if payload.get("file_document_id"):
        return "file"
    return "tool"


def check_delegation_boundary(
    payload: dict[str, Any] | None = None,
    *,
    executor_type: str | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    executor_type = executor_type or select_executor_type(payload)
    owned_session = session is None
    s = session or get_session()
    try:
        reasons: list[str] = []
        allowed = True
        permission_required = False
        boundary = define_task_boundary(payload)
        if executor_type == "tool":
            tool_definition_id = _to_uuid(payload.get("tool_definition_id"))
            tool_definition = s.get(ToolDefinition, tool_definition_id) if tool_definition_id else None
            if tool_definition is None and tool_definition_id is None:
                reasons.append("executor_target_pending_selection")
            elif tool_definition is None:
                reasons.append("tool_definition_missing")
                allowed = False
            else:
                if not tool_definition.is_enabled or tool_definition.deleted_at is not None:
                    reasons.append("tool_definition_disabled")
                    allowed = False
                if tool_definition.risk_level in {"high", "critical"}:
                    permission_required = True
                    reasons.append("tool_permission_required")
                if tool_definition.risk_level == "critical":
                    reasons.append("critical_tools_cannot_be_auto_executed")
                if boundary["allowed_tool_definition_ids"] and str(tool_definition.id) not in {
                    str(item) for item in boundary["allowed_tool_definition_ids"]
                }:
                    reasons.append("tool_not_in_allowed_scope")
                    allowed = False
                permission = s.execute(
                    select(ToolPermission).where(
                        ToolPermission.tool_definition_id == tool_definition.id,
                        ToolPermission.status == "active",
                    )
                ).scalar_one_or_none()
                if permission is None and permission_required:
                    reasons.append("no_active_permission_grant")
        elif executor_type == "project":
            project_task_id = _to_uuid(payload.get("project_task_id"))
            if project_task_id:
                task = s.get(ProjectTask, project_task_id)
                if task is None:
                    reasons.append("project_task_missing")
                    allowed = False
            else:
                reasons.append("executor_target_pending_selection")
            if boundary["allowed_project_task_ids"] and payload.get("project_task_id") and str(payload["project_task_id"]) not in {
                str(item) for item in boundary["allowed_project_task_ids"]
            }:
                reasons.append("project_task_not_in_allowed_scope")
                allowed = False
        elif executor_type == "file":
            document_id = _to_uuid(payload.get("file_document_id"))
            document = s.get(FileDocument, document_id) if document_id else None
            if document is None and document_id is None:
                reasons.append("executor_target_pending_selection")
            elif document is None:
                reasons.append("file_document_missing")
                allowed = False
            elif document.deleted_at is not None:
                reasons.append("file_document_deleted")
                allowed = False
        return {
            "allowed": allowed,
            "executor_type": executor_type,
            "permission_required": permission_required,
            "reasons": reasons,
            "result_memory_mode": "candidate_review_required",
        }
    finally:
        if owned_session:
            s.close()


def link_tool_run_or_project_task(trace_run_id: uuid.UUID, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    with get_session() as s:
        trace = s.get(TraceRun, trace_run_id)
        if trace is None or trace.agent_graph_name != "delegated_execution_graph":
            return None

        metadata = _delegation_metadata(trace)
        executor_type = payload.get("executor_type") or metadata.get("executor_type") or select_executor_type(payload)
        boundary_check = check_delegation_boundary(payload, executor_type=executor_type, session=s)
        if not boundary_check["allowed"]:
            write_delegation_trace(
                trace.id,
                {
                    "step_name": "link_execution",
                    "decision": "blocked",
                    "output_json": {"boundary_check": boundary_check},
                },
                session=s,
            )
            trace.status = "failed"
            s.commit()
            return _trace_to_bundle(s, trace)

        link_result: dict[str, Any]
        if executor_type == "tool":
            tool_payload = {
                "user_id": str(trace.user_id),
                "companion_id": str(trace.companion_id),
                "conversation_id": str(trace.conversation_id) if trace.conversation_id else None,
                "trace_run_id": str(trace.id),
                "tool_definition_id": payload.get("tool_definition_id"),
                "requested_by": "delegated_execution",
                "input_json": payload.get("input_json") or {
                    "task_title": metadata.get("task_title"),
                    "task_summary": metadata.get("task_summary"),
                },
                "evidence_refs": payload.get("evidence_refs") or [],
            }
            link_result = tool_service.create_tool_run(tool_payload)
            tool_run_id = link_result["id"]
            trace.tool_run_ids = list(set([*(trace.tool_run_ids or []), uuid.UUID(tool_run_id)]))
            metadata["linked_execution"] = {"executor_type": "tool", "tool_run_id": tool_run_id}
            metadata["boundary_check"] = boundary_check
            _set_delegation_metadata(trace, metadata)
        elif executor_type == "project":
            if payload.get("project_task_id"):
                existing_task = project_service.get_task(_to_uuid(payload["project_task_id"]))
                if existing_task is None:
                    return None
                link_result = existing_task
            else:
                project_payload = {
                    "user_id": str(trace.user_id),
                    "companion_id": str(trace.companion_id),
                    "conversation_id": str(trace.conversation_id) if trace.conversation_id else None,
                    "milestone_id": payload.get("milestone_id"),
                    "title": payload.get("project_task_title") or metadata.get("task_title") or "Delegated project task",
                    "description": payload.get("project_task_description") or metadata.get("task_summary"),
                    "status": payload.get("status", "todo"),
                    "priority": payload.get("priority", 0.5),
                }
                link_result = project_service.create_task(project_payload)
            metadata["linked_execution"] = {"executor_type": "project", "project_task_id": link_result["id"]}
            metadata["boundary_check"] = boundary_check
            _set_delegation_metadata(trace, metadata)
        else:
            document = s.get(FileDocument, _to_uuid(payload.get("file_document_id")))
            if document is None:
                return None
            link_result = {
                "id": str(document.id),
                "title": document.title,
                "status": document.status,
                "document_type": document.document_type,
            }
            metadata["linked_execution"] = {"executor_type": "file", "file_document_id": link_result["id"]}
            metadata["boundary_check"] = boundary_check
            _set_delegation_metadata(trace, metadata)

        trace.status = "started"
        write_delegation_trace(
            trace.id,
            {
                "step_name": "link_tool_run_or_project_task",
                "decision": executor_type,
                "output_json": {"boundary_check": boundary_check, "linked_execution": link_result},
                "tool_json": {"executor_type": executor_type, "linked_execution": link_result} if executor_type == "tool" else {},
                "file_context_json": {"linked_execution": link_result} if executor_type == "file" else {},
                "evidence_json": {"linked_execution": link_result} if executor_type == "project" else {},
            },
            session=s,
        )
        s.commit()
        return _trace_to_bundle(s, trace)


def inspect_execution_result(trace_run_id: uuid.UUID, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    with get_session() as s:
        trace = s.get(TraceRun, trace_run_id)
        if trace is None or trace.agent_graph_name != "delegated_execution_graph":
            return None

        metadata = _delegation_metadata(trace)
        linked = metadata.get("linked_execution") or {}
        executor_type = linked.get("executor_type") or metadata.get("executor_type")
        result_summary = payload.get("result_summary")
        acceptance_status = "needs_review"
        linked_result: dict[str, Any] | None = None

        if executor_type == "tool" and linked.get("tool_run_id"):
            row = s.get(ToolRun, uuid.UUID(linked["tool_run_id"]))
            if row:
                linked_result = {
                    "id": str(row.id),
                    "status": row.status,
                    "permission_required": row.permission_required,
                    "permission_granted": row.permission_granted,
                    "output_json": row.output_json or {},
                    "error_json": row.error_json or {},
                }
                result_summary = result_summary or (row.output_json or {}).get("summary") or row.status
                if row.status == "succeeded":
                    acceptance_status = "accepted"
                elif row.status in {"failed", "cancelled"}:
                    acceptance_status = "failed"
        elif executor_type == "project" and linked.get("project_task_id"):
            row = s.get(ProjectTask, uuid.UUID(linked["project_task_id"]))
            if row:
                linked_result = {
                    "id": str(row.id),
                    "status": row.status,
                    "title": row.title,
                    "evidence_summary": row.evidence_summary,
                }
                result_summary = result_summary or row.evidence_summary or row.status
                if row.status == "done":
                    acceptance_status = "accepted"
        elif executor_type == "file" and linked.get("file_document_id"):
            row = s.get(FileDocument, uuid.UUID(linked["file_document_id"]))
            if row:
                linked_result = {
                    "id": str(row.id),
                    "status": row.status,
                    "title": row.title,
                    "summary": row.summary,
                }
                result_summary = result_summary or row.summary or row.status
                if row.status == "ready":
                    acceptance_status = "accepted"

        if payload.get("force_status") in {"accepted", "needs_review", "failed"}:
            acceptance_status = payload["force_status"]
        acceptance_note = payload.get("acceptance_note") or _default_acceptance_note(acceptance_status)
        trace.output_summary = result_summary
        trace.status = "failed" if acceptance_status == "failed" else "completed"
        metadata["inspection"] = {
            "acceptance_status": acceptance_status,
            "acceptance_note": acceptance_note,
            "result_summary": result_summary,
        }
        _set_delegation_metadata(trace, metadata)
        write_delegation_trace(
            trace.id,
            {
                "step_name": "inspect_execution_result",
                "decision": acceptance_status,
                "output_json": {
                    "linked_result": linked_result,
                    "result_summary": result_summary,
                    "acceptance_note": acceptance_note,
                },
            },
            session=s,
        )
        s.commit()
        return _trace_to_bundle(s, trace)


def create_shared_experience_from_result_candidate(
    trace_run_id: uuid.UUID, payload: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    payload = payload or {}
    with get_session() as s:
        trace = s.get(TraceRun, trace_run_id)
        if trace is None or trace.agent_graph_name != "delegated_execution_graph":
            return None
        metadata = _delegation_metadata(trace)
        linked = metadata.get("linked_execution") or {}
        inspection = metadata.get("inspection") or {}
        record = SharedExperienceRecord(
            user_id=trace.user_id,
            co_presence_session_id=_to_uuid(metadata.get("co_presence_session_id")),
            shared_scene_id=_to_uuid(metadata.get("shared_scene_id")),
            source_scene_event_id=None,
            source_conversation_id=trace.conversation_id,
            source_trace_run_id=trace.id,
            source_type="delegation_result",
            experience_title=payload.get("experience_title") or metadata.get("task_title"),
            experience_summary=payload.get("experience_summary")
            or inspection.get("result_summary")
            or trace.output_summary
            or metadata.get("task_summary")
            or "",
            experience_detail=payload.get("experience_detail") or inspection.get("acceptance_note"),
            experience_status="candidate_pending_review",
            recommended_memory_action="shared_candidate",
            review_required=True,
            created_by_participant_id=None,
            approved_shared_memory_id=None,
            policy_snapshot_json={
                "delegation_trace_run_id": str(trace.id),
                "linked_execution": linked,
                "inspection": inspection,
                "result_memory_mode": "candidate_review_required",
            },
            occurred_at=datetime.now(timezone.utc),
            metadata_={"implementation_origin": "delegated_execution"},
        )
        s.add(record)
        s.flush()
        metadata["shared_experience_record_id"] = str(record.id)
        _set_delegation_metadata(trace, metadata)
        write_delegation_trace(
            trace.id,
            {
                "step_name": "create_shared_experience_from_result_candidate",
                "decision": "candidate_created",
                "output_json": {
                    "shared_experience_record_id": str(record.id),
                    "review_required": True,
                },
            },
            session=s,
        )
        s.commit()
        s.refresh(record)
        return {
            "delegation_intent": _trace_to_bundle(s, trace),
            "shared_experience_record": _shared_experience_to_dict(record),
        }


def write_delegation_trace(
    trace_run_id: uuid.UUID,
    payload: dict[str, Any],
    *,
    session: Session | None = None,
) -> dict[str, Any] | None:
    owned_session = session is None
    s = session or get_session()
    try:
        trace = s.get(TraceRun, trace_run_id)
        if trace is None:
            return None
        step_name = payload["step_name"]
        step = s.execute(
            select(TraceStep).where(
                TraceStep.trace_run_id == trace.id,
                TraceStep.step_name == step_name,
            )
        ).scalar_one_or_none()
        if step is None:
            existing_count = s.execute(
                select(func.count()).select_from(TraceStep).where(TraceStep.trace_run_id == trace.id)
            ).scalar() or 0
            step = TraceStep(
                trace_run_id=trace.id,
                step_name=step_name,
                step_order=int(existing_count),
                status=payload.get("status", "completed"),
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                decision=payload.get("decision"),
                output_json=payload.get("output_json") or {},
                tool_json=payload.get("tool_json") or {},
                file_context_json=payload.get("file_context_json") or {},
                evidence_json=payload.get("evidence_json") or {},
                user_visible_summary=payload.get("user_visible_summary"),
                metadata_={"implementation_origin": "delegated_execution"},
            )
            s.add(step)
        else:
            step.status = payload.get("status", step.status)
            step.completed_at = datetime.now(timezone.utc)
            step.decision = payload.get("decision", step.decision)
            step.output_json = payload.get("output_json") or step.output_json
            step.tool_json = payload.get("tool_json") or step.tool_json
            step.file_context_json = payload.get("file_context_json") or step.file_context_json
            step.evidence_json = payload.get("evidence_json") or step.evidence_json
            if payload.get("user_visible_summary") is not None:
                step.user_visible_summary = payload["user_visible_summary"]
        if owned_session:
            s.commit()
            s.refresh(step)
        return _trace_step_to_dict(step)
    finally:
        if owned_session:
            s.close()


def _trace_to_bundle(s: Session, trace: TraceRun) -> dict[str, Any]:
    steps = list(
        s.execute(
            select(TraceStep).where(TraceStep.trace_run_id == trace.id).order_by(TraceStep.step_order.asc())
        ).scalars().all()
    )
    return {
        "id": str(trace.id),
        "user_id": str(trace.user_id),
        "companion_id": str(trace.companion_id),
        "conversation_id": str(trace.conversation_id) if trace.conversation_id else None,
        "status": trace.status,
        "agent_graph_name": trace.agent_graph_name,
        "input_summary": trace.input_summary,
        "output_summary": trace.output_summary,
        "tool_run_ids": [str(item) for item in (trace.tool_run_ids or [])],
        "metadata": trace.metadata_ or {},
        "steps": [_trace_step_to_dict(item) for item in steps],
    }


def _trace_step_to_dict(step: TraceStep) -> dict[str, Any]:
    return {
        "id": str(step.id),
        "step_name": step.step_name,
        "step_order": step.step_order,
        "status": step.status,
        "decision": step.decision,
        "output_json": step.output_json or {},
        "tool_json": step.tool_json or {},
        "file_context_json": step.file_context_json or {},
        "evidence_json": step.evidence_json or {},
    }


def _shared_experience_to_dict(record: SharedExperienceRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "shared_scene_id": str(record.shared_scene_id) if record.shared_scene_id else None,
        "co_presence_session_id": str(record.co_presence_session_id) if record.co_presence_session_id else None,
        "source_trace_run_id": str(record.source_trace_run_id) if record.source_trace_run_id else None,
        "source_type": record.source_type,
        "experience_title": record.experience_title,
        "experience_summary": record.experience_summary,
        "experience_detail": record.experience_detail,
        "experience_status": record.experience_status,
        "recommended_memory_action": record.recommended_memory_action,
        "review_required": record.review_required,
    }


def _resolve_user_id(s: Session, payload: dict[str, Any]) -> uuid.UUID | None:
    value = _to_uuid(payload.get("user_id"))
    if value:
        return value
    row = s.query(User).first()
    return row.id if row else None


def _resolve_companion_id(s: Session, payload: dict[str, Any]) -> uuid.UUID | None:
    value = _to_uuid(payload.get("requested_by_companion_id")) or _to_uuid(payload.get("companion_id"))
    if value:
        return value
    row = s.query(Companion).first()
    return row.id if row else None


def _delegation_metadata(trace: TraceRun) -> dict[str, Any]:
    metadata = trace.metadata_ or {}
    delegation = dict(metadata.get("delegation") or {})
    delegation.setdefault("linked_execution", {})
    return delegation


def _set_delegation_metadata(trace: TraceRun, delegation: dict[str, Any]) -> None:
    root = dict(trace.metadata_ or {})
    root["delegation"] = dict(delegation)
    trace.metadata_ = root


def _default_acceptance_note(status: str) -> str:
    mapping = {
        "accepted": "Execution result inspected and accepted for delegated follow-up.",
        "failed": "Execution result failed inspection and requires correction.",
        "needs_review": "Execution result requires human or companion review before acceptance.",
    }
    return mapping.get(status, "Delegated execution inspected.")


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
