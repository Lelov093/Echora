"""Presence Opportunity API routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import presence_service

router = APIRouter(prefix="/presence/opportunities", tags=["Presence"])


@router.get("")
def list_opportunities(companion_id: str | None = Query(None), status: str | None = Query(None),
                       type: str | None = Query(None, alias="type"),
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = presence_service.list_opportunities(
        uuid.UUID(companion_id) if companion_id else None, status, type, page, page_size,
    )
    items = [presence_service._opp_dict(o) for o in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.get("/{opportunity_id}")
def get_opportunity(opportunity_id: str):
    o = presence_service.get_opportunity(uuid.UUID(opportunity_id))
    if not o:
        return err("PRESENCE_OPPORTUNITY_NOT_FOUND", "Opportunity not found")
    return ok(presence_service._opp_dict(o))


@router.post("/{opportunity_id}/accept")
def accept_opportunity(opportunity_id: str, body: dict | None = None):
    conv_id = (body or {}).get("conversation_id")
    result = presence_service.accept_opportunity(
        uuid.UUID(opportunity_id), uuid.UUID(conv_id) if conv_id else None,
    )
    if not result:
        return err("PRESENCE_OPPORTUNITY_NOT_FOUND", "Opportunity not found")
    return ok(result)


@router.post("/{opportunity_id}/dismiss")
def dismiss_opportunity(opportunity_id: str):
    o = presence_service.dismiss_opportunity(uuid.UUID(opportunity_id))
    if not o:
        return err("PRESENCE_OPPORTUNITY_NOT_FOUND", "Opportunity not found")
    return ok(presence_service._opp_dict(o))


@router.post("/{opportunity_id}/snooze")
def snooze_opportunity(opportunity_id: str, body: dict | None = None):
    snooze_until_str = (body or {}).get("snoozed_until")
    snooze_until = datetime.fromisoformat(snooze_until_str) if snooze_until_str else datetime.now(timezone.utc)
    o = presence_service.snooze_opportunity(uuid.UUID(opportunity_id), snooze_until)
    if not o:
        return err("PRESENCE_OPPORTUNITY_NOT_FOUND", "Opportunity not found")
    return ok(presence_service._opp_dict(o))


@router.post("/{opportunity_id}/suppress-type")
def suppress_opportunity_type(opportunity_id: str):
    o = presence_service.suppress_opportunity_type(uuid.UUID(opportunity_id))
    if not o:
        return err("PRESENCE_OPPORTUNITY_NOT_FOUND", "Opportunity not found")
    return ok(presence_service._opp_dict(o))
