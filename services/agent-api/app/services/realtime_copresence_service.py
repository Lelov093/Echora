"""Realtime compatibility realtime co-presence REST resource service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CoPresenceParticipant,
    CoPresenceSession,
    Companion,
    RealtimeChannelStateEvent,
    RealtimeCoPresenceParticipant,
    RealtimeCoPresenceSession,
    RealtimeParticipantState,
    RealtimeSessionChannel,
    RealtimeSessionStateEvent,
    User,
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_realtime_sessions(
    *,
    user_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(RealtimeCoPresenceSession)
        if user_id is not None:
            stmt = stmt.where(RealtimeCoPresenceSession.user_id == user_id)
        if status:
            stmt = stmt.where(RealtimeCoPresenceSession.session_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(RealtimeCoPresenceSession.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def create_realtime_session(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        user = s.get(User, user_id)
        if user is None:
            return None

        co_presence_id = _to_uuid(payload.get("co_presence_session_id"))
        co_presence = s.get(CoPresenceSession, co_presence_id) if co_presence_id else None
        active_companion_id = _to_uuid(payload.get("active_companion_id"))
        if active_companion_id is None and co_presence is not None:
            active_companion_id = co_presence.primary_companion_id
        active_companion = s.get(Companion, active_companion_id) if active_companion_id else None
        if co_presence is None and active_companion is None:
            return None

        session = RealtimeCoPresenceSession(
            user_id=user_id,
            co_presence_session_id=co_presence.id if co_presence else None,
            active_companion_id=active_companion.id if active_companion else None,
            originating_conversation_id=_to_uuid(payload.get("originating_conversation_id")),
            shared_scene_id=_to_uuid(payload.get("shared_scene_id")),
            session_title=payload.get("session_title") or _default_session_title(active_companion),
            session_status=payload.get("session_status", "created"),
            session_source=payload.get("session_source", "conversation"),
            default_transport="sse",
            permission_snapshot_json=payload.get("permission_snapshot_json") or {},
            participant_summary_json={},
            boundary_snapshot_json=payload.get("boundary_snapshot_json") or {},
            runtime_state_json=payload.get("runtime_state_json") or {},
            started_at=_now(),
            last_event_at=_now(),
            metadata_={"implementation_origin": "realtime_copresence", **(payload.get("metadata") or {})},
        )
        s.add(session)
        s.flush()

        channel = RealtimeSessionChannel(
            user_id=user_id,
            realtime_session_id=session.id,
            channel_type="sse",
            channel_status="active",
            transport_type="sse",
            is_default_event_stream=True,
            can_send_events=True,
            can_receive_actions=False,
            permission_snapshot_json=session.permission_snapshot_json,
            runtime_state_json={},
            opened_at=_now(),
            last_event_at=_now(),
            metadata_={"implementation_origin": "realtime_copresence", "bootstrap": "default_sse_channel"},
        )
        s.add(channel)

        if payload.get("bootstrap_active_participant", True) and active_companion is not None:
            participant = _build_realtime_participant(
                user_id=user_id,
                realtime_session_id=session.id,
                payload={
                    "participant_type": "companion",
                    "participant_role": "speaker_companion",
                    "participant_companion_id": str(active_companion.id),
                    "can_listen": True,
                    "can_speak": True,
                    "can_observe": True,
                    "can_remember": False,
                    "can_receive_transcript": False,
                },
            )
            s.add(participant)
            s.flush()
            _record_participant_state(s, participant)

        _refresh_session_summary(s, session)
        s.commit()
        return get_realtime_session_bundle(session.id)


def get_realtime_session_bundle(realtime_session_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        session = s.get(RealtimeCoPresenceSession, realtime_session_id)
        if session is None:
            return None
        participants = list(
            s.execute(
                select(RealtimeCoPresenceParticipant)
                .where(RealtimeCoPresenceParticipant.realtime_session_id == session.id)
                .order_by(RealtimeCoPresenceParticipant.joined_at.asc(), RealtimeCoPresenceParticipant.created_at.asc())
            ).scalars().all()
        )
        channels = list(
            s.execute(
                select(RealtimeSessionChannel)
                .where(RealtimeSessionChannel.realtime_session_id == session.id)
                .order_by(RealtimeSessionChannel.opened_at.asc(), RealtimeSessionChannel.created_at.asc())
            ).scalars().all()
        )
        state_events = list(
            s.execute(
                select(RealtimeSessionStateEvent)
                .where(RealtimeSessionStateEvent.realtime_session_id == session.id)
                .order_by(RealtimeSessionStateEvent.occurred_at.desc())
                .limit(20)
            ).scalars().all()
        )
        return {
            **_session_to_dict(session),
            "participants": [_participant_to_dict(item) for item in participants],
            "channels": [_channel_to_dict(item) for item in channels],
            "recent_state_events": [_session_event_to_dict(item) for item in state_events],
        }


def transition_realtime_session(realtime_session_id: uuid.UUID, action: str) -> dict[str, Any] | None:
    next_status_by_action = {"pause": "paused", "resume": "active", "end": "ended"}
    event_type_by_action = {"pause": "session.paused", "resume": "session.resumed", "end": "session.ended"}
    if action not in next_status_by_action:
        return None
    with get_session() as s:
        session = s.get(RealtimeCoPresenceSession, realtime_session_id)
        if session is None:
            return None
        previous_status = session.session_status
        next_status = next_status_by_action[action]
        now = _now()
        session.session_status = next_status
        session.last_event_at = now
        if action == "pause":
            session.paused_at = now
        elif action == "resume":
            session.paused_at = None
        elif action == "end":
            session.ended_at = now
            _close_channels(s, session.id, now)
            _leave_participants(s, session.id, now)
        event = RealtimeSessionStateEvent(
            user_id=session.user_id,
            realtime_session_id=session.id,
            event_type=event_type_by_action[action],
            event_status="recorded",
            previous_status=previous_status,
            next_status=next_status,
            event_payload_json={"action": action},
            permission_snapshot_json=session.permission_snapshot_json or {},
            occurred_at=now,
            metadata_={"implementation_origin": "realtime_copresence"},
        )
        s.add(event)
        _refresh_session_summary(s, session)
        s.commit()
        return get_realtime_session_bundle(session.id)


def add_participant(realtime_session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        session = s.get(RealtimeCoPresenceSession, realtime_session_id)
        if session is None:
            return None
        participant = _build_realtime_participant(
            user_id=session.user_id,
            realtime_session_id=session.id,
            payload=payload,
        )
        s.add(participant)
        s.flush()
        _record_participant_state(s, participant)
        _refresh_session_summary(s, session)
        s.commit()
        return get_realtime_session_bundle(session.id)


def patch_participant(
    realtime_session_id: uuid.UUID,
    participant_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    with get_session() as s:
        session = s.get(RealtimeCoPresenceSession, realtime_session_id)
        participant = s.get(RealtimeCoPresenceParticipant, participant_id)
        if session is None or participant is None or participant.realtime_session_id != session.id:
            return None
        previous_status = participant.participant_status
        for field in [
            "participant_role",
            "participant_status",
            "can_listen",
            "can_speak",
            "can_observe",
            "can_remember",
            "can_receive_transcript",
        ]:
            if field in payload and payload[field] is not None:
                setattr(participant, field, payload[field])
        if payload.get("left_at"):
            participant.left_at = _to_datetime(payload["left_at"])
        if "permission_snapshot_json" in payload and payload["permission_snapshot_json"] is not None:
            participant.permission_snapshot_json = payload["permission_snapshot_json"]
        if "runtime_state_json" in payload and payload["runtime_state_json"] is not None:
            participant.runtime_state_json = payload["runtime_state_json"]
        _enforce_observer_boundary(participant)
        participant.updated_at = _now()
        _record_participant_state(s, participant)
        if previous_status != participant.participant_status:
            s.add(
                RealtimeSessionStateEvent(
                    user_id=session.user_id,
                    realtime_session_id=session.id,
                    actor_participant_id=participant.id,
                    event_type="participant.updated",
                    event_status="recorded",
                    previous_status=previous_status,
                    next_status=participant.participant_status,
                    event_payload_json={"participant_id": str(participant.id)},
                    permission_snapshot_json=participant.permission_snapshot_json or {},
                    occurred_at=_now(),
                    metadata_={"implementation_origin": "realtime_copresence"},
                )
            )
        _refresh_session_summary(s, session)
        s.commit()
        return get_realtime_session_bundle(session.id)


def list_channels(realtime_session_id: uuid.UUID) -> list[dict[str, Any]] | None:
    with get_session() as s:
        session = s.get(RealtimeCoPresenceSession, realtime_session_id)
        if session is None:
            return None
        channels = list(
            s.execute(
                select(RealtimeSessionChannel)
                .where(RealtimeSessionChannel.realtime_session_id == session.id)
                .order_by(RealtimeSessionChannel.created_at.asc())
            ).scalars().all()
        )
        return [_channel_to_dict(item) for item in channels]


def patch_channel(realtime_session_id: uuid.UUID, channel_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        session = s.get(RealtimeCoPresenceSession, realtime_session_id)
        channel = s.get(RealtimeSessionChannel, channel_id)
        if session is None or channel is None or channel.realtime_session_id != session.id:
            return None
        previous_status = channel.channel_status
        for field in ["channel_status", "can_send_events", "can_receive_actions"]:
            if field in payload and payload[field] is not None:
                setattr(channel, field, payload[field])
        if payload.get("closed_at"):
            channel.closed_at = _to_datetime(payload["closed_at"])
        if "runtime_state_json" in payload and payload["runtime_state_json"] is not None:
            channel.runtime_state_json = payload["runtime_state_json"]
        channel.last_event_at = _now()
        s.add(
            RealtimeChannelStateEvent(
                user_id=session.user_id,
                realtime_session_id=session.id,
                channel_id=channel.id,
                event_type=_channel_event_type(channel.channel_status),
                event_status="recorded",
                previous_status=previous_status,
                next_status=channel.channel_status,
                event_payload_json={"channel_id": str(channel.id)},
                permission_snapshot_json=channel.permission_snapshot_json or {},
                occurred_at=_now(),
                metadata_={"implementation_origin": "realtime_copresence"},
            )
        )
        s.commit()
        return _channel_to_dict(channel)


def _build_realtime_participant(
    *,
    user_id: uuid.UUID,
    realtime_session_id: uuid.UUID,
    payload: dict[str, Any],
) -> RealtimeCoPresenceParticipant:
    participant = RealtimeCoPresenceParticipant(
        user_id=user_id,
        realtime_session_id=realtime_session_id,
        co_presence_participant_id=_to_uuid(payload.get("co_presence_participant_id")),
        participant_type=payload["participant_type"],
        participant_role=payload.get("participant_role", "listener_companion"),
        participant_status=payload.get("participant_status", "active"),
        participant_user_id=_to_uuid(payload.get("participant_user_id")),
        participant_companion_id=_to_uuid(payload.get("participant_companion_id")),
        external_agent_label=payload.get("external_agent_label"),
        can_listen=bool(payload.get("can_listen", False)),
        can_speak=bool(payload.get("can_speak", False)),
        can_observe=bool(payload.get("can_observe", True)),
        can_remember=bool(payload.get("can_remember", False)),
        can_receive_transcript=bool(payload.get("can_receive_transcript", False)),
        permission_snapshot_json=payload.get("permission_snapshot_json") or {},
        runtime_state_json=payload.get("runtime_state_json") or {},
        joined_at=_now(),
        metadata_={"implementation_origin": "realtime_copresence"},
    )
    _enforce_observer_boundary(participant)
    return participant


def _enforce_observer_boundary(participant: RealtimeCoPresenceParticipant) -> None:
    if participant.participant_role == "observing_companion":
        participant.can_listen = False
        participant.can_speak = False
        participant.can_remember = False
        participant.can_receive_transcript = False


def _channel_event_type(channel_status: str) -> str:
    return {
        "active": "channel.resumed",
        "paused": "channel.paused",
        "closed": "channel.closed",
        "failed": "channel.failed",
    }.get(channel_status, "permission.changed")


def _record_participant_state(s: Session, participant: RealtimeCoPresenceParticipant) -> None:
    s.execute(
        RealtimeParticipantState.__table__.update()
        .where(RealtimeParticipantState.realtime_participant_id == participant.id)
        .values(is_current=False)
    )
    s.add(
        RealtimeParticipantState(
            user_id=participant.user_id,
            realtime_session_id=participant.realtime_session_id,
            realtime_participant_id=participant.id,
            state_type="presence",
            state_status=participant.participant_status,
            is_current=True,
            can_listen=participant.can_listen,
            can_speak=participant.can_speak,
            can_observe=participant.can_observe,
            can_remember=participant.can_remember,
            state_json=participant.runtime_state_json or {},
            permission_snapshot_json=participant.permission_snapshot_json or {},
            recorded_at=_now(),
            metadata_={"implementation_origin": "realtime_copresence"},
        )
    )


def _refresh_session_summary(s: Session, session: RealtimeCoPresenceSession) -> None:
    participants = list(
        s.execute(
            select(RealtimeCoPresenceParticipant).where(RealtimeCoPresenceParticipant.realtime_session_id == session.id)
        ).scalars().all()
    )
    session.participant_summary_json = {
        "participant_count": len(participants),
        "active_count": len([item for item in participants if item.participant_status == "active"]),
        "observing_count": len([item for item in participants if item.participant_role == "observing_companion"]),
        "roles": [item.participant_role for item in participants],
    }


def _close_channels(s: Session, realtime_session_id: uuid.UUID, closed_at: datetime) -> None:
    channels = list(
        s.execute(
            select(RealtimeSessionChannel).where(RealtimeSessionChannel.realtime_session_id == realtime_session_id)
        ).scalars().all()
    )
    for channel in channels:
        channel.channel_status = "closed"
        channel.closed_at = closed_at
        channel.last_event_at = closed_at


def _leave_participants(s: Session, realtime_session_id: uuid.UUID, left_at: datetime) -> None:
    participants = list(
        s.execute(
            select(RealtimeCoPresenceParticipant).where(
                RealtimeCoPresenceParticipant.realtime_session_id == realtime_session_id
            )
        ).scalars().all()
    )
    for participant in participants:
        participant.participant_status = "left"
        if participant.left_at is None:
            participant.left_at = left_at
        _record_participant_state(s, participant)


def _default_session_title(companion: Companion | None) -> str:
    return f"{companion.name} realtime co-presence session" if companion else "Realtime co-presence session"


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _session_to_dict(session: RealtimeCoPresenceSession) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "user_id": str(session.user_id),
        "co_presence_session_id": str(session.co_presence_session_id) if session.co_presence_session_id else None,
        "active_companion_id": str(session.active_companion_id) if session.active_companion_id else None,
        "originating_conversation_id": str(session.originating_conversation_id)
        if session.originating_conversation_id
        else None,
        "shared_scene_id": str(session.shared_scene_id) if session.shared_scene_id else None,
        "session_title": session.session_title,
        "session_status": session.session_status,
        "session_source": session.session_source,
        "default_transport": session.default_transport,
        "permission_snapshot_json": session.permission_snapshot_json or {},
        "participant_summary_json": session.participant_summary_json or {},
        "boundary_snapshot_json": session.boundary_snapshot_json or {},
        "runtime_state_json": session.runtime_state_json or {},
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "paused_at": session.paused_at.isoformat() if session.paused_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "last_event_at": session.last_event_at.isoformat() if session.last_event_at else None,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


def _participant_to_dict(participant: RealtimeCoPresenceParticipant) -> dict[str, Any]:
    return {
        "id": str(participant.id),
        "user_id": str(participant.user_id),
        "realtime_session_id": str(participant.realtime_session_id),
        "co_presence_participant_id": str(participant.co_presence_participant_id)
        if participant.co_presence_participant_id
        else None,
        "participant_type": participant.participant_type,
        "participant_role": participant.participant_role,
        "participant_status": participant.participant_status,
        "participant_user_id": str(participant.participant_user_id) if participant.participant_user_id else None,
        "participant_companion_id": str(participant.participant_companion_id)
        if participant.participant_companion_id
        else None,
        "external_agent_label": participant.external_agent_label,
        "can_listen": participant.can_listen,
        "can_speak": participant.can_speak,
        "can_observe": participant.can_observe,
        "can_remember": participant.can_remember,
        "can_receive_transcript": participant.can_receive_transcript,
        "permission_snapshot_json": participant.permission_snapshot_json or {},
        "runtime_state_json": participant.runtime_state_json or {},
        "joined_at": participant.joined_at.isoformat() if participant.joined_at else None,
        "left_at": participant.left_at.isoformat() if participant.left_at else None,
    }


def _channel_to_dict(channel: RealtimeSessionChannel) -> dict[str, Any]:
    return {
        "id": str(channel.id),
        "user_id": str(channel.user_id),
        "realtime_session_id": str(channel.realtime_session_id),
        "channel_type": channel.channel_type,
        "channel_status": channel.channel_status,
        "transport_type": channel.transport_type,
        "is_default_event_stream": channel.is_default_event_stream,
        "can_send_events": channel.can_send_events,
        "can_receive_actions": channel.can_receive_actions,
        "permission_snapshot_json": channel.permission_snapshot_json or {},
        "runtime_state_json": channel.runtime_state_json or {},
        "opened_at": channel.opened_at.isoformat() if channel.opened_at else None,
        "closed_at": channel.closed_at.isoformat() if channel.closed_at else None,
        "last_event_at": channel.last_event_at.isoformat() if channel.last_event_at else None,
    }


def _session_event_to_dict(event: RealtimeSessionStateEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "event_status": event.event_status,
        "previous_status": event.previous_status,
        "next_status": event.next_status,
        "event_payload_json": event.event_payload_json or {},
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
    }
