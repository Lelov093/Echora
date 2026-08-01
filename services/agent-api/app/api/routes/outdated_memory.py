"""Outdated memory API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import outdated_memory_service

router = APIRouter(tags=["Outdated Memory"])


@router.get("/outdated-memory-flags")
def list_outdated_memory_flags(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), memory_id: str | None = None, status: str | None = None):
    result = outdated_memory_service.list_flags(page, page_size, memory_id=uuid.UUID(memory_id) if memory_id else None, status=status)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/outdated-memory-flags")
def create_outdated_memory_flag(body: dict):
    return ok(outdated_memory_service.create_flag(body))


@router.patch("/outdated-memory-flags/{flag_id}")
def update_outdated_memory_flag(flag_id: str, body: dict):
    row = outdated_memory_service.update_flag(uuid.UUID(flag_id), body)
    return ok(row) if row else err("NOT_FOUND", "Outdated memory flag not found")


@router.get("/outdated-memory-reviews")
def list_outdated_memory_reviews(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), memory_id: str | None = None):
    result = outdated_memory_service.list_reviews(page, page_size, memory_id=uuid.UUID(memory_id) if memory_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/outdated-memory-flags/{flag_id}/review")
def create_outdated_memory_review(flag_id: str, body: dict):
    row = outdated_memory_service.create_review(uuid.UUID(flag_id), body)
    return ok(row) if row else err("NOT_FOUND", "Outdated memory flag not found")
