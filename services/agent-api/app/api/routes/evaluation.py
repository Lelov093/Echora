"""Evaluation API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import evaluation_service, learned_policy_readiness_service

router = APIRouter(tags=["Evaluation"])


@router.get("/evaluation/core-algorithm/catalog")
def get_core_algorithm_catalog():
    return ok(evaluation_service.core_algorithm_catalog())


@router.post("/evaluation/core-algorithm/dataset")
def ensure_core_algorithm_dataset():
    return ok(evaluation_service.ensure_core_algorithm_dataset())


@router.get("/evaluation/core-algorithm/activation-gate")
def get_core_algorithm_activation_gate():
    return ok(evaluation_service.latest_core_algorithm_activation_gate())


@router.post("/evaluation/learned-policy-readiness")
def run_learned_policy_readiness(body: dict):
    try:
        companion_id = uuid.UUID(str(body["companion_id"]))
        return ok(
            learned_policy_readiness_service.run_readiness_evaluation(companion_id)
        )
    except (KeyError, ValueError) as exc:
        return err("LEARNED_POLICY_READINESS_INVALID", str(exc))


@router.get("/evaluation/learned-policy-readiness/{companion_id}")
def get_learned_policy_readiness(companion_id: str):
    try:
        return ok(
            learned_policy_readiness_service.latest_readiness(
                uuid.UUID(companion_id)
            )
        )
    except ValueError as exc:
        return err("LEARNED_POLICY_READINESS_INVALID", str(exc))


@router.get("/evaluation-datasets")
def list_evaluation_datasets(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = evaluation_service.list_datasets(page, page_size)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/evaluation-datasets")
def create_evaluation_dataset(body: dict):
    return ok(evaluation_service.create_dataset(body))


@router.get("/evaluation-cases")
def list_evaluation_cases(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), dataset_id: str | None = None):
    result = evaluation_service.list_cases(page, page_size, dataset_id=uuid.UUID(dataset_id) if dataset_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/evaluation-cases")
def create_evaluation_case(body: dict):
    return ok(evaluation_service.create_case(body))


@router.get("/evaluation-runs")
def list_evaluation_runs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), dataset_id: str | None = None):
    result = evaluation_service.list_runs(page, page_size, dataset_id=uuid.UUID(dataset_id) if dataset_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/evaluation-runs")
def create_evaluation_run(body: dict):
    return ok(evaluation_service.create_run(body))


@router.get("/evaluation-results")
def list_evaluation_results(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), evaluation_run_id: str | None = None):
    result = evaluation_service.list_results(page, page_size, evaluation_run_id=uuid.UUID(evaluation_run_id) if evaluation_run_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/evaluation-results")
def create_evaluation_result(body: dict):
    return ok(evaluation_service.create_result(body))


@router.post("/evaluation-results/{result_id}/bad-case")
def evaluation_result_to_bad_case(result_id: str, body: dict | None = None):
    row = evaluation_service.result_to_bad_case(uuid.UUID(result_id), body)
    return ok(row) if row else err("NOT_FOUND", "Evaluation result not found")
