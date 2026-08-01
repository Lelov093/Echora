"""Realtime compatibility realtime channel event and SSE service."""

import json
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import (
    RealtimeChannelStateEvent,
    RealtimeCoPresenceSession,
    RealtimeSessionChannel,
    RealtimeSessionStateEvent,
)
from app.services.realtime_copresence_service import get_session

PUBLISHED_EVENT_TYPES = {
    "session.started",
    "session.paused",
    "session.resumed",
    "session.ended",
    "participant.updated",
    "channel.updated",
    "transcript.partial",
    "transcript.final",
    "response.delta",
    "permission.requested",
    "permission.changed",
    "hard_stop.triggered",
}

SESSION_EVENT_TYPES = {
    "session.started",
    "session.paused",
    "session.resumed",
    "session.ended",
    "participant.updated",
    "permission.changed",
    "hard_stop.triggered",
}

CHANNEL_DIRECT_EVENT_TYPES = {
    "channel.created",
    "channel.opened",
    "channel.paused",
    "channel.resumed",
    "channel.closed",
    "channel.failed",
    "permission.changed",
    "hard_stop.triggered",
}


def publish_channel_event(channel_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    event_type = str(payload.get("event_type") or "").strip()
    if event_type not in PUBLISHED_EVENT_TYPES:
        return None

    with get_session() as s:
        channel = s.get(RealtimeSessionChannel, channel_id)
        if channel is None:
            return None
        session = s.get(RealtimeCoPresenceSession, channel.realtime_session_id)
        if session is None:
            return None

        now = _now()
        event_payload = {
            "event_type": event_type,
            "payload": payload.get("payload") or {},
            "preview": payload.get("preview"),
        }
        direct_channel_event_type = _channel_event_type_for_publish(event_type)
        previous_channel_status = channel.channel_status
        previous_session_status = session.session_status

        if event_type == "hard_stop.triggered":
            channel.channel_status = "closed"
            channel.can_send_events = False
            channel.can_receive_actions = False
            channel.closed_at = now
            session.session_status = "ended"
            session.ended_at = now
        elif event_type == "session.started" and session.session_status == "created":
            session.session_status = "active"
        elif event_type == "session.paused":
            session.session_status = "paused"
            session.paused_at = now
        elif event_type == "session.resumed":
            session.session_status = "active"
            session.paused_at = None
        elif event_type == "session.ended":
            session.session_status = "ended"
            session.ended_at = now

        channel.last_event_at = now
        session.last_event_at = now

        channel_event = RealtimeChannelStateEvent(
            user_id=channel.user_id,
            realtime_session_id=channel.realtime_session_id,
            channel_id=channel.id,
            actor_participant_id=_to_uuid(payload.get("actor_participant_id")),
            event_type=direct_channel_event_type,
            event_status="recorded",
            previous_status=previous_channel_status,
            next_status=channel.channel_status,
            event_payload_json=event_payload,
            permission_snapshot_json=channel.permission_snapshot_json or {},
            occurred_at=now,
            metadata_={"implementation_origin": "realtime_channel", "published_event_type": event_type},
        )
        s.add(channel_event)

        session_event = None
        if event_type in SESSION_EVENT_TYPES:
            session_event = RealtimeSessionStateEvent(
                user_id=session.user_id,
                realtime_session_id=session.id,
                actor_participant_id=_to_uuid(payload.get("actor_participant_id")),
                event_type=event_type,
                event_status="recorded",
                previous_status=previous_session_status,
                next_status=session.session_status,
                event_payload_json=event_payload,
                permission_snapshot_json=session.permission_snapshot_json or {},
                occurred_at=now,
                metadata_={"implementation_origin": "realtime_channel", "source_channel_id": str(channel.id)},
            )
            s.add(session_event)

        s.commit()
        s.refresh(channel_event)
        if session_event is not None:
            s.refresh(session_event)
        return _stream_event_to_dict(_channel_event_to_stream(channel_event))


def list_recent_channel_events(
    channel_id: uuid.UUID,
    *,
    last_event_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]] | None:
    with get_session() as s:
        channel = s.get(RealtimeSessionChannel, channel_id)
        if channel is None:
            return None
        events = _load_stream_events(s, channel, max(limit, 1))
        events = _filter_after_last_event(events, last_event_id)
        return [_stream_event_to_dict(item) for item in events[:limit]]


def iter_sse_events(
    channel_id: uuid.UUID,
    *,
    last_event_id: str | None = None,
    max_events: int = 50,
) -> Iterator[str]:
    events = list_recent_channel_events(channel_id, last_event_id=last_event_id, limit=max(max_events, 1))
    if events is None:
        yield _format_sse_event(
            {
                "id": f"missing:{channel_id}",
                "event": "channel.missing",
                "data": {"channel_id": str(channel_id), "status": "missing"},
            }
        )
        return

    yielded = 0
    for event in events:
        yield _format_sse_event(event)
        yielded += 1
        if yielded >= max_events:
            return
    if yielded == 0:
        yield _format_sse_event(
            {
                "id": f"heartbeat:{channel_id}",
                "event": "heartbeat",
                "data": {"channel_id": str(channel_id), "status": "idle", "occurred_at": _now().isoformat()},
            }
        )


def _load_stream_events(s, channel: RealtimeSessionChannel, limit: int) -> list[dict[str, Any]]:
    session_events = list(
        s.execute(
            select(RealtimeSessionStateEvent)
            .where(RealtimeSessionStateEvent.realtime_session_id == channel.realtime_session_id)
            .order_by(RealtimeSessionStateEvent.occurred_at.desc(), RealtimeSessionStateEvent.created_at.desc())
            .limit(limit)
        ).scalars().all()
    )
    channel_events = list(
        s.execute(
            select(RealtimeChannelStateEvent)
            .where(RealtimeChannelStateEvent.channel_id == channel.id)
            .order_by(RealtimeChannelStateEvent.occurred_at.desc(), RealtimeChannelStateEvent.created_at.desc())
            .limit(limit)
        ).scalars().all()
    )
    events = [_session_event_to_stream(item, channel.id) for item in session_events]
    events.extend(_channel_event_to_stream(item) for item in channel_events)
    return sorted(events, key=lambda item: (item["occurred_at"] or "", item["id"]))


def _filter_after_last_event(events: list[dict[str, Any]], last_event_id: str | None) -> list[dict[str, Any]]:
    if not last_event_id:
        return events
    for index, event in enumerate(events):
        if event["id"] == last_event_id:
            return events[index + 1 :]
    return events


def _session_event_to_stream(event: RealtimeSessionStateEvent, channel_id: uuid.UUID) -> dict[str, Any]:
    return {
        "id": f"session:{event.id}",
        "event": event.event_type,
        "source": "session",
        "channel_id": str(channel_id),
        "realtime_session_id": str(event.realtime_session_id),
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "payload": event.event_payload_json or {},
    }


def _channel_event_to_stream(event: RealtimeChannelStateEvent) -> dict[str, Any]:
    payload = event.event_payload_json or {}
    published_event_type = payload.get("event_type")
    return {
        "id": f"channel:{event.id}",
        "event": published_event_type or event.event_type,
        "source": "channel",
        "channel_id": str(event.channel_id),
        "realtime_session_id": str(event.realtime_session_id),
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "payload": payload,
    }


def _stream_event_to_dict(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event["id"],
        "event": event["event"],
        "source": event["source"],
        "channel_id": event["channel_id"],
        "realtime_session_id": event["realtime_session_id"],
        "occurred_at": event["occurred_at"],
        "payload": event["payload"],
    }


def _format_sse_event(event: dict[str, Any]) -> str:
    data = event.get("data") or _stream_event_to_dict(event)
    return "\n".join(
        [
            f"id: {event['id']}",
            f"event: {event['event']}",
            f"data: {json.dumps(data, ensure_ascii=True, default=str)}",
            "",
            "",
        ]
    )


def _channel_event_type_for_publish(event_type: str) -> str:
    if event_type in CHANNEL_DIRECT_EVENT_TYPES:
        return event_type
    return "event.published"


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)
