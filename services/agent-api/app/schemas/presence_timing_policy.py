"""Requests for Companion Presence timing policy changes."""

from typing import Literal

from pydantic import BaseModel


PresencePolicySurface = Literal["queue", "hub"]


class PresenceTimingPolicyUpdateRequest(BaseModel):
    surface: PresencePolicySurface
    enabled: bool
    expected_revision: int


class PresenceTimingPolicyRollbackRequest(BaseModel):
    surface: PresencePolicySurface
    expected_revision: int
