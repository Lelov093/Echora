"""Trace API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import trace_service

router = APIRouter(tags=["Traces"])


@router.get("/traces")
def list_traces(companion_id: str | None = Query(None), conversation_id: str | None = Query(None),
                page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = trace_service.list_traces(
        uuid.UUID(companion_id) if companion_id else None,
        uuid.UUID(conversation_id) if conversation_id else None,
        page, page_size,
    )
    items = [trace_service._tr_dict(t) for t in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.get("/traces/{trace_run_id}")
def get_trace_detail(trace_run_id: str):
    detail = trace_service.get_trace_detail(uuid.UUID(trace_run_id))
    if not detail:
        return err("TRACE_NOT_FOUND", "Trace run not found")
    return ok(detail)


@router.get("/traces/{trace_run_id}/signals")
@router.get("/traces/{trace_run_id}/v3", include_in_schema=False, deprecated=True)
def get_execution_signals_detail(trace_run_id: str):
    detail = trace_service.get_trace_detail(uuid.UUID(trace_run_id))
    if not detail:
        return err("TRACE_NOT_FOUND", "Trace run not found")
    return ok(detail["execution_signals"])


@router.get("/traces/{trace_run_id}/companion-context")
@router.get("/traces/{trace_run_id}/v4", include_in_schema=False, deprecated=True)
def get_companion_context_detail(trace_run_id: str):
    detail = trace_service.get_trace_detail(uuid.UUID(trace_run_id))
    if not detail:
        return err("TRACE_NOT_FOUND", "Trace run not found")
    return ok(detail["companion_context"])


@router.get("/traces/{trace_run_id}/realtime")
def get_realtime_trace_detail(trace_run_id: str):
    detail = trace_service.get_realtime_trace_detail(uuid.UUID(trace_run_id))
    if not detail:
        return err("TRACE_NOT_FOUND", "Trace run not found")
    return ok(detail)


@router.get("/conversations/{conversation_id}/traces")
def list_conversation_traces(conversation_id: str, page: int = Query(1, ge=1),
                             page_size: int = Query(20, ge=1, le=100)):
    result = trace_service.list_conversation_traces(uuid.UUID(conversation_id), page, page_size)
    items = [trace_service._tr_dict(t) for t in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])
