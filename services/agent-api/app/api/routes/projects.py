"""Project API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import project_service

router = APIRouter(tags=["Projects"])


@router.get("/project-milestones")
def list_project_milestones(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str | None = None):
    result = project_service.list_milestones(page, page_size, status=status)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/project-milestones")
def create_project_milestone(body: dict):
    return ok(project_service.create_milestone(body))


@router.get("/project-milestones/{milestone_id}")
def get_project_milestone(milestone_id: str):
    row = project_service.get_milestone(uuid.UUID(milestone_id))
    return ok(row) if row else err("NOT_FOUND", "Project milestone not found")


@router.patch("/project-milestones/{milestone_id}")
def update_project_milestone(milestone_id: str, body: dict):
    row = project_service.update_milestone(uuid.UUID(milestone_id), body)
    return ok(row) if row else err("NOT_FOUND", "Project milestone not found")


@router.get("/project-tasks")
def list_project_tasks(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str | None = None, milestone_id: str | None = None):
    result = project_service.list_tasks(page, page_size, status=status, milestone_id=uuid.UUID(milestone_id) if milestone_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/project-tasks")
def create_project_task(body: dict):
    return ok(project_service.create_task(body))


@router.get("/project-tasks/{task_id}")
def get_project_task(task_id: str):
    row = project_service.get_task(uuid.UUID(task_id))
    return ok(row) if row else err("NOT_FOUND", "Project task not found")


@router.patch("/project-tasks/{task_id}")
def update_project_task(task_id: str, body: dict):
    row = project_service.update_task(uuid.UUID(task_id), body)
    return ok(row) if row else err("NOT_FOUND", "Project task not found")


@router.post("/project-tasks/{task_id}/complete")
def complete_project_task(task_id: str, body: dict | None = None):
    row = project_service.complete_task(uuid.UUID(task_id), (body or {}).get("note"))
    return ok(row) if row else err("NOT_FOUND", "Project task not found")


@router.get("/project-tasks/{task_id}/events")
def list_project_task_events(task_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = project_service.list_task_events(uuid.UUID(task_id), page, page_size)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/project-tasks/{task_id}/evidence-links")
def create_project_task_evidence_link(task_id: str, body: dict):
    row = project_service.create_task_evidence_link(uuid.UUID(task_id), body)
    return ok(row) if row else err("NOT_FOUND", "Project task not found")
