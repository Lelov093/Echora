"""Deferred realtime memory buffer contracts."""

import uuid

from fastapi import APIRouter

from app.schemas.common import err, ok
from app.services import (
    realtime_memory_buffer_service,
    realtime_salient_moment_service,
    realtime_shared_memory_candidate_service,
)

router = APIRouter(tags=["Realtime Memory"])


@router.post("/realtime-memory-buffers")
def create_realtime_memory_buffer(body: dict):
    user_id = uuid.UUID(body["user_id"]) if body.get("user_id") else None
    if user_id is None:
        return err("REALTIME_MEMORY_USER_REQUIRED", "user_id is required")
    data = realtime_memory_buffer_service.create_buffer(user_id, body or {})
    if not data:
        return err("REALTIME_MEMORY_BUFFER_CREATE_FAILED", "Unable to create realtime memory buffer")
    return ok(data)


@router.get("/realtime-memory-buffers/{buffer_id}")
def get_realtime_memory_buffer(buffer_id: str):
    data = realtime_memory_buffer_service.get_buffer_bundle(uuid.UUID(buffer_id))
    if not data:
        return err("REALTIME_MEMORY_BUFFER_NOT_FOUND", "Realtime memory buffer not found")
    return ok(data)


@router.post("/realtime-memory-buffers/{buffer_id}/items")
def append_realtime_memory_buffer_item(buffer_id: str, body: dict):
    data = realtime_memory_buffer_service.append_buffer_item(uuid.UUID(buffer_id), body or {})
    if not data:
        return err("REALTIME_MEMORY_BUFFER_NOT_FOUND", "Realtime memory buffer not found")
    return ok(data)


@router.post("/realtime-memory-buffers/{buffer_id}/expire-items")
def expire_realtime_memory_buffer_items(buffer_id: str):
    data = realtime_memory_buffer_service.expire_buffer_items(uuid.UUID(buffer_id))
    if not data:
        return err("REALTIME_MEMORY_BUFFER_NOT_FOUND", "Realtime memory buffer not found")
    return ok(data)


@router.post("/realtime-memory-buffers/{buffer_id}/memory-gate-trace")
def write_memory_gate_trace(buffer_id: str, body: dict):
    data = realtime_memory_buffer_service.write_memory_gate_trace(uuid.UUID(buffer_id), body or {})
    if not data:
        return err("REALTIME_MEMORY_GATE_TRACE_FAILED", "Unable to write realtime memory gate trace")
    return ok(data)


@router.post("/realtime-memory-buffer-items/{buffer_item_id}/salient-moment")
def detect_salient_moment(buffer_item_id: str, body: dict):
    data = realtime_salient_moment_service.detect_salient_moment(uuid.UUID(buffer_item_id), body or {})
    if not data:
        return err("REALTIME_SALIENT_MOMENT_FAILED", "Unable to create realtime salient moment")
    return ok(data)


@router.get("/realtime-salient-moments/{moment_id}")
def get_salient_moment(moment_id: str):
    data = realtime_salient_moment_service.get_salient_moment(uuid.UUID(moment_id))
    if not data:
        return err("REALTIME_SALIENT_MOMENT_NOT_FOUND", "Realtime salient moment not found")
    return ok(data)


@router.post("/realtime-salient-moments/{moment_id}/shared-memory-candidate")
def create_shared_episodic_memory_candidate(moment_id: str, body: dict):
    data = realtime_shared_memory_candidate_service.create_shared_episodic_memory_candidate(
        uuid.UUID(moment_id),
        body or {},
    )
    if not data:
        return err("REALTIME_SHARED_MEMORY_CANDIDATE_FAILED", "Unable to create realtime shared memory candidate")
    return ok(data)


@router.post("/realtime-shared-memory-candidates/{candidate_id}/decision")
def decide_realtime_shared_memory_candidate(candidate_id: str, body: dict):
    data = realtime_shared_memory_candidate_service.decide_realtime_memory_candidate(
        uuid.UUID(candidate_id), (body or {}).get("decision", "").lower()
    )
    if not data:
        return err("INVALID_REALTIME_MEMORY_REVIEW", "Candidate is unavailable or no longer pending review")
    return ok(data)
