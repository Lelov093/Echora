"""Agent execution project API service."""

import uuid
from datetime import datetime, timezone

from app.db.models import ProjectMilestone, ProjectTask, ProjectTaskEvent, ProjectTaskEvidenceLink
from app.services.persistence_helpers import create_row, default_ids, get_session, list_rows, row_to_dict, update_row


def list_milestones(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, ProjectMilestone, filters, page, page_size)


def create_milestone(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        return create_row(session, ProjectMilestone, data)


def get_milestone(milestone_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(ProjectMilestone, milestone_id)
        return row_to_dict(row) if row else None


def update_milestone(milestone_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        row = update_row(session, ProjectMilestone, milestone_id, data)
        return row


def list_tasks(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, ProjectTask, filters, page, page_size)


def create_task(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        return create_row(session, ProjectTask, data)


def get_task(task_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(ProjectTask, task_id)
        return row_to_dict(row) if row else None


def update_task(task_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        return update_row(session, ProjectTask, task_id, data)


def complete_task(task_id: uuid.UUID, note: str | None = None) -> dict | None:
    with get_session() as session:
        row = session.get(ProjectTask, task_id)
        if row is None:
            return None
        previous_status = row.status
        row.status = "done"
        row.completed_at = datetime.now(timezone.utc)
        session.add(ProjectTaskEvent(
            project_task_id=row.id,
            user_id=row.user_id,
            companion_id=row.companion_id,
            event_type="status_changed",
            previous_status=previous_status,
            new_status="done",
            description=note,
            event_json={"note": note} if note else {},
        ))
        session.commit()
        session.refresh(row)
        return row_to_dict(row)


def list_task_events(task_id: uuid.UUID, page: int = 1, page_size: int = 20) -> dict:
    with get_session() as session:
        return list_rows(session, ProjectTaskEvent, {"project_task_id": task_id}, page, page_size)


def create_task_evidence_link(task_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        task = session.get(ProjectTask, task_id)
        if task is None:
            return None
        data.pop("evidence_uri", None)
        evidence_aliases = {
            "tool": "tool_run",
            "file": "file_document",
            "trace": "trace_run",
            "bad case": "bad_case",
        }
        if data.get("evidence_type") in evidence_aliases:
            data["evidence_type"] = evidence_aliases[data["evidence_type"]]
        data["project_task_id"] = task_id
        return create_row(session, ProjectTaskEvidenceLink, data)
