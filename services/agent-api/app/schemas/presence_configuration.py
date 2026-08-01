"""Single-write product contract for Companion Presence configuration."""

from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PresenceQuietHoursInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    start: str = Field(default="23:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(default="08:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def validate_window(self):
        if self.enabled and self.start == self.end:
            raise ValueError("quiet hours must span a non-zero window")
        return self


class PresenceConfigurationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_schedule_revision: int | None = Field(default=None, ge=1)
    expected_policy_updated_at: datetime | None = None
    expected_persona_updated_at: datetime
    expected_boundary_updated_at: datetime

    enabled: bool = False
    proactive_level: Literal["low", "medium", "high"] = "medium"
    presence_style: Literal["quiet", "balanced", "expressive"] = "balanced"
    notification_surface: Literal["hub_queue_only", "allow_light_notification", "disabled"] = "hub_queue_only"
    meaningful_silence_enabled: bool = True
    quiet_hours: PresenceQuietHoursInput = Field(default_factory=PresenceQuietHoursInput)
    max_presence_per_day: int = Field(default=3, ge=0, le=100)

    destination_mode: Literal["bound_conversation", "new_conversation_per_delivery"] = "bound_conversation"
    bound_conversation_id: uuid.UUID | None = None
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)), min_length=1, max_length=7)
    timing_mode: Literal["fixed", "random_window"] = "fixed"
    fixed_minute_of_day: int = Field(default=1200, ge=0, le=1439)
    window_start_minute: int = Field(default=1140, ge=0, le=1439)
    window_end_minute: int = Field(default=1320, ge=0, le=1439)
    cadence_mode: Literal["fixed", "random_interval"] = "fixed"
    fixed_interval_minutes: int = Field(default=1440, ge=60, le=525600)
    random_interval_min_minutes: int = Field(default=1440, ge=60, le=525600)
    random_interval_max_minutes: int = Field(default=4320, ge=60, le=525600)

    @model_validator(mode="after")
    def validate_configuration(self):
        if len(set(self.weekdays)) != len(self.weekdays) or any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("weekdays must contain unique values from 0 to 6")
        if self.enabled and self.destination_mode == "bound_conversation" and self.bound_conversation_id is None:
            raise ValueError("bound_conversation_id is required before enabling proactive greetings")
        if self.random_interval_max_minutes < self.random_interval_min_minutes:
            raise ValueError("random interval maximum must be greater than or equal to minimum")
        if self.timing_mode == "random_window" and self.window_start_minute == self.window_end_minute:
            raise ValueError("random delivery window must span at least one minute")
        return self
