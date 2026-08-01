"""Companion co-presence session service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session

from app.core.algorithm_contract import clamp01
from app.core.config import settings
from app.db.models import (
    CoPresenceParticipant,
    CoPresenceSession,
    CoPresenceSessionPolicy,
    Companion,
    CompanionBoundaryProfile,
    CompanionIdentityProfile,
    CompanionPersonaProfile,
    CompanionRelationshipContract,
    ParticipantAwarenessState,
    ParticipantMemoryPermission,
    RelationshipState,
    SharedScene,
    User,
)
from app.services import participant_awareness_service

_engine = None
CO_PRESENCE_UTILITY_VERSION = "core-r12-copresence-utility-v1"
CO_PRESENCE_UTILITY_WEIGHTS = {
    "project": {
        "usefulness": 0.20,
        "companionship": 0.08,
        "continuity": 0.13,
        "goal_progress": 0.20,
        "creativity": 0.05,
        "immersion": 0.04,
        "persona_stability": 0.13,
        "mutual_presence_value": 0.07,
        "boundary_risk": -0.16,
        "interruption_risk": -0.12,
        "cross_companion_noise": -0.10,
    },
    "creative": {
        "usefulness": 0.10,
        "companionship": 0.12,
        "continuity": 0.10,
        "goal_progress": 0.08,
        "creativity": 0.20,
        "immersion": 0.15,
        "persona_stability": 0.12,
        "mutual_presence_value": 0.13,
        "boundary_risk": -0.18,
        "interruption_risk": -0.10,
        "cross_companion_noise": -0.12,
    },
    "shared_scene": {
        "usefulness": 0.08,
        "companionship": 0.18,
        "continuity": 0.12,
        "goal_progress": 0.06,
        "creativity": 0.12,
        "immersion": 0.18,
        "persona_stability": 0.13,
        "mutual_presence_value": 0.13,
        "boundary_risk": -0.18,
        "interruption_risk": -0.12,
        "cross_companion_noise": -0.14,
    },
    "conversation": {
        "usefulness": 0.12,
        "companionship": 0.18,
        "continuity": 0.16,
        "goal_progress": 0.08,
        "creativity": 0.08,
        "immersion": 0.08,
        "persona_stability": 0.16,
        "mutual_presence_value": 0.14,
        "boundary_risk": -0.18,
        "interruption_risk": -0.12,
        "cross_companion_noise": -0.12,
    },
}


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def build_co_presence_utility_decision(
    current_companion_id: uuid.UUID,
    participants: list[dict[str, Any]],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    companion_ids = [
        _to_uuid(item.get("companion_id") or item.get("participant_companion_id"))
        for item in participants
    ]
    companion_ids = [item for item in companion_ids if item is not None]
    with get_session() as session:
        identities = _profile_map(
            session,
            CompanionIdentityProfile,
            companion_ids,
        )
        personas = _profile_map(
            session,
            CompanionPersonaProfile,
            companion_ids,
        )
        contracts = _profile_map(
            session,
            CompanionRelationshipContract,
            companion_ids,
        )
        boundaries = _profile_map(
            session,
            CompanionBoundaryProfile,
            companion_ids,
        )
        relationships = _profile_map(
            session,
            RelationshipState,
            companion_ids,
        )

    candidates = []
    for participant in participants:
        companion_id = _to_uuid(
            participant.get("companion_id")
            or participant.get("participant_companion_id")
        )
        if companion_id is None:
            continue
        candidates.append(
            {
                **participant,
                "companion_id": str(companion_id),
                "identity": _identity_features(identities.get(companion_id)),
                "persona": _persona_features(personas.get(companion_id)),
                "relationship_contract": _contract_features(
                    contracts.get(companion_id)
                ),
                "boundary_profile": _boundary_features(
                    boundaries.get(companion_id)
                ),
                "relationship": _relationship_features(
                    relationships.get(companion_id)
                ),
            }
        )
    return score_co_presence_utility(
        candidates,
        current_companion_id=str(current_companion_id),
        context=context,
    )


def score_co_presence_utility(
    candidates: list[dict[str, Any]],
    *,
    current_companion_id: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = dict(context or {})
    context_key = _utility_context_key(context)
    weights = CO_PRESENCE_UTILITY_WEIGHTS[context_key]
    active_count = len(
        [
            item
            for item in candidates
            if item.get("join_status") == "active"
        ]
    )
    scored = []
    for candidate in candidates:
        factors = _co_presence_factors(
            candidate,
            current_companion_id=current_companion_id,
            context=context,
            active_count=active_count,
        )
        raw_utility = sum(
            weights[name] * factors[name] for name in weights
        )
        veto_reasons = []
        if candidate.get("join_status") != "active":
            veto_reasons.append("participant_not_active")
        if candidate.get("can_speak") is False:
            veto_reasons.append("participant_cannot_speak")
        if factors["persona_stability"] < 0.45:
            veto_reasons.append("persona_stability_below_gate")
        if factors["boundary_risk"] >= 0.75:
            veto_reasons.append("boundary_risk_above_gate")
        utility = 0.0 if veto_reasons else clamp01(raw_utility)
        scored.append(
            {
                "companion_id": str(candidate.get("companion_id")),
                "participant_id": candidate.get("participant_id")
                or candidate.get("id"),
                "participant_role": candidate.get("participant_role"),
                "join_status": candidate.get("join_status"),
                "can_speak": candidate.get("can_speak", True),
                "utility": round(utility, 6),
                "raw_utility": round(raw_utility, 6),
                "factors": {
                    key: round(value, 6) for key, value in factors.items()
                },
                "vetoed": bool(veto_reasons),
                "veto_reasons": veto_reasons,
            }
        )

    ranked = sorted(
        scored,
        key=lambda item: (-item["utility"], item["companion_id"]),
    )
    current = next(
        (
            item
            for item in ranked
            if item["companion_id"] == current_companion_id
        ),
        None,
    )
    selected = current if current and not current["vetoed"] else None
    for item in scored:
        item["speaker_status"] = (
            "speaker"
            if selected and item["companion_id"] == selected["companion_id"]
            else "observing"
        )
        item["selection_reason"] = (
            "conversation_scoped_active_companion"
            if item["speaker_status"] == "speaker"
            else (
                "safety_gate_veto"
                if item["vetoed"]
                else "single_speaker_default"
            )
        )

    invite_candidate = next(
        (
            item
            for item in ranked
            if item["companion_id"] != current_companion_id
            and not item["vetoed"]
            and item["utility"] >= 0.35
        ),
        None,
    )
    invite_reason = (
        _invite_reason(invite_candidate, context_key)
        if invite_candidate
        else "no_additional_companion_cleared_utility_and_safety_gates"
    )
    return {
        "algorithm_version": CO_PRESENCE_UTILITY_VERSION,
        "context_key": context_key,
        "weights": dict(weights),
        "candidate_count": len(scored),
        "selected_speaker_companion_id": (
            selected["companion_id"] if selected else None
        ),
        "speaker_count": 1 if selected else 0,
        "observer_companion_ids": [
            item["companion_id"]
            for item in scored
            if not selected
            or item["companion_id"] != selected["companion_id"]
        ],
        "candidates": scored,
        "invite_recommendation": {
            "allowed": invite_candidate is not None,
            "target_companion_id": (
                invite_candidate["companion_id"]
                if invite_candidate
                else None
            ),
            "utility": (
                invite_candidate["utility"] if invite_candidate else 0.0
            ),
            "reason": invite_reason,
            "requires_user_confirmation": True,
            "requires_group_persona_gate": True,
        },
    }


def apply_group_persona_gate(
    decision: dict[str, Any],
    group_gate: dict[str, Any] | None,
) -> dict[str, Any]:
    result = {
        **decision,
        "candidates": [
            {**item} for item in decision.get("candidates", [])
        ],
        "invite_recommendation": {
            **(decision.get("invite_recommendation") or {})
        },
    }
    invitation = result["invite_recommendation"]
    gate_status = str((group_gate or {}).get("check_status") or "not_run")
    invitation["group_persona_gate"] = {
        "status": gate_status,
        "consistency_score": (group_gate or {}).get("consistency_score"),
        "requires_review": bool(
            (group_gate or {}).get("requires_review", False)
        ),
    }
    if gate_status == "blocked":
        invitation.update(
            {
                "allowed": False,
                "target_companion_id": None,
                "reason": "group_persona_consistency_blocked_invitation",
            }
        )
    elif gate_status == "review_required":
        invitation["requires_user_confirmation"] = True
        invitation["reason"] = (
            f"{invitation.get('reason')}; group_persona_review_required"
        )
    return result


def list_co_presence_sessions(
    *,
    user_id: uuid.UUID | None = None,
    status: str | None = None,
    session_source: str | None = None,
    companion_scope: str = "all",
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(CoPresenceSession)
        if user_id is not None:
            stmt = stmt.where(CoPresenceSession.user_id == user_id)
        if status:
            stmt = stmt.where(CoPresenceSession.session_status == status)
        if session_source:
            stmt = stmt.where(CoPresenceSession.session_source == session_source)
        if companion_scope == "product":
            stmt = stmt.join(Companion, Companion.id == CoPresenceSession.primary_companion_id).where(
                Companion.companion_environment == "product",
                Companion.deleted_at.is_(None),
            )
        elif companion_scope != "all":
            raise ValueError(f"Unsupported Companion scope: {companion_scope}")
        normalized_search = (search or "").strip()
        if normalized_search:
            pattern = f"%{normalized_search}%"
            stmt = stmt.where(or_(
                CoPresenceSession.session_title.ilike(pattern),
                CoPresenceSession.session_summary.ilike(pattern),
                CoPresenceSession.session_status.ilike(pattern),
            ))
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(CoPresenceSession.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def create_co_presence_session(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        primary_companion = s.get(Companion, _to_uuid(payload.get("primary_companion_id")))
        user = s.get(User, user_id)
        if primary_companion is None or user is None:
            return None

        session = CoPresenceSession(
            user_id=user_id,
            primary_companion_id=primary_companion.id,
            originating_conversation_id=_to_uuid(payload.get("originating_conversation_id")),
            session_title=payload.get("session_title") or f"{primary_companion.name} co-presence session",
            session_summary=payload.get("session_summary"),
            session_status=payload.get("session_status", "active"),
            session_source=payload.get("session_source", "direct_conversation"),
            visibility_scope=payload.get("visibility_scope", "role_summary"),
            entry_reason=payload.get("entry_reason"),
            participant_summary_json={},
            boundary_summary_json={},
            metadata_={"implementation_origin": "shared_scene", **(payload.get("metadata") or {})},
        )
        s.add(session)
        s.flush()

        policy = CoPresenceSessionPolicy(
            user_id=user_id,
            co_presence_session_id=session.id,
            policy_status="active",
            default_primary_memory_participation=_policy_value(
                payload, "default_primary_memory_participation", "private_candidate_allowed"
            ),
            default_active_memory_participation=_policy_value(
                payload, "default_active_memory_participation", "shared_candidate_allowed"
            ),
            default_observing_memory_participation=_policy_value(
                payload, "default_observing_memory_participation", "none"
            ),
            default_delegated_memory_participation=_policy_value(
                payload, "default_delegated_memory_participation", "candidate_only"
            ),
            user_global_memory_scope=_policy_value(payload, "user_global_memory_scope", "low_risk_summary_only"),
            cross_companion_private_read_policy=_policy_value(
                payload, "cross_companion_private_read_policy", "deny"
            ),
            private_to_shared_policy=_policy_value(payload, "private_to_shared_policy", "review_required"),
            shared_to_private_policy=_policy_value(payload, "shared_to_private_policy", "review_required"),
            allow_observing_companion_long_term_memory=bool(
                _policy_value(payload, "allow_observing_companion_long_term_memory", False)
            ),
            allow_autonomous_companion_interaction=bool(
                _policy_value(payload, "allow_autonomous_companion_interaction", False)
            ),
            session_visibility_policy_json=payload.get("session_visibility_policy_json") or {},
            boundary_policy_json=payload.get("boundary_policy_json") or {},
            metadata_={"implementation_origin": "shared_scene"},
        )
        s.add(policy)
        s.flush()

        user_participant = CoPresenceParticipant(
            user_id=user_id,
            co_presence_session_id=session.id,
            participant_type="user",
            participant_role="user",
            participant_user_id=user.id,
            join_status="active",
            visibility_scope=session.visibility_scope,
            can_speak=True,
            can_delegate=True,
            policy_override_json={},
            metadata_={"implementation_origin": "shared_scene", "bootstrap": "user"},
        )
        primary_participant = CoPresenceParticipant(
            user_id=user_id,
            co_presence_session_id=session.id,
            participant_type="companion",
            participant_role="primary_companion",
            participant_companion_id=primary_companion.id,
            join_status="active",
            visibility_scope=session.visibility_scope,
            can_speak=True,
            can_delegate=True,
            policy_override_json={},
            metadata_={"implementation_origin": "shared_scene", "bootstrap": "primary_companion"},
        )
        s.add_all([user_participant, primary_participant])
        s.flush()

        for participant in (user_participant, primary_participant):
            participant_awareness_service.ensure_self_awareness_state(
                s, co_presence_session=session, participant=participant
            )
            participant_awareness_service.ensure_participant_memory_permission(
                s,
                co_presence_session=session,
                participant=participant,
                policy=policy,
            )
        participant_awareness_service.sync_participant_awareness_links(
            s, co_presence_session=session, participant=primary_participant
        )
        _refresh_session_summaries(s, session, policy)
        s.commit()
        return get_co_presence_session_bundle(session.id)


def get_co_presence_session_bundle(co_presence_session_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        session = s.get(CoPresenceSession, co_presence_session_id)
        if session is None:
            return None
        policy = s.execute(
            select(CoPresenceSessionPolicy).where(CoPresenceSessionPolicy.co_presence_session_id == session.id)
        ).scalar_one_or_none()
        participants = list(
            s.execute(
                select(CoPresenceParticipant)
                .where(CoPresenceParticipant.co_presence_session_id == session.id)
                .order_by(CoPresenceParticipant.joined_at.asc())
            ).scalars().all()
        )
        awareness_states = list(
            s.execute(
                select(ParticipantAwarenessState)
                .where(ParticipantAwarenessState.co_presence_session_id == session.id)
                .order_by(ParticipantAwarenessState.updated_at.asc())
            ).scalars().all()
        )
        permissions = list(
            s.execute(
                select(ParticipantMemoryPermission)
                .where(ParticipantMemoryPermission.co_presence_session_id == session.id)
                .order_by(ParticipantMemoryPermission.created_at.asc())
            ).scalars().all()
        )
        scenes = list(
            s.execute(
                select(SharedScene)
                .where(SharedScene.co_presence_session_id == session.id)
                .order_by(SharedScene.created_at.asc())
            ).scalars().all()
        )
        awareness_by_participant: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for item in awareness_states:
            awareness_by_participant.setdefault(item.participant_id, []).append(
                participant_awareness_service.awareness_to_dict(item)
            )
        permission_by_participant = {
            item.participant_id: participant_awareness_service.memory_permission_to_dict(item) for item in permissions
        }
        return {
            **_session_to_dict(session),
            "policy": _policy_to_dict(policy) if policy else None,
            "participants": [
                {
                    **_participant_to_dict(item),
                    "awareness_states": awareness_by_participant.get(item.id, []),
                    "memory_permission": permission_by_participant.get(item.id),
                }
                for item in participants
            ],
            "shared_scene_ids": [str(scene.id) for scene in scenes],
        }


def patch_co_presence_session(
    co_presence_session_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    with get_session() as s:
        session = s.get(CoPresenceSession, co_presence_session_id)
        if session is None:
            return None
        fields = ["session_title", "session_summary", "session_status", "visibility_scope"]
        for field in fields:
            if field in payload and payload[field] is not None:
                setattr(session, field, payload[field])
        if payload.get("ended_at"):
            session.ended_at = _to_datetime(payload["ended_at"])
        if "boundary_summary_json" in payload and payload["boundary_summary_json"] is not None:
            session.boundary_summary_json = payload["boundary_summary_json"]
        session.updated_at = datetime.now(timezone.utc)
        s.commit()
        return get_co_presence_session_bundle(session.id)


def add_participant_to_session(
    co_presence_session_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    with get_session() as s:
        session = s.get(CoPresenceSession, co_presence_session_id)
        if session is None:
            return None
        policy = s.execute(
            select(CoPresenceSessionPolicy).where(CoPresenceSessionPolicy.co_presence_session_id == session.id)
        ).scalar_one_or_none()
        if policy is None:
            return None
        participant = CoPresenceParticipant(
            user_id=session.user_id,
            co_presence_session_id=session.id,
            participant_type=payload["participant_type"],
            participant_role=payload.get("participant_role", "active_companion"),
            participant_user_id=_to_uuid(payload.get("participant_user_id")),
            participant_companion_id=_to_uuid(payload.get("participant_companion_id")),
            external_agent_label=payload.get("external_agent_label"),
            join_status=payload.get("join_status", "active"),
            visibility_scope=payload.get("visibility_scope", session.visibility_scope),
            can_speak=bool(payload.get("can_speak", True)),
            can_delegate=bool(payload.get("can_delegate", False)),
            policy_override_json=payload.get("policy_override_json") or {},
            metadata_={"implementation_origin": "shared_scene"},
        )
        s.add(participant)
        s.flush()
        participant_awareness_service.ensure_self_awareness_state(
            s,
            co_presence_session=session,
            participant=participant,
            overrides=payload.get("awareness") or {},
        )
        participant_awareness_service.ensure_participant_memory_permission(
            s,
            co_presence_session=session,
            participant=participant,
            policy=policy,
            overrides=payload.get("memory_permission") or {},
        )
        participant_awareness_service.sync_participant_awareness_links(
            s, co_presence_session=session, participant=participant
        )
        _refresh_session_summaries(s, session, policy)
        s.commit()
        return get_co_presence_session_bundle(session.id)


def patch_participant(
    co_presence_session_id: uuid.UUID,
    participant_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    with get_session() as s:
        session = s.get(CoPresenceSession, co_presence_session_id)
        participant = s.get(CoPresenceParticipant, participant_id)
        if session is None or participant is None or participant.co_presence_session_id != session.id:
            return None
        policy = s.execute(
            select(CoPresenceSessionPolicy).where(CoPresenceSessionPolicy.co_presence_session_id == session.id)
        ).scalar_one_or_none()
        if policy is None:
            return None
        fields = ["participant_role", "join_status", "visibility_scope", "can_speak", "can_delegate"]
        for field in fields:
            if field in payload and payload[field] is not None:
                setattr(participant, field, payload[field])
        if payload.get("left_at"):
            participant.left_at = _to_datetime(payload["left_at"])
        if "policy_override_json" in payload and payload["policy_override_json"] is not None:
            participant.policy_override_json = payload["policy_override_json"]
        participant.updated_at = datetime.now(timezone.utc)
        participant_awareness_service.ensure_self_awareness_state(
            s,
            co_presence_session=session,
            participant=participant,
            overrides=payload.get("awareness") or {"awareness_status": participant.join_status},
        )
        participant_awareness_service.ensure_participant_memory_permission(
            s,
            co_presence_session=session,
            participant=participant,
            policy=policy,
            overrides=payload.get("memory_permission") or {},
        )
        participant_awareness_service.sync_participant_awareness_links(
            s, co_presence_session=session, participant=participant, updated_by_source="system"
        )
        _refresh_session_summaries(s, session, policy)
        s.commit()
        return get_co_presence_session_bundle(session.id)


def end_co_presence_session(co_presence_session_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        session = s.get(CoPresenceSession, co_presence_session_id)
        if session is None:
            return None
        ended_at = datetime.now(timezone.utc)
        session.session_status = "ended"
        session.ended_at = ended_at
        participants = list(
            s.execute(
                select(CoPresenceParticipant).where(CoPresenceParticipant.co_presence_session_id == session.id)
            ).scalars().all()
        )
        for participant in participants:
            if participant.join_status == "active":
                participant.join_status = "left"
            if participant.left_at is None:
                participant.left_at = ended_at
        policy = s.execute(
            select(CoPresenceSessionPolicy).where(CoPresenceSessionPolicy.co_presence_session_id == session.id)
        ).scalar_one_or_none()
        if policy is not None:
            _refresh_session_summaries(s, session, policy)
        s.commit()
        return get_co_presence_session_bundle(session.id)


def _refresh_session_summaries(
    s: Session,
    session: CoPresenceSession,
    policy: CoPresenceSessionPolicy,
) -> None:
    participants = list(
        s.execute(
            select(CoPresenceParticipant).where(CoPresenceParticipant.co_presence_session_id == session.id)
        ).scalars().all()
    )
    active_count = len([item for item in participants if item.join_status == "active"])
    observing_count = len([item for item in participants if item.participant_role == "observing_companion"])
    session.participant_summary_json = {
        "participant_count": len(participants),
        "active_count": active_count,
        "observing_count": observing_count,
        "roles": [item.participant_role for item in participants],
    }
    session.boundary_summary_json = {
        "user_global_memory_scope": policy.user_global_memory_scope,
        "cross_companion_private_read_policy": policy.cross_companion_private_read_policy,
        "private_to_shared_policy": policy.private_to_shared_policy,
        "shared_to_private_policy": policy.shared_to_private_policy,
        "allow_observing_companion_long_term_memory": policy.allow_observing_companion_long_term_memory,
    }


def _policy_value(payload: dict[str, Any], key: str, default: Any) -> Any:
    policy = payload.get("policy") or {}
    if key in policy:
        return policy[key]
    return payload.get(key, default)


def _profile_map(
    session: Session,
    model: type,
    companion_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Any]:
    if not companion_ids:
        return {}
    rows = list(
        session.execute(
            select(model).where(model.companion_id.in_(companion_ids))
        ).scalars()
    )
    return {row.companion_id: row for row in rows}


def _utility_context_key(context: dict[str, Any]) -> str:
    if context.get("shared_scene_id") or context.get("has_shared_scene"):
        return "shared_scene"
    mode = str(context.get("mode") or "conversation").lower()
    if mode in {"project", "creative"}:
        return mode
    return "conversation"


def _co_presence_factors(
    candidate: dict[str, Any],
    *,
    current_companion_id: str,
    context: dict[str, Any],
    active_count: int,
) -> dict[str, float]:
    relationship = candidate.get("relationship") or {}
    identity = candidate.get("identity") or {}
    persona = candidate.get("persona") or {}
    contract = candidate.get("relationship_contract") or {}
    boundary = candidate.get("boundary_profile") or {}
    role = str(candidate.get("participant_role") or "")
    is_current = str(candidate.get("companion_id")) == current_companion_id
    is_primary = role == "primary_companion"
    is_observing = role == "observing_companion"
    collaboration = clamp01(relationship.get("collaboration"), 0.5)
    trust = clamp01(relationship.get("trust"), 0.5)
    closeness = clamp01(relationship.get("emotional_closeness"), 0.5)
    relationship_continuity = clamp01(
        relationship.get("continuity"),
        0.5,
    )
    identity_continuity = (
        1.0
        if identity.get("self_continuity_summary")
        else (
            0.7
            if identity.get("profile_status", "active") == "active"
            else 0.2
        )
    )
    continuity = clamp01(
        0.75 * relationship_continuity
        + 0.25 * identity_continuity
    )
    support_scope = contract.get("support_scope_json") or []
    contract_active = contract.get("contract_status", "active") == "active"

    usefulness = clamp01(
        0.35
        + 0.30 * collaboration
        + (0.20 if is_primary or is_current else 0.0)
        + (0.15 if support_scope else 0.0)
    )
    companionship = clamp01((trust + closeness) / 2.0)
    goal_progress = clamp01(
        0.65 * collaboration
        + (0.25 if context.get("has_goal") else 0.0)
        + (0.10 if is_current else 0.0)
    )
    creativity = clamp01(
        0.45
        + (
            0.35
            if str(persona.get("presence_style") or "").lower()
            in {"creative", "playful", "expressive", "immersive"}
            else 0.0
        )
        + (0.20 if context.get("mode") == "creative" else 0.0)
    )
    immersion = clamp01(
        0.35
        + (0.40 if context.get("has_shared_scene") else 0.0)
        + (0.15 if not is_observing else 0.0)
    )
    persona_stability = _persona_stability(
        persona,
        contract_active,
        identity.get("profile_status", "active") == "active",
    )
    mutual_presence_value = clamp01(
        0.35
        + (0.25 if candidate.get("join_status") == "active" else 0.0)
        + (0.20 if is_current else 0.0)
        + (0.10 if candidate.get("can_delegate") else 0.0)
    )

    boundary_risk = clamp01(context.get("boundary_risk"), 0.0)
    if candidate.get("can_speak") is False:
        boundary_risk = 1.0
    if candidate.get("join_status") != "active":
        boundary_risk = max(boundary_risk, 0.85)
    if not contract_active:
        boundary_risk = max(boundary_risk, 0.85)
    if boundary.get("presence_interrupt_policy") == "silent_only":
        boundary_risk = max(boundary_risk, 0.90)
    if boundary.get("cross_companion_read_policy") not in {
        None,
        "blocked",
        "review_required",
    }:
        boundary_risk = max(boundary_risk, 0.55)

    interruption_risk = clamp01(
        context.get("interruption_risk"),
        0.15 if is_current else 0.30,
    )
    if is_observing:
        interruption_risk = max(interruption_risk, 0.45)
    if str(context.get("user_focus") or "") in {"deep_work", "resting"}:
        interruption_risk = max(interruption_risk, 0.85)
    cross_companion_noise = clamp01(
        max(0, active_count - 1) / 4.0
        + (0.20 if is_observing else 0.0)
    )
    return {
        "usefulness": usefulness,
        "companionship": companionship,
        "continuity": continuity,
        "goal_progress": goal_progress,
        "creativity": creativity,
        "immersion": immersion,
        "persona_stability": persona_stability,
        "mutual_presence_value": mutual_presence_value,
        "boundary_risk": boundary_risk,
        "interruption_risk": interruption_risk,
        "cross_companion_noise": cross_companion_noise,
    }


def _persona_stability(
    persona: dict[str, Any],
    contract_active: bool,
    identity_active: bool,
) -> float:
    lock_scores = {
        "locked": 1.0,
        "guarded": 0.9,
        "review_required": 0.8,
        "adaptive": 0.65,
    }
    drift_scores = {
        "strict": 1.0,
        "standard": 0.85,
        "guarded": 0.9,
        "loose": 0.55,
    }
    lock = lock_scores.get(
        str(persona.get("persona_lock_level") or "guarded").lower(),
        0.75,
    )
    drift = drift_scores.get(
        str(persona.get("drift_guard_level") or "standard").lower(),
        0.75,
    )
    return clamp01(
        0.45 * lock
        + 0.35 * drift
        + 0.10 * contract_active
        + 0.10 * identity_active
    )


def _invite_reason(
    candidate: dict[str, Any],
    context_key: str,
) -> str:
    factors = candidate.get("factors") or {}
    positive = [
        key
        for key in (
            "usefulness",
            "companionship",
            "continuity",
            "goal_progress",
            "creativity",
            "immersion",
            "persona_stability",
            "mutual_presence_value",
        )
        if factors.get(key, 0.0) >= 0.6
    ]
    strongest = positive[:3] or ["mutual_presence_value"]
    return (
        f"{context_key}_utility_support:"
        + ",".join(strongest)
    )


def _identity_features(profile: Any | None) -> dict[str, Any]:
    if profile is None:
        return {}
    return {
        "display_name": profile.display_name,
        "identity_summary": profile.identity_summary,
        "self_continuity_summary": profile.self_continuity_summary,
        "profile_status": profile.profile_status,
    }


def _persona_features(profile: Any | None) -> dict[str, Any]:
    if profile is None:
        return {}
    return {
        "persona_lock_level": profile.persona_lock_level,
        "drift_guard_level": profile.drift_guard_level,
        "presence_style": profile.presence_style,
    }


def _contract_features(profile: Any | None) -> dict[str, Any]:
    if profile is None:
        return {}
    return {
        "relationship_role": profile.relationship_role,
        "contract_status": profile.contract_status,
        "support_scope_json": profile.support_scope_json or [],
        "cross_companion_disclosure_policy": (
            profile.cross_companion_disclosure_policy
        ),
    }


def _boundary_features(profile: Any | None) -> dict[str, Any]:
    if profile is None:
        return {}
    return {
        "cross_companion_read_policy": profile.cross_companion_read_policy,
        "presence_interrupt_policy": profile.presence_interrupt_policy,
        "review_required_cross_companion_share": (
            profile.review_required_cross_companion_share
        ),
    }


def _relationship_features(profile: Any | None) -> dict[str, Any]:
    if profile is None:
        return {}
    return {
        "familiarity": profile.familiarity,
        "understanding": profile.understanding,
        "collaboration": profile.collaboration,
        "trust": profile.trust,
        "emotional_closeness": profile.emotional_closeness,
        "boundary_awareness": profile.boundary_awareness,
        "continuity": profile.continuity,
    }


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _session_to_dict(session: CoPresenceSession) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "user_id": str(session.user_id),
        "primary_companion_id": str(session.primary_companion_id),
        "originating_conversation_id": str(session.originating_conversation_id)
        if session.originating_conversation_id
        else None,
        "session_title": session.session_title,
        "session_summary": session.session_summary,
        "session_status": session.session_status,
        "session_source": session.session_source,
        "visibility_scope": session.visibility_scope,
        "entry_reason": session.entry_reason,
        "participant_summary_json": session.participant_summary_json or {},
        "boundary_summary_json": session.boundary_summary_json or {},
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "roster_revision": session.roster_revision,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


def _participant_to_dict(participant: CoPresenceParticipant) -> dict[str, Any]:
    return {
        "id": str(participant.id),
        "user_id": str(participant.user_id),
        "co_presence_session_id": str(participant.co_presence_session_id),
        "participant_type": participant.participant_type,
        "participant_role": participant.participant_role,
        "participant_user_id": str(participant.participant_user_id) if participant.participant_user_id else None,
        "participant_companion_id": str(participant.participant_companion_id)
        if participant.participant_companion_id
        else None,
        "external_agent_label": participant.external_agent_label,
        "join_status": participant.join_status,
        "visibility_scope": participant.visibility_scope,
        "can_speak": participant.can_speak,
        "can_delegate": participant.can_delegate,
        "joined_at": participant.joined_at.isoformat() if participant.joined_at else None,
        "left_at": participant.left_at.isoformat() if participant.left_at else None,
        "rejoined_at": participant.rejoined_at.isoformat() if participant.rejoined_at else None,
        "muted_at": participant.muted_at.isoformat() if participant.muted_at else None,
        "revoked_at": participant.revoked_at.isoformat() if participant.revoked_at else None,
        "membership_revision": participant.membership_revision,
        "policy_override_json": participant.policy_override_json or {},
    }


def _policy_to_dict(policy: CoPresenceSessionPolicy) -> dict[str, Any]:
    return {
        "id": str(policy.id),
        "co_presence_session_id": str(policy.co_presence_session_id),
        "policy_status": policy.policy_status,
        "default_primary_memory_participation": policy.default_primary_memory_participation,
        "default_active_memory_participation": policy.default_active_memory_participation,
        "default_observing_memory_participation": policy.default_observing_memory_participation,
        "default_delegated_memory_participation": policy.default_delegated_memory_participation,
        "user_global_memory_scope": policy.user_global_memory_scope,
        "cross_companion_private_read_policy": policy.cross_companion_private_read_policy,
        "private_to_shared_policy": policy.private_to_shared_policy,
        "shared_to_private_policy": policy.shared_to_private_policy,
        "allow_observing_companion_long_term_memory": policy.allow_observing_companion_long_term_memory,
        "allow_autonomous_companion_interaction": policy.allow_autonomous_companion_interaction,
        "session_visibility_policy_json": policy.session_visibility_policy_json or {},
        "boundary_policy_json": policy.boundary_policy_json or {},
    }
