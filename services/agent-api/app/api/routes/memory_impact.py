"""Memory Impact API routes."""

import uuid

from fastapi import APIRouter

from app.schemas.common import ok, err
from app.services import memory_impact_service

router = APIRouter(tags=["Memory Impact"])


@router.get("/memories/{memory_id}/impact")
def get_memory_impact(memory_id: str):
    result = memory_impact_service.get_memory_impact(uuid.UUID(memory_id))
    if result is None:
        return err("NOT_FOUND", "Memory not found")
    return ok(result)
