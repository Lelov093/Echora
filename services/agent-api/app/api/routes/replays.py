"""Replay API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import replay_service

router = APIRouter(tags=["Replays"])


@router.get("/replays")
def list_replays(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), trace_run_id: str | None = None):
    result = replay_service.list_replays(page, page_size, trace_run_id=uuid.UUID(trace_run_id) if trace_run_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/replays/from-trace/{trace_run_id}")
def create_replay_from_trace(trace_run_id: str, body: dict | None = None):
    row = replay_service.create_static_replay_from_trace(uuid.UUID(trace_run_id), body)
    return ok(row) if row else err("NOT_FOUND", "Trace run not found")


@router.get("/replays/{replay_id}")
def get_replay(replay_id: str):
    row = replay_service.get_replay(uuid.UUID(replay_id))
    return ok(row) if row else err("NOT_FOUND", "Replay not found")


@router.post("/replays/{replay_id}/annotations")
def create_replay_annotation(replay_id: str, body: dict):
    row = replay_service.create_annotation(uuid.UUID(replay_id), body)
    return ok(row) if row else err("NOT_FOUND", "Replay not found")


@router.post("/replays/{replay_id}/bad-case")
def replay_to_bad_case(replay_id: str, body: dict | None = None):
    row = replay_service.replay_to_bad_case(uuid.UUID(replay_id), body)
    return ok(row) if row else err("NOT_FOUND", "Replay not found")


@router.post("/replays/{replay_id}/regression-case")
def replay_to_regression_case(replay_id: str, body: dict | None = None):
    row = replay_service.replay_to_regression_case(uuid.UUID(replay_id), body)
    return ok(row) if row else err("NOT_FOUND", "Replay not found")
