"""Product-facing Companion room application contracts."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CompanionRoomParticipantCreate(BaseModel):
    companion_id: uuid.UUID
    role: Literal["active_companion", "observing_companion"] = "active_companion"


class CompanionRoomCreateRequest(BaseModel):
    primary_companion_id: uuid.UUID
    title: str = Field(min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=1000)
    participants: list[CompanionRoomParticipantCreate] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_participants(self):
        ids = [item.companion_id for item in self.participants]
        if self.primary_companion_id in ids:
            raise ValueError("primary Companion must not be repeated in participants")
        if len(ids) != len(set(ids)):
            raise ValueError("Companion room participants must be unique")
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("Companion room title must not be blank")
        return self


class CompanionRoomUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("at least one room field must be provided")
        if self.title is not None:
            self.title = self.title.strip()
            if not self.title:
                raise ValueError("Companion room title must not be blank")
        return self


class CompanionRoomMemberInviteRequest(BaseModel):
    companion_id: uuid.UUID
    mode: Literal["speaker", "observer"] = "speaker"
    expected_roster_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


class CompanionRoomMemberActionRequest(BaseModel):
    action: Literal["speaker", "observer", "mute", "inactivate", "reactivate", "revoke"]
    expected_roster_revision: int = Field(ge=1)
    expected_participant_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


class CompanionRoomRestoreRequest(BaseModel):
    expected_roster_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


class CompanionRoomTurnRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    target_companion_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)
    idempotency_key: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_targets(self):
        if len(self.target_companion_ids) != len(set(self.target_companion_ids)):
            raise ValueError("target Companion IDs must be unique")
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("Room turn content must not be blank")
        return self


class CompanionRoomSuccessorRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=1000)
    continuation_summary: str = Field(min_length=1, max_length=2000)
    confirm_reviewed: Literal[True]
    expected_roster_revision: int = Field(ge=1)

    @model_validator(mode="after")
    def normalize_text(self):
        self.title = self.title.strip()
        self.continuation_summary = self.continuation_summary.strip()
        if not self.title or not self.continuation_summary:
            raise ValueError("successor Room title and reviewed continuation must not be blank")
        return self


class DiscordGuildCreateRequest(BaseModel):
    user_id: uuid.UUID
    provider_guild_ref: str = Field(min_length=1, max_length=100)
    guild_display_name: str = Field(min_length=1, max_length=120)


class DiscordTextChannelCreateRequest(BaseModel):
    provider_channel_ref: str = Field(min_length=1, max_length=100)
    channel_display_name: str = Field(min_length=1, max_length=120)
    permission_status: Literal["unverified", "ready", "blocked"] = "unverified"


class DiscordChannelRoomBindRequest(BaseModel):
    room_id: uuid.UUID
    provider_bot_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    expected_channel_revision: int = Field(ge=1)
    expected_room_roster_revision: int = Field(ge=1)
    mention_policy: Literal["mention_only", "coordinator_managed", "observe_only"] = "mention_only"

    @model_validator(mode="after")
    def validate_bots(self):
        if len(self.provider_bot_ids) != len(set(self.provider_bot_ids)):
            raise ValueError("provider Bot identities must be unique")
        return self


class DiscordChannelRoomTransitionRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)
