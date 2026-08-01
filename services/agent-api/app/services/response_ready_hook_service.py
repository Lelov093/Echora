"""Request-local hook for durable consumers of a persisted assistant response."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator


logger = logging.getLogger(__name__)
ResponseReadyHook = Callable[[dict[str, Any]], None]
_response_ready_hook: ContextVar[ResponseReadyHook | None] = ContextVar(
    "response_ready_hook",
    default=None,
)


@contextmanager
def bind_response_ready_hook(hook: ResponseReadyHook | None) -> Iterator[None]:
    """Bind a callback only for the current synchronous Conversation turn."""
    token = _response_ready_hook.set(hook)
    try:
        yield
    finally:
        _response_ready_hook.reset(token)


def notify_response_ready(payload: dict[str, Any]) -> str:
    """Notify the bound consumer without making channel delivery break the Graph."""
    hook = _response_ready_hook.get()
    if hook is None:
        return "not_registered"
    try:
        hook(payload)
        return "dispatched"
    except Exception as exc:
        logger.warning(
            "Response-ready hook failed type=%s trace_run_id=%s",
            type(exc).__name__,
            payload.get("trace_run_id"),
        )
        return "dispatch_failed"
