"""Core error codes and unified error response."""

from typing import Any, Literal

from pydantic import BaseModel

# ── Common Error Codes ──────────────────────────────────────────────

CommonErrorCode = Literal[
    "BAD_REQUEST",
    "UNAUTHORIZED",
    "FORBIDDEN",
    "NOT_FOUND",
    "CONFLICT",
    "VALIDATION_ERROR",
    "RATE_LIMITED",
    "INTERNAL_ERROR",
    "NOT_IMPLEMENTED",
]

# ── Memory Error Codes (Companion/5 reserved) ─────────────────────────

MemoryErrorCode = Literal[
    "REALTIME_MEMORY_BUFFER_NOT_FOUND",
    "REALTIME_MEMORY_WRITE_BLOCKED",
    "REALTIME_MEMORY_CANDIDATE_REQUIRES_REVIEW",
    "AUTO_PERSISTENT_MEMORY_WRITE_BLOCKED",
    "MEMORY_SCOPE_VIOLATION",
    "CHARACTER_MEMORY_ISOLATED",
    "VIRTUAL_WORLD_MEMORY_ISOLATED",
]

ErrorCode = CommonErrorCode  # extend with unions as needed


class ApiError(BaseModel):
    """Unified API error object."""
    code: str
    message: str
    details: dict[str, Any] | None = None
