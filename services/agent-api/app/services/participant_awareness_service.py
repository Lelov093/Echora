"""Companion participant awareness and memory permission service."""

import uuid
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CoPresenceParticipant,
    CoPresenceSession,
    CoPresenceSessionPolicy,
    ParticipantAwarenessState,
    ParticipantMemoryPermission,
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_awareness_states(
    co_presence_session_id: uuid.UUID,
    participant_id: uuid.UUID | None = None,
) -> list[ParticipantAwarenessState]:
    with get_session() as s:
        stmt = select(ParticipantAwarenessState).where(
            ParticipantAwarenessState.co_presence_session_id == co_presence_session_id
        )
        if participant_id is not None:
            stmt = stmt.where(ParticipantAwarenessState.participant_id == participant_id)
        stmt = stmt.order_by(ParticipantAwarenessState.updated_at.asc())
        return list(s.execute(stmt).scalars().all())


def list_memory_permissions(
    co_presence_session_id: uuid.UUID,
    participant_id: uuid.UUID | None = None,
) -> list[ParticipantMemoryPermission]:
    with get_session() as s:
        stmt = select(ParticipantMemoryPermission).where(
            ParticipantMemoryPermission.co_presence_session_id == co_presence_session_id
        )
        if participant_id is not None:
            stmt = stmt.where(ParticipantMemoryPermission.participant_id == participant_id)
        stmt = stmt.order_by(ParticipantMemoryPermission.created_at.asc())
        return list(s.execute(stmt).scalars().all())


def ensure_participant_memory_permission(
    s: Session,
    *,
    co_presence_session: CoPresenceSession,
    participant: CoPresenceParticipant,
    policy: CoPresenceSessionPolicy,
    overrides: dict[str, Any] | None = None,
) -> ParticipantMemoryPermission:
    permission = s.execute(
        select(ParticipantMemoryPermission).where(
            ParticipantMemoryPermission.co_presence_session_id == co_presence_session.id,
            ParticipantMemoryPermission.participant_id == participant.id,
        )
    ).scalar_one_or_none()
    defaults = _build_default_permission_payload(policy=policy, participant=participant)
    payload = {**defaults, **(overrides or {})}
    if permission is None:
        permission = ParticipantMemoryPermission(
            user_id=co_presence_session.user_id,
            co_presence_session_id=co_presence_session.id,
            participant_id=participant.id,
        )
        s.add(permission)
    _apply_permission_fields(permission, payload)
    return permission


def ensure_self_awareness_state(
    s: Session,
    *,
    co_presence_session: CoPresenceSession,
    participant: CoPresenceParticipant,
    overrides: dict[str, Any] | None = None,
) -> ParticipantAwarenessState:
    awareness = s.execute(
        select(ParticipantAwarenessState).where(
            ParticipantAwarenessState.co_presence_session_id == co_presence_session.id,
            ParticipantAwarenessState.participant_id == participant.id,
            ParticipantAwarenessState.target_participant_id.is_(None),
            ParticipantAwarenessState.awareness_type == "participant_presence",
        )
    ).scalar_one_or_none()
    payload = {
        "awareness_type": "participant_presence",
        "awareness_level": "full",
        "awareness_status": awareness_status_for_join_status(participant.join_status),
        "updated_by_source": "system",
        "awareness_summary": f"{participant.participant_role} is present in this co-presence session.",
        "awareness_json": {
            "participant_role": participant.participant_role,
            "visibility_scope": participant.visibility_scope,
        },
    }
    payload.update(overrides or {})
    if awareness is None:
        awareness = ParticipantAwarenessState(
            user_id=co_presence_session.user_id,
            co_presence_session_id=co_presence_session.id,
            participant_id=participant.id,
            target_participant_id=None,
        )
        s.add(awareness)
    _apply_awareness_fields(awareness, payload)
    return awareness


def sync_participant_awareness_links(
    s: Session,
    *,
    co_presence_session: CoPresenceSession,
    participant: CoPresenceParticipant,
    updated_by_source: str = "system",
) -> None:
    peers = list(
        s.execute(
            select(CoPresenceParticipant).where(
                CoPresenceParticipant.co_presence_session_id == co_presence_session.id,
                CoPresenceParticipant.id != participant.id,
            )
        ).scalars().all()
    )
    for peer in peers:
        _upsert_target_awareness(
            s,
            co_presence_session=co_presence_session,
            participant=peer,
            target_participant=participant,
            updated_by_source=updated_by_source,
        )
        _upsert_target_awareness(
            s,
            co_presence_session=co_presence_session,
            participant=participant,
            target_participant=peer,
            updated_by_source=updated_by_source,
        )


def update_participant_awareness(
    participant_id: uuid.UUID,
    payload: dict[str, Any],
) -> ParticipantAwarenessState | None:
    with get_session() as s:
        participant = s.get(CoPresenceParticipant, participant_id)
        if participant is None:
            return None
        session = s.get(CoPresenceSession, participant.co_presence_session_id)
        if session is None:
            return None
        awareness = ensure_self_awareness_state(
            s,
            co_presence_session=session,
            participant=participant,
            overrides=payload,
        )
        s.commit()
        s.refresh(awareness)
        return awareness


def update_participant_memory_permission(
    participant_id: uuid.UUID,
    payload: dict[str, Any],
) -> ParticipantMemoryPermission | None:
    with get_session() as s:
        participant = s.get(CoPresenceParticipant, participant_id)
        if participant is None:
            return None
        session = s.get(CoPresenceSession, participant.co_presence_session_id)
        if session is None:
            return None
        policy = s.execute(
            select(CoPresenceSessionPolicy).where(CoPresenceSessionPolicy.co_presence_session_id == session.id)
        ).scalar_one_or_none()
        if policy is None:
            return None
        permission = ensure_participant_memory_permission(
            s,
            co_presence_session=session,
            participant=participant,
            policy=policy,
            overrides=payload,
        )
        s.commit()
        s.refresh(permission)
        return permission


def count_observing_participants(co_presence_session_id: uuid.UUID) -> int:
    with get_session() as s:
        return (
            s.execute(
                select(func.count()).select_from(CoPresenceParticipant).where(
                    CoPresenceParticipant.co_presence_session_id == co_presence_session_id,
                    CoPresenceParticipant.participant_role == "observing_companion",
                    CoPresenceParticipant.join_status == "active",
                )
            ).scalar()
            or 0
        )


def _upsert_target_awareness(
    s: Session,
    *,
    co_presence_session: CoPresenceSession,
    participant: CoPresenceParticipant,
    target_participant: CoPresenceParticipant,
    updated_by_source: str,
) -> ParticipantAwarenessState:
    awareness = s.execute(
        select(ParticipantAwarenessState).where(
            ParticipantAwarenessState.co_presence_session_id == co_presence_session.id,
            ParticipantAwarenessState.participant_id == participant.id,
            ParticipantAwarenessState.target_participant_id == target_participant.id,
            ParticipantAwarenessState.awareness_type == "participant_presence",
        )
    ).scalar_one_or_none()
    if awareness is None:
        awareness = ParticipantAwarenessState(
            user_id=co_presence_session.user_id,
            co_presence_session_id=co_presence_session.id,
            participant_id=participant.id,
            target_participant_id=target_participant.id,
        )
        s.add(awareness)
    _apply_awareness_fields(
        awareness,
        {
            "awareness_type": "participant_presence",
            "awareness_level": "full" if target_participant.visibility_scope != "hidden" else "limited",
            "awareness_status": awareness_status_for_join_status(target_participant.join_status),
            "updated_by_source": updated_by_source,
            "awareness_summary": f"{target_participant.participant_role} is present in the shared session.",
            "awareness_json": {
                "target_participant_role": target_participant.participant_role,
                "target_visibility_scope": target_participant.visibility_scope,
            },
        },
    )
    return awareness


def awareness_status_for_join_status(join_status: str) -> str:
    """Map membership lifecycle state onto the narrower awareness contract."""
    if join_status == "active":
        return "active"
    if join_status in {"invited", "paused"}:
        return "stale"
    return "suppressed"


def _build_default_permission_payload(
    *,
    policy: CoPresenceSessionPolicy,
    participant: CoPresenceParticipant,
) -> dict[str, Any]:
    role = participant.participant_role
    if role == "primary_companion":
        memory_override = policy.default_primary_memory_participation
        allow_private_candidate = True
        allow_shared_candidate = True
    elif role == "active_companion":
        memory_override = policy.default_active_memory_participation
        allow_private_candidate = False
        allow_shared_candidate = True
    elif role == "observing_companion":
        memory_override = policy.default_observing_memory_participation
        allow_private_candidate = bool(policy.allow_observing_companion_long_term_memory)
        allow_shared_candidate = False
    elif role == "delegated_executor":
        memory_override = policy.default_delegated_memory_participation
        allow_private_candidate = False
        allow_shared_candidate = False
    else:
        memory_override = "none"
        allow_private_candidate = False
        allow_shared_candidate = False

    return {
        "permission_source": "session_default",
        "memory_participation_override": memory_override,
        "allow_private_candidate": allow_private_candidate,
        "allow_shared_candidate": allow_shared_candidate,
        "allow_user_global_summary_read": policy.user_global_memory_scope in {
            "low_risk_summary_only",
            "policy_authorized",
        },
        "allow_user_global_full_read": False,
        "allow_cross_companion_private_read": False,
        "allow_private_to_shared_sync": False,
        "allow_shared_to_private_sync": False,
        "review_required": True,
        "boundary_policy_json": {
            "private_to_shared_policy": policy.private_to_shared_policy,
            "shared_to_private_policy": policy.shared_to_private_policy,
            "cross_companion_private_read_policy": policy.cross_companion_private_read_policy,
            "allow_observing_companion_long_term_memory": policy.allow_observing_companion_long_term_memory,
        },
    }


def _apply_permission_fields(permission: ParticipantMemoryPermission, payload: dict[str, Any]) -> None:
    fields = [
        "permission_source",
        "memory_participation_override",
        "allow_private_candidate",
        "allow_shared_candidate",
        "allow_user_global_summary_read",
        "allow_user_global_full_read",
        "allow_cross_companion_private_read",
        "allow_private_to_shared_sync",
        "allow_shared_to_private_sync",
        "review_required",
        "boundary_policy_json",
    ]
    for field in fields:
        if field in payload:
            setattr(permission, field, payload[field])


def _apply_awareness_fields(awareness: ParticipantAwarenessState, payload: dict[str, Any]) -> None:
    fields = [
        "awareness_type",
        "awareness_level",
        "awareness_status",
        "updated_by_source",
        "awareness_summary",
        "awareness_json",
    ]
    for field in fields:
        if field in payload:
            setattr(awareness, field, payload[field])


def awareness_to_dict(awareness: ParticipantAwarenessState) -> dict[str, Any]:
    return {
        "id": str(awareness.id),
        "participant_id": str(awareness.participant_id),
        "target_participant_id": str(awareness.target_participant_id) if awareness.target_participant_id else None,
        "awareness_type": awareness.awareness_type,
        "awareness_level": awareness.awareness_level,
        "awareness_status": awareness.awareness_status,
        "updated_by_source": awareness.updated_by_source,
        "awareness_summary": awareness.awareness_summary,
        "awareness_json": awareness.awareness_json or {},
        "updated_at": awareness.updated_at.isoformat() if awareness.updated_at else None,
    }


def memory_permission_to_dict(permission: ParticipantMemoryPermission) -> dict[str, Any]:
    return {
        "id": str(permission.id),
        "participant_id": str(permission.participant_id),
        "permission_source": permission.permission_source,
        "memory_participation_override": permission.memory_participation_override,
        "allow_private_candidate": permission.allow_private_candidate,
        "allow_shared_candidate": permission.allow_shared_candidate,
        "allow_user_global_summary_read": permission.allow_user_global_summary_read,
        "allow_user_global_full_read": permission.allow_user_global_full_read,
        "allow_cross_companion_private_read": permission.allow_cross_companion_private_read,
        "allow_private_to_shared_sync": permission.allow_private_to_shared_sync,
        "allow_shared_to_private_sync": permission.allow_shared_to_private_sync,
        "review_required": permission.review_required,
        "boundary_policy_json": permission.boundary_policy_json or {},
        "updated_at": permission.updated_at.isoformat() if permission.updated_at else None,
    }
