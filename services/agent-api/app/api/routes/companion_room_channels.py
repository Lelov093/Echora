"""Discord Guild/Channel directory and Room binding routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok
from app.schemas.companion_room import (
    DiscordChannelRoomBindRequest,
    DiscordChannelRoomTransitionRequest,
    DiscordGuildCreateRequest,
    DiscordTextChannelCreateRequest,
)
from app.services import companion_room_channel_service as service
from app.services import discord_room_service


router = APIRouter(prefix="/companion-room-channels", tags=["Companion Room Channels"])


def _run(operation):
    try:
        return ok(operation())
    except service.CompanionRoomChannelError as exc:
        return err(exc.code, exc.message, exc.details)


@router.get("/guilds")
def list_guilds(user_id: str | None = Query(None)):
    return _run(lambda: {"items": service.list_guilds(uuid.UUID(user_id) if user_id else None)})


@router.post("/guilds")
def create_guild(body: DiscordGuildCreateRequest):
    return _run(lambda: service.create_guild(body.model_dump(mode="json")))


@router.get("/channels")
def list_channels(guild_id: str | None = Query(None), user_id: str | None = Query(None)):
    return _run(lambda: {"items": service.list_channels(
        uuid.UUID(guild_id) if guild_id else None,
        uuid.UUID(user_id) if user_id else None,
    )})


@router.post("/guilds/{guild_id}/channels")
def create_channel(guild_id: str, body: DiscordTextChannelCreateRequest):
    return _run(lambda: service.create_channel(uuid.UUID(guild_id), body.model_dump(mode="json")))


@router.get("/bot-identities")
def list_bot_identities(user_id: str | None = Query(None)):
    return _run(lambda: {"items": service.list_available_bot_identities(uuid.UUID(user_id) if user_id else None)})


@router.post("/channels/{channel_id}/bind")
def bind_channel(channel_id: str, body: DiscordChannelRoomBindRequest):
    return _run(lambda: service.bind_channel_to_room(uuid.UUID(channel_id), body.model_dump(mode="json")))


@router.post("/bindings/{binding_id}/{action}")
def transition_binding(binding_id: str, action: str, body: DiscordChannelRoomTransitionRequest):
    return _run(lambda: service.transition_channel_binding(
        uuid.UUID(binding_id), action, body.expected_revision, body.reason
    ))


@router.get("/rooms/{room_id}/ingresses")
def list_room_ingresses(room_id: str, limit: int = Query(30, ge=1, le=100)):
    try:
        return ok({"items": discord_room_service.list_recent_ingresses(uuid.UUID(room_id), limit=limit)})
    except discord_room_service.DiscordRoomError as exc:
        return err(exc.code, exc.message, exc.details)
