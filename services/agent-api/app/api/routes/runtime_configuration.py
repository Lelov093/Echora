"""Trusted loopback runtime configuration control plane."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.schemas.common import err, ok
from app.services import local_configuration_security_service as security
from app.services import runtime_configuration_service as configuration

router = APIRouter(prefix="/runtime-configuration", tags=["Runtime Configuration"])


def _failure(exc: Exception) -> JSONResponse:
    if isinstance(exc, security.LocalConfigurationSecurityError):
        return JSONResponse(status_code=403, content=err(exc.code, str(exc)))
    if isinstance(exc, configuration.RuntimeConfigurationError):
        status = 409 if exc.code == "RUNTIME_CONFIGURATION_REVISION_CONFLICT" else 422
        return JSONResponse(status_code=status, content=err(exc.code, str(exc), exc.details))
    return JSONResponse(status_code=500, content=err("RUNTIME_CONFIGURATION_FAILED", "Runtime configuration failed safely."))


@router.post("/session")
def create_session(request: Request):
    try:
        return ok(security.create_control_session(request))
    except Exception as exc:
        return _failure(exc)


@router.get("")
def get_configuration(request: Request):
    try:
        security.require_control_session(request)
        return ok(configuration.read_configuration())
    except Exception as exc:
        return _failure(exc)


@router.put("")
def put_configuration(request: Request, body: dict):
    try:
        security.require_control_session(request)
        return ok(configuration.update_configuration(body or {}))
    except Exception as exc:
        return _failure(exc)


@router.post("/test")
def test_connection(request: Request, body: dict):
    try:
        security.require_control_session(request)
        return ok(configuration.test_connection(str(body.get("target") or ""), body.get("bot_key")))
    except Exception as exc:
        return _failure(exc)
