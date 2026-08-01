"""Short-lived local control sessions for the write-only configuration plane."""

from __future__ import annotations

import hmac
import ipaddress
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.core.config import settings


class LocalConfigurationSecurityError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _ControlSession:
    csrf_token: str
    client_host: str
    origin: str
    expires_at: datetime


_sessions: dict[str, _ControlSession] = {}
_lock = threading.Lock()
_ttl = timedelta(minutes=15)


def _allowed_origins() -> set[str]:
    return {value.strip().rstrip("/") for value in settings.CORS_ORIGINS.split(",") if value.strip()}


def _request_identity(request: Request) -> tuple[str, str]:
    host = request.client.host if request.client else ""
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError
    except ValueError as exc:
        raise LocalConfigurationSecurityError(
            "LOCAL_CONFIGURATION_LOOPBACK_REQUIRED",
            "Runtime configuration is available only from this device.",
        ) from exc
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin not in _allowed_origins():
        raise LocalConfigurationSecurityError(
            "LOCAL_CONFIGURATION_ORIGIN_REJECTED",
            "The request origin is not allowed to use runtime configuration.",
        )
    return host, origin


def create_control_session(request: Request) -> dict:
    host, origin = _request_identity(request)
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + _ttl
    with _lock:
        _prune_locked()
        _sessions[token] = _ControlSession(csrf, host, origin, expires_at)
    return {
        "session_token": token,
        "csrf_token": csrf,
        "expires_at": expires_at.isoformat(),
        "security_mode": "loopback_origin_session_csrf",
    }


def require_control_session(request: Request) -> None:
    host, origin = _request_identity(request)
    token = request.headers.get("x-echora-config-session") or ""
    csrf = request.headers.get("x-echora-csrf") or ""
    with _lock:
        _prune_locked()
        session = _sessions.get(token)
    if (
        session is None
        or not hmac.compare_digest(session.csrf_token, csrf)
        or session.client_host != host
        or session.origin != origin
    ):
        raise LocalConfigurationSecurityError(
            "LOCAL_CONFIGURATION_SESSION_INVALID",
            "The local configuration session is missing, expired, or invalid.",
        )


def _prune_locked() -> None:
    now = datetime.now(timezone.utc)
    expired = [token for token, session in _sessions.items() if session.expires_at <= now]
    for token in expired:
        _sessions.pop(token, None)
