"""Health / System API routes."""

import os
import uuid
from fastapi import APIRouter, Query
from sqlalchemy import text

from app.core.config import settings
from app.schemas.common import ok, err
from app.services import companion_service

router = APIRouter(tags=["System"])


@router.get("/health")
def health_check():
    return ok(
        {
            "status": "ok",
            "service": "echora-agent-api",
            "version": "0.1.0",
            "capability_probe": os.getenv("E2E_CAPABILITY_PROBE"),
            "capability_version": "echora-local-v1",
        }
    )


@router.get("/health/db")
def db_health_check():
    session = None
    try:
        session = companion_service.get_session()
        session.execute(text("SELECT 1"))
        return ok({"status": "ok", "database": "connected"})
    except Exception as e:
        return err("DATABASE_ERROR", str(e))
    finally:
        if session is not None:
            session.close()


@router.get("/system/env")
def system_env():
    return ok({
        "env": settings.APP_ENV,
        "backend_port": settings.BACKEND_PORT,
        "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
        "database_configured": bool(settings.DATABASE_URL),
        "project_root_exists": settings.PROJECT_ROOT.exists(),
    })
