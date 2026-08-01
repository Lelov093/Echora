"""Project Context & Creative Context API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import context_service

router = APIRouter(tags=["Contexts"])


def _get_seed_ids():
    from app.db.models import User, Companion
    s = context_service.get_session()
    u = s.query(User).first()
    c = s.query(Companion).first()
    s.close()
    return (u.id if u else uuid.uuid4(), c.id if c else uuid.uuid4())


# ── Project Context ──────────────────────────────────────────────────

@router.get("/project-contexts")
def list_project_contexts(companion_id: str | None = Query(None),
                          page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = context_service.list_project_contexts(
        uuid.UUID(companion_id) if companion_id else None, page, page_size,
    )
    items = [_pc_dict(pc) for pc in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/project-contexts")
def create_project_context(body: dict):
    uid, cid = _get_seed_ids()
    body.setdefault("user_id", uid)
    body.setdefault("companion_id", cid)
    ctx = context_service.create_project_context(body)
    return ok(_pc_dict(ctx))


@router.get("/project-contexts/{context_id}")
def get_project_context(context_id: str):
    ctx = context_service.get_project_context(uuid.UUID(context_id))
    if not ctx:
        return err("NOT_FOUND", "Project context not found")
    return ok(_pc_dict(ctx))


@router.patch("/project-contexts/{context_id}")
def update_project_context(context_id: str, body: dict):
    ctx = context_service.update_project_context(uuid.UUID(context_id), body)
    if not ctx:
        return err("NOT_FOUND", "Project context not found")
    return ok(_pc_dict(ctx))


# ── Creative Context ─────────────────────────────────────────────────

@router.get("/creative-contexts")
def list_creative_contexts(companion_id: str | None = Query(None),
                           page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = context_service.list_creative_contexts(
        uuid.UUID(companion_id) if companion_id else None, page, page_size,
    )
    items = [_cc_dict(cc) for cc in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/creative-contexts")
def create_creative_context(body: dict):
    uid, cid = _get_seed_ids()
    body.setdefault("user_id", uid)
    body.setdefault("companion_id", cid)
    ctx = context_service.create_creative_context(body)
    return ok(_cc_dict(ctx))


@router.get("/creative-contexts/{context_id}")
def get_creative_context(context_id: str):
    ctx = context_service.get_creative_context(uuid.UUID(context_id))
    if not ctx:
        return err("NOT_FOUND", "Creative context not found")
    return ok(_cc_dict(ctx))


@router.patch("/creative-contexts/{context_id}")
def update_creative_context(context_id: str, body: dict):
    ctx = context_service.update_creative_context(uuid.UUID(context_id), body)
    if not ctx:
        return err("NOT_FOUND", "Creative context not found")
    return ok(_cc_dict(ctx))


# ── Serialization ────────────────────────────────────────────────────

def _pc_dict(ctx) -> dict:
    return {
        "id": str(ctx.id), "name": ctx.name, "description": ctx.description,
        "current_phase": ctx.current_phase, "current_goal": ctx.current_goal,
        "principles": ctx.principles, "constraints": ctx.constraints,
        "next_steps": ctx.next_steps, "is_active": ctx.is_active,
        "created_at": ctx.created_at.isoformat() if ctx.created_at else None,
    }


def _cc_dict(ctx) -> dict:
    return {
        "id": str(ctx.id), "name": ctx.name, "description": ctx.description,
        "creative_domain": ctx.creative_domain,
        "tone_preferences": ctx.tone_preferences, "style_preferences": ctx.style_preferences,
        "is_active": ctx.is_active,
        "created_at": ctx.created_at.isoformat() if ctx.created_at else None,
    }
