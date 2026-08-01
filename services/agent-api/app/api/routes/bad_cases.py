"""Bad Case API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import bad_case_service

router = APIRouter(tags=["Bad Cases"])


def _get_seed_ids():
    from app.db.models import User, Companion
    s = bad_case_service.get_session()
    u = s.query(User).first()
    c = s.query(Companion).first()
    s.close()
    return (u.id if u else uuid.uuid4(), c.id if c else uuid.uuid4())


@router.get("/bad-cases")
def list_bad_cases(companion_id: str | None = Query(None), type: str | None = Query(None),
                   status: str | None = Query(None), page: int = Query(1, ge=1),
                   page_size: int = Query(20, ge=1, le=100)):
    result = bad_case_service.list_bad_cases(
        uuid.UUID(companion_id) if companion_id else None, type, status, page, page_size,
    )
    items = [bad_case_service._bc_dict(bc) for bc in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/bad-cases")
def create_bad_case(body: dict):
    uid, cid = _get_seed_ids()
    body.setdefault("user_id", uid)
    body.setdefault("companion_id", cid)
    bc = bad_case_service.create_bad_case(body)
    return ok(bad_case_service._bc_dict(bc))


@router.patch("/bad-cases/{bad_case_id}")
def update_bad_case(bad_case_id: str, body: dict):
    bc = bad_case_service.update_bad_case(uuid.UUID(bad_case_id), body)
    if not bc:
        return err("NOT_FOUND", "Bad case not found")
    return ok(bad_case_service._bc_dict(bc))
