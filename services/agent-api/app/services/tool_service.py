"""Agent execution tool API service."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import BadCase, Companion, ToolDefinition, ToolPermission, ToolRun
from app.services.persistence_helpers import (
    as_uuid,
    create_row,
    default_ids,
    get_session,
    list_rows,
    row_to_dict,
    update_row,
)


def list_tool_definitions(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, ToolDefinition, filters, page, page_size)


def create_tool_definition(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        return create_row(session, ToolDefinition, data)


def get_tool_definition(tool_definition_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(ToolDefinition, tool_definition_id)
        return row_to_dict(row) if row else None


def update_tool_definition(tool_definition_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        return update_row(session, ToolDefinition, tool_definition_id, data)


def delete_tool_definition(tool_definition_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(ToolDefinition, tool_definition_id)
        if row is None:
            return None
        row.deleted_at = datetime.now(timezone.utc)
        row.is_enabled = False
        session.commit()
        session.refresh(row)
        return row_to_dict(row)


def list_tool_permissions(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, ToolPermission, filters, page, page_size)


def create_tool_permission(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        return create_row(session, ToolPermission, data)


def update_tool_permission(permission_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        return update_row(session, ToolPermission, permission_id, data)


def update_tool_permission_scoped(permission_id: uuid.UUID, companion_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        row = session.get(ToolPermission, permission_id)
        companion = session.get(Companion, companion_id)
        if row is None or companion is None or row.companion_id != companion_id or row.user_id != companion.user_id:
            return None
        allowed = {"policy", "status", "allowed_until", "reason", "scope_json"}
        for key, value in data.items():
            if key in allowed:
                setattr(row, key, value)
        session.commit()
        session.refresh(row)
        return row_to_dict(row)


def set_tool_permission_scoped(
    tool_definition_id: uuid.UUID,
    companion_id: uuid.UUID,
    policy: str,
    reason: str | None = None,
) -> dict | None:
    with get_session() as session:
        companion = session.get(Companion, companion_id)
        definition = session.get(ToolDefinition, tool_definition_id)
        if companion is None or definition is None or definition.deleted_at is not None:
            return None
        row = session.execute(
            select(ToolPermission)
            .where(
                ToolPermission.user_id == companion.user_id,
                ToolPermission.companion_id == companion_id,
                ToolPermission.tool_definition_id == tool_definition_id,
                ToolPermission.deleted_at.is_(None),
            )
            .order_by(ToolPermission.created_at.desc())
        ).scalars().first()
        if row is None:
            row = ToolPermission(
                user_id=companion.user_id,
                companion_id=companion_id,
                tool_definition_id=tool_definition_id,
            )
            session.add(row)
        previous_policy = row.policy
        row.policy = policy
        row.status = "active"
        row.allowed_until = None
        row.reason = reason or "user_configured"
        scope = dict(row.scope_json or {})
        if previous_policy != policy:
            scope.pop("ask_once_granted_at", None)
        row.scope_json = scope
        session.commit()
        session.refresh(row)
        return row_to_dict(row)


def list_tool_runs(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, ToolRun, filters, page, page_size)


def create_tool_run(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)

        definition = None
        definition_id = as_uuid(data.get("tool_definition_id"))
        if definition_id:
            definition = session.get(ToolDefinition, definition_id)
        risk_level = data.get("risk_level") or (definition.risk_level if definition else "medium")
        data["risk_level"] = risk_level
        if risk_level in ("high", "critical"):
            data["permission_required"] = True
            data["permission_granted"] = False
            data["status"] = "permission_required"
        else:
            data.setdefault("permission_required", False)
            data.setdefault("permission_granted", True)
            data.setdefault("status", "planned")
        return create_row(session, ToolRun, data)


def get_tool_run(tool_run_id: uuid.UUID, companion_id: uuid.UUID | None = None) -> dict | None:
    with get_session() as session:
        row = session.get(ToolRun, tool_run_id)
        return row_to_dict(row) if row and (companion_id is None or row.companion_id == companion_id) else None


def confirm_tool_run(tool_run_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(ToolRun, tool_run_id)
        if row is None:
            return None
        row.permission_granted = True
        row.status = "planned"
        session.commit()
        session.refresh(row)
        return row_to_dict(row)


def cancel_tool_run(tool_run_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(ToolRun, tool_run_id)
        if row is None:
            return None
        row.status = "cancelled"
        row.completed_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        return row_to_dict(row)


def retry_tool_run(tool_run_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(ToolRun, tool_run_id)
        if row is None:
            return None
        data = row_to_dict(row)
        for key in ("id", "created_at", "updated_at", "started_at", "completed_at", "deleted_at"):
            data.pop(key, None)
        data["status"] = "permission_required" if data.get("permission_required") else "planned"
        return create_row(session, ToolRun, data)


def create_tool_run_bad_case(tool_run_id: uuid.UUID, data: dict | None = None, companion_id: uuid.UUID | None = None) -> dict | None:
    with get_session() as session:
        run = session.get(ToolRun, tool_run_id)
        if run is None or (companion_id is not None and run.companion_id != companion_id):
            return None
        payload = data or {}
        bad_case = BadCase(
            user_id=run.user_id,
            companion_id=run.companion_id,
            conversation_id=run.conversation_id,
            trace_run_id=run.trace_run_id,
            type="other",
            title=payload.get("title") or f"Tool run issue: {run.id}",
            description=payload.get("description") or "Created from a Agent execution tool run.",
            severity=payload.get("severity") or ("high" if run.risk_level in ("high", "critical") else "medium"),
            status="open",
            evidence_links=[{"type": "tool_run", "id": str(run.id)}],
        )
        session.add(bad_case)
        session.commit()
        session.refresh(bad_case)
        return row_to_dict(bad_case)
