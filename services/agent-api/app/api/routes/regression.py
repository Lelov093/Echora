"""Regression API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import regression_service

router = APIRouter(tags=["Regression"])


@router.get("/regression-cases")
def list_regression_cases(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str | None = None):
    result = regression_service.list_cases(page, page_size, status=status)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/regression-cases")
def create_regression_case(body: dict):
    return ok(regression_service.create_case(body))


@router.get("/regression-runs")
def list_regression_runs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str | None = None):
    result = regression_service.list_runs(page, page_size, status=status)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/regression-runs")
def create_regression_run(body: dict):
    return ok(regression_service.create_run(body))


@router.get("/regression-results")
def list_regression_results(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), regression_run_id: str | None = None):
    result = regression_service.list_results(page, page_size, regression_run_id=uuid.UUID(regression_run_id) if regression_run_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/regression-results")
def create_regression_result(body: dict):
    return ok(regression_service.create_result(body))


@router.post("/regression-results/{result_id}/bad-case")
def regression_result_to_bad_case(result_id: str, body: dict | None = None):
    row = regression_service.result_to_bad_case(uuid.UUID(result_id), body)
    return ok(row) if row else err("NOT_FOUND", "Regression result not found")
