"""Companion shared scene service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Companion,
    CompanionIdentityProfile,
    CoPresenceParticipant,
    CoPresenceSession,
    SharedExperienceRecord,
    SharedScene,
    SharedSceneEvent,
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_shared_scenes(
    *,
    user_id: uuid.UUID | None = None,
    companion_scope: str = "all",
    co_presence_session_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    if companion_scope not in {"product", "test", "archived", "unclassified", "all"}:
        raise ValueError(f"Unsupported Companion scope: {companion_scope}")
    with get_session() as s:
        stmt = select(SharedScene)
        if user_id is not None:
            stmt = stmt.where(SharedScene.user_id == user_id)
        if companion_scope == "archived":
            stmt = stmt.join(Companion, Companion.id == SharedScene.owner_companion_id).join(
                CompanionIdentityProfile,
                CompanionIdentityProfile.companion_id == Companion.id,
            ).where(CompanionIdentityProfile.profile_status == "archived")
        elif companion_scope != "all":
            stmt = stmt.join(Companion, Companion.id == SharedScene.owner_companion_id).join(
                CompanionIdentityProfile,
                CompanionIdentityProfile.companion_id == Companion.id,
            ).where(
                Companion.companion_environment == companion_scope,
                CompanionIdentityProfile.profile_status == "active",
            )
        if co_presence_session_id is not None:
            stmt = stmt.where(SharedScene.co_presence_session_id == co_presence_session_id)
        if status:
            stmt = stmt.where(SharedScene.scene_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(SharedScene.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def create_shared_scene(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        session_id = _to_uuid(payload.get("co_presence_session_id"))
        if session_id is not None and s.get(CoPresenceSession, session_id) is None:
            return None
        scene = SharedScene(
            user_id=user_id,
            co_presence_session_id=session_id,
            owner_companion_id=_to_uuid(payload.get("owner_companion_id")),
            scene_title=payload.get("scene_title", ""),
            scene_summary=payload.get("scene_summary"),
            scene_type=payload.get("scene_type", "conversation"),
            scene_status=payload.get("scene_status", "active"),
            source_type=payload.get("source_type", "co_presence_session"),
            focal_topic=payload.get("focal_topic"),
            visibility_scope=payload.get("visibility_scope", "role_summary"),
            context_json=payload.get("context_json") or {},
            visibility_policy_json=payload.get("visibility_policy_json") or {},
            metadata_={"implementation_origin": "shared_scene", **(payload.get("metadata") or {})},
        )
        s.add(scene)
        s.commit()
        s.refresh(scene)
        return get_shared_scene_bundle(scene.id)


def get_shared_scene_bundle(shared_scene_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        scene = s.get(SharedScene, shared_scene_id)
        if scene is None:
            return None
        events = list(
            s.execute(
                select(SharedSceneEvent)
                .where(SharedSceneEvent.shared_scene_id == scene.id)
                .order_by(SharedSceneEvent.occurred_at.asc())
            ).scalars().all()
        )
        experiences = list(
            s.execute(
                select(SharedExperienceRecord)
                .where(SharedExperienceRecord.shared_scene_id == scene.id)
                .order_by(SharedExperienceRecord.occurred_at.asc())
            ).scalars().all()
        )
        participants = []
        companion_names = {}
        if scene.co_presence_session_id:
            participants = list(s.execute(select(CoPresenceParticipant).where(
                CoPresenceParticipant.co_presence_session_id == scene.co_presence_session_id
            ).order_by(CoPresenceParticipant.joined_at.asc())).scalars().all())
            companion_ids = [item.participant_companion_id for item in participants if item.participant_companion_id]
            if companion_ids:
                companion_names = dict(s.execute(select(Companion.id, Companion.name).where(Companion.id.in_(companion_ids))).all())
        return {
            **_scene_to_dict(scene),
            "participants": [_participant_to_dict(item, companion_names) for item in participants],
            "events": [_event_to_dict(item) for item in events],
            "shared_experiences": [_experience_to_dict(item) for item in experiences],
        }


def patch_shared_scene(shared_scene_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        scene = s.get(SharedScene, shared_scene_id)
        if scene is None:
            return None
        fields = [
            "scene_title",
            "scene_summary",
            "scene_status",
            "focal_topic",
            "visibility_scope",
            "context_json",
            "visibility_policy_json",
        ]
        for field in fields:
            if field in payload and payload[field] is not None:
                setattr(scene, field, payload[field])
        if payload.get("closed_at"):
            scene.closed_at = _to_datetime(payload["closed_at"])
        scene.updated_at = datetime.now(timezone.utc)
        s.commit()
        return get_shared_scene_bundle(scene.id)


def list_shared_scene_events(shared_scene_id: uuid.UUID) -> list[SharedSceneEvent]:
    with get_session() as s:
        return list(
            s.execute(
                select(SharedSceneEvent)
                .where(SharedSceneEvent.shared_scene_id == shared_scene_id)
                .order_by(SharedSceneEvent.occurred_at.asc())
            ).scalars().all()
        )


def create_shared_scene_event(shared_scene_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        scene = s.get(SharedScene, shared_scene_id)
        if scene is None:
            return None
        event = SharedSceneEvent(
            user_id=scene.user_id,
            shared_scene_id=scene.id,
            co_presence_session_id=_to_uuid(payload.get("co_presence_session_id")) or scene.co_presence_session_id,
            participant_id=_to_uuid(payload.get("participant_id")),
            event_type=payload.get("event_type", "scene_note"),
            event_source=payload.get("event_source", "system"),
            title=payload.get("title", ""),
            content=payload.get("content"),
            visibility_scope=payload.get("visibility_scope", scene.visibility_scope),
            triggers_shared_experience_candidate=bool(payload.get("triggers_shared_experience_candidate", False)),
            event_payload_json=payload.get("event_payload_json") or {},
            occurred_at=_to_datetime(payload["occurred_at"]) if payload.get("occurred_at") else datetime.now(timezone.utc),
            metadata_={"implementation_origin": "shared_scene"},
        )
        s.add(event)
        s.flush()

        experience = None
        if event.triggers_shared_experience_candidate:
            experience = SharedExperienceRecord(
                user_id=scene.user_id,
                co_presence_session_id=event.co_presence_session_id or scene.co_presence_session_id,
                shared_scene_id=scene.id,
                source_scene_event_id=event.id,
                source_type="scene_event",
                experience_title=event.title,
                experience_summary=payload.get("experience_summary") or event.content or event.title,
                experience_detail=payload.get("experience_detail"),
                experience_status="candidate_pending_review",
                recommended_memory_action="shared_candidate",
                review_required=True,
                created_by_participant_id=event.participant_id,
                policy_snapshot_json=payload.get("policy_snapshot_json")
                or {"visibility_scope": event.visibility_scope, "review_required": True},
                occurred_at=event.occurred_at,
                metadata_={"implementation_origin": "shared_scene", "source_event_id": str(event.id)},
            )
            s.add(experience)

        s.commit()
        s.refresh(event)
        if experience is not None:
            s.refresh(experience)
        return {
            "event": _event_to_dict(event),
            "shared_experience": _experience_to_dict(experience) if experience is not None else None,
        }


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _scene_to_dict(scene: SharedScene) -> dict[str, Any]:
    return {
        "id": str(scene.id),
        "user_id": str(scene.user_id),
        "co_presence_session_id": str(scene.co_presence_session_id) if scene.co_presence_session_id else None,
        "owner_companion_id": str(scene.owner_companion_id) if scene.owner_companion_id else None,
        "scene_title": scene.scene_title,
        "scene_summary": scene.scene_summary,
        "scene_type": scene.scene_type,
        "scene_status": scene.scene_status,
        "source_type": scene.source_type,
        "focal_topic": scene.focal_topic,
        "visibility_scope": scene.visibility_scope,
        "context_json": scene.context_json or {},
        "visibility_policy_json": scene.visibility_policy_json or {},
        "opened_at": scene.opened_at.isoformat() if scene.opened_at else None,
        "closed_at": scene.closed_at.isoformat() if scene.closed_at else None,
        "created_at": scene.created_at.isoformat() if scene.created_at else None,
        "updated_at": scene.updated_at.isoformat() if scene.updated_at else None,
    }


def _event_to_dict(event: SharedSceneEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "shared_scene_id": str(event.shared_scene_id),
        "co_presence_session_id": str(event.co_presence_session_id) if event.co_presence_session_id else None,
        "participant_id": str(event.participant_id) if event.participant_id else None,
        "event_type": event.event_type,
        "event_source": event.event_source,
        "title": event.title,
        "content": event.content,
        "visibility_scope": event.visibility_scope,
        "triggers_shared_experience_candidate": event.triggers_shared_experience_candidate,
        "event_payload_json": event.event_payload_json or {},
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
    }


def _participant_to_dict(participant: CoPresenceParticipant, companion_names: dict[uuid.UUID, str]) -> dict[str, Any]:
    return {
        "id": str(participant.id),
        "participant_type": participant.participant_type,
        "participant_role": participant.participant_role,
        "name": companion_names.get(participant.participant_companion_id) or participant.external_agent_label or ("you" if participant.participant_user_id else "unnamed participant"),
        "join_status": participant.join_status,
        "visibility_scope": participant.visibility_scope,
        "can_speak": participant.can_speak,
        "can_delegate": participant.can_delegate,
    }


def _experience_to_dict(experience: SharedExperienceRecord | None) -> dict[str, Any] | None:
    if experience is None:
        return None
    return {
        "id": str(experience.id),
        "co_presence_session_id": str(experience.co_presence_session_id) if experience.co_presence_session_id else None,
        "shared_scene_id": str(experience.shared_scene_id) if experience.shared_scene_id else None,
        "source_scene_event_id": str(experience.source_scene_event_id) if experience.source_scene_event_id else None,
        "source_type": experience.source_type,
        "experience_title": experience.experience_title,
        "experience_summary": experience.experience_summary,
        "experience_detail": experience.experience_detail,
        "experience_status": experience.experience_status,
        "recommended_memory_action": experience.recommended_memory_action,
        "review_required": experience.review_required,
        "created_by_participant_id": str(experience.created_by_participant_id)
        if experience.created_by_participant_id
        else None,
        "policy_snapshot_json": experience.policy_snapshot_json or {},
        "occurred_at": experience.occurred_at.isoformat() if experience.occurred_at else None,
    }
