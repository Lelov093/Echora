"""Strategy learning API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import strategy_service

router = APIRouter(tags=["Strategy"])


@router.get("/reranker-training-examples")
def list_reranker_training_examples(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), memory_id: str | None = None):
    result = strategy_service.list_reranker_examples(page, page_size, memory_id=uuid.UUID(memory_id) if memory_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/reranker-training-examples")
def create_reranker_training_example(body: dict):
    try:
        return ok(strategy_service.create_reranker_example(body))
    except ValueError as exc:
        return err("RERANKER_SAMPLE_INVALID", str(exc))


@router.post("/reranker-training-examples/from-feedback/{feedback_event_id}")
def create_reranker_training_example_from_feedback(feedback_event_id: str, body: dict | None = None):
    row = strategy_service.build_reranker_example_from_feedback(uuid.UUID(feedback_event_id), body)
    return ok(row) if row else err("NOT_FOUND", "Feedback event not found")


@router.get("/memory-reranker-runs")
def list_memory_reranker_runs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), trace_run_id: str | None = None):
    result = strategy_service.list_memory_reranker_runs(page, page_size, trace_run_id=uuid.UUID(trace_run_id) if trace_run_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/memory-reranker-runs")
def create_memory_reranker_run(body: dict):
    try:
        return ok(strategy_service.create_memory_reranker_run(body))
    except ValueError as exc:
        return err("INVALID_LEARNING_MODE", str(exc))


@router.post("/memory-reranker-models/train")
def train_memory_reranker(body: dict):
    try:
        companion_id = uuid.UUID(str(body["companion_id"]))
        return ok(strategy_service.train_memory_reranker(companion_id))
    except (KeyError, ValueError) as exc:
        return err("RERANKER_TRAINING_INVALID", str(exc))


@router.get("/presence-policy-feedback-samples")
def list_presence_policy_feedback_samples(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), presence_opportunity_id: str | None = None):
    result = strategy_service.list_presence_feedback_samples(page, page_size, presence_opportunity_id=uuid.UUID(presence_opportunity_id) if presence_opportunity_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/presence-policy-feedback-samples")
def create_presence_policy_feedback_sample(body: dict):
    return ok(strategy_service.create_presence_feedback_sample(body))


@router.get("/presence-policy-runs")
def list_presence_policy_runs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), trace_run_id: str | None = None):
    result = strategy_service.list_presence_policy_runs(page, page_size, trace_run_id=uuid.UUID(trace_run_id) if trace_run_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/presence-policy-runs")
def create_presence_policy_run(body: dict):
    try:
        return ok(strategy_service.create_presence_policy_run(body))
    except ValueError as exc:
        return err("INVALID_LEARNING_MODE", str(exc))
