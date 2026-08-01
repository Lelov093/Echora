"""Quality feedback inbox API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import bad_case_inbox_service

router = APIRouter(tags=["Quality Feedback"])


@router.get("/bad-case-inbox")
def list_bad_case_inbox(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str | None = None):
    result = bad_case_inbox_service.list_items(page, page_size, status=status)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/bad-case-inbox")
def create_bad_case_inbox_item(body: dict):
    return ok(bad_case_inbox_service.create_item(body))


@router.get("/bad-case-inbox/{item_id}")
def get_bad_case_inbox_item(item_id: str):
    row = bad_case_inbox_service.get_item(uuid.UUID(item_id))
    return ok(row) if row else err("NOT_FOUND", "Bad case inbox item not found")


@router.patch("/bad-case-inbox/{item_id}")
def update_bad_case_inbox_item(item_id: str, body: dict):
    row = bad_case_inbox_service.update_item(uuid.UUID(item_id), body)
    return ok(row) if row else err("NOT_FOUND", "Bad case inbox item not found")


@router.post("/bad-case-inbox/{item_id}/triage")
def triage_bad_case_inbox_item(item_id: str, body: dict):
    row = bad_case_inbox_service.triage_item(uuid.UUID(item_id), body)
    return ok(row) if row else err("NOT_FOUND", "Bad case inbox item not found")


@router.post("/bad-case-inbox/{item_id}/links")
def create_bad_case_link(item_id: str, body: dict):
    row = bad_case_inbox_service.create_link(uuid.UUID(item_id), body)
    return ok(row) if row else err("NOT_FOUND", "Bad case inbox item not found")


@router.post("/bad-case-inbox/{item_id}/bad-case")
def convert_bad_case_inbox_item(item_id: str, body: dict | None = None):
    row = bad_case_inbox_service.convert_to_bad_case(uuid.UUID(item_id), body)
    return ok(row) if row else err("NOT_FOUND", "Bad case inbox item not found")


@router.post("/bad-case-inbox/{item_id}/regression-case")
def convert_bad_case_inbox_item_to_regression(item_id: str, body: dict | None = None):
    row = bad_case_inbox_service.convert_to_regression_case(uuid.UUID(item_id), body)
    return ok(row) if row else err("NOT_FOUND", "Bad case inbox item not found")
