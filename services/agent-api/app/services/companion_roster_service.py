"""Companion companion roster service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Companion,
    CompanionMode,
    CompanionIdentityProfile,
    CompanionPersonaProfile,
    CompanionRelationshipContract,
    CompanionBoundaryProfile,
    CompanionVisibilityPolicy,
    CompanionLifecycleEvent,
    Conversation,
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


COMPANION_SCOPES = {"product", "test", "archived", "unclassified", "all"}
COMPANION_ENVIRONMENTS = {"unclassified", "product", "test"}
COMPANION_PROVENANCE = {"legacy", "user_created", "seed", "smoke", "import", "system"}


def list_companions(user_id: uuid.UUID | None = None, scope: str = "all") -> list[Companion]:
    if scope not in COMPANION_SCOPES:
        raise ValueError(f"Unsupported Companion scope: {scope}")
    with get_session() as s:
        stmt = select(Companion).where(Companion.deleted_at.is_(None)).order_by(Companion.created_at.desc())
        if user_id:
            stmt = stmt.where(Companion.user_id == user_id)
        if scope == "archived":
            stmt = stmt.join(CompanionIdentityProfile).where(CompanionIdentityProfile.profile_status == "archived")
        elif scope != "all":
            stmt = stmt.join(CompanionIdentityProfile).where(
                Companion.companion_environment == scope,
                CompanionIdentityProfile.profile_status == "active",
            )
        return list(s.execute(stmt).scalars().all())


def list_companions_page(
    *,
    user_id: uuid.UUID | None = None,
    scope: str = "all",
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Return a roster page without materializing the owner's full Companion history."""
    if scope not in COMPANION_SCOPES:
        raise ValueError(f"Unsupported Companion scope: {scope}")
    with get_session() as s:
        stmt = select(Companion).where(Companion.deleted_at.is_(None))
        if user_id:
            stmt = stmt.where(Companion.user_id == user_id)
        if scope == "archived":
            stmt = stmt.join(CompanionIdentityProfile).where(CompanionIdentityProfile.profile_status == "archived")
        elif scope != "all":
            stmt = stmt.join(CompanionIdentityProfile).where(
                Companion.companion_environment == scope,
                CompanionIdentityProfile.profile_status == "active",
            )
        normalized_search = (search or "").strip()
        if normalized_search:
            pattern = f"%{normalized_search}%"
            stmt = stmt.where(or_(
                Companion.name.ilike(pattern),
                Companion.subtitle.ilike(pattern),
                Companion.current_focus.ilike(pattern),
            ))
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(s.execute(
            stmt.order_by(Companion.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all())
        return {"items": items, "total": total}


def get_companion(companion_id: uuid.UUID) -> Companion | None:
    with get_session() as s:
        return s.get(Companion, companion_id)


def create_companion(payload: dict[str, Any]) -> tuple[Companion, Conversation]:
    environment = payload.get("companion_environment", "product")
    provenance = payload.get("provenance", "user_created")
    if environment not in COMPANION_ENVIRONMENTS:
        raise ValueError(f"Unsupported Companion environment: {environment}")
    if provenance not in COMPANION_PROVENANCE:
        raise ValueError(f"Unsupported Companion provenance: {provenance}")
    with get_session() as s:
        user_id = payload["user_id"]
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)
        companion_data = {
            "user_id": user_id,
            "name": payload.get("name", "Echora"),
            "subtitle": payload.get("subtitle"),
            "identity_prompt": payload.get("identity_prompt"),
            "base_personality": payload.get("base_personality"),
            "tone_profile": payload.get("tone_profile") or {},
            "companion_profile": payload.get("companion_profile") or {},
            "current_mode": payload.get("current_mode", "project"),
            "current_status": payload.get("current_status", "idle"),
            "current_focus": payload.get("current_focus"),
            "companion_environment": environment,
            "provenance": provenance,
        }
        companion = Companion(**companion_data)
        s.add(companion)
        s.flush()

        _ensure_default_modes(s, companion)
        _ensure_companion_profiles(
            s,
            companion,
            payload.get("identity") or {},
            payload.get("persona") or {},
            payload.get("contract") or {},
            payload.get("boundary") or {},
            payload.get("visibility") or {},
        )
        first_meeting = Conversation(
            user_id=companion.user_id,
            companion_id=companion.id,
            title="第一次相识",
            mode_key=companion.current_mode,
            current_topic="认识彼此",
            current_goal="从双方确认的关系与边界开始",
            continuity_state={"origin": "companion_creation", "memory_commit_requires_review": True},
        )
        s.add(first_meeting)
        s.flush()
        _record_lifecycle_event(
            s,
            companion_id=companion.id,
            user_id=companion.user_id,
            event_type="relationship_contract_initialized",
            event_source="api",
            title="第一次相识开始",
            detail="已建立最初的关系约定与边界；后续长期记忆仍需用户确认。",
            previous_state_json={},
            new_state_json={
                "name": companion.name,
                "current_mode": companion.current_mode,
                "relationship_intent": (payload.get("contract") or {}).get("relationship_role", "companion"),
                "first_meeting_conversation_id": str(first_meeting.id),
                "origin": "companion_creation",
            },
            review_required=False,
            metadata={"implementation_origin": "companion_creation", "origin": "companion_creation"},
        )
        s.commit()
        s.refresh(companion)
        s.refresh(first_meeting)
        return companion, first_meeting


def update_companion(companion_id: uuid.UUID, payload: dict[str, Any]) -> Companion | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        previous = _companion_to_dict(companion)
        mutable_fields = [
            "name",
            "subtitle",
            "identity_prompt",
            "base_personality",
            "tone_profile",
            "companion_profile",
            "current_mode",
            "current_status",
            "current_focus",
        ]
        for field in mutable_fields:
            if field in payload and payload[field] is not None:
                setattr(companion, field, payload[field])
        companion.updated_at = datetime.now(timezone.utc)
        s.flush()
        if companion.name != previous["name"]:
            identity = _get_identity_profile(s, companion.id)
            if identity:
                identity.display_name = companion.name
        _record_lifecycle_event(
            s,
            companion_id=companion.id,
            user_id=companion.user_id,
            event_type="companion_profile_backfilled",
            event_source="api",
            title="Companion updated",
            detail="Roster fields updated",
            previous_state_json=previous,
            new_state_json=_companion_to_dict(companion),
            review_required=False,
            metadata={"implementation_origin": "companion_profile"},
        )
        s.commit()
        s.refresh(companion)
        return companion


def get_companion_bundle(companion_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        created = _ensure_companion_profiles(s, companion)
        if created:
            s.commit()
        identity = _get_identity_profile(s, companion.id)
        persona = _get_persona_profile(s, companion.id)
        contract = _get_contract_profile(s, companion.id)
        boundary = _get_boundary_profile(s, companion.id)
        return {
            **_companion_to_dict(companion),
            "identity_profile_status": identity.profile_status if identity else None,
            "persona_lock_level": persona.persona_lock_level if persona else None,
            "relationship_role": contract.relationship_role if contract else None,
            "boundary_scope": boundary.global_memory_read_scope if boundary else None,
            "companion_environment": companion.companion_environment,
            "provenance": companion.provenance,
        }


def ensure_companion_profiles(companion_id: uuid.UUID) -> None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion:
            return
        if _ensure_companion_profiles(s, companion):
            s.commit()


def _ensure_default_modes(s: Session, companion: Companion) -> None:
    default_modes = [
        ("project", "Project", True),
        ("creative", "Creative", True),
    ]
    for mode_key, display_name, is_enabled in default_modes:
        existing = s.execute(
            select(CompanionMode).where(
                CompanionMode.companion_id == companion.id,
                CompanionMode.mode_key == mode_key,
            )
        ).scalar_one_or_none()
        if not existing:
            s.add(
                CompanionMode(
                    companion_id=companion.id,
                    mode_key=mode_key,
                    display_name=display_name,
                    is_enabled=is_enabled,
                    description=f"Bootstrap mode for {display_name.lower()} work.",
                    config={},
                )
            )


def _ensure_companion_profiles(
    s: Session,
    companion: Companion,
    identity_data: dict[str, Any] | None = None,
    persona_data: dict[str, Any] | None = None,
    contract_data: dict[str, Any] | None = None,
    boundary_data: dict[str, Any] | None = None,
    visibility_data: dict[str, Any] | None = None,
) -> bool:
    created = False
    identity_data = identity_data or {}
    persona_data = persona_data or {}
    contract_data = contract_data or {}
    boundary_data = boundary_data or {}
    visibility_data = visibility_data or {}

    if _get_identity_profile(s, companion.id) is None:
        created = True
        s.add(
            CompanionIdentityProfile(
                user_id=companion.user_id,
                companion_id=companion.id,
                display_name=identity_data.get("display_name", companion.name),
                identity_summary=identity_data.get(
                    "identity_summary",
                    companion.identity_prompt or f"{companion.name} is a long-lived cyber companion.",
                ),
                origin_story=identity_data.get("origin_story"),
                self_continuity_summary=identity_data.get(
                    "self_continuity_summary",
                    f"{companion.name} persists across conversations and shared experiences.",
                ),
                core_traits_json=identity_data.get("core_traits_json", []),
                identity_labels_json=identity_data.get("identity_labels_json", ["companion", "persistent"]),
                voice_style_hint=identity_data.get("voice_style_hint"),
                avatar_style_hint=identity_data.get("avatar_style_hint"),
                profile_status=identity_data.get("profile_status", "active"),
            )
        )

    if _get_persona_profile(s, companion.id) is None:
        created = True
        s.add(
            CompanionPersonaProfile(
                user_id=companion.user_id,
                companion_id=companion.id,
                persona_summary=persona_data.get(
                    "persona_summary",
                    companion.base_personality or "A stable, long-term cyber companion persona.",
                ),
                communication_style_summary=persona_data.get("communication_style_summary"),
                tone_descriptors_json=persona_data.get(
                    "tone_descriptors_json",
                    list((companion.tone_profile or {}).keys()) if isinstance(companion.tone_profile, dict) else [],
                ),
                core_values_json=persona_data.get("core_values_json", []),
                response_preferences_json=persona_data.get("response_preferences_json", {}),
                persona_lock_level=persona_data.get("persona_lock_level", "guarded"),
                drift_guard_level=persona_data.get("drift_guard_level", "standard"),
                presence_style=persona_data.get("presence_style", "balanced"),
            )
        )

    if _get_contract_profile(s, companion.id) is None:
        created = True
        s.add(
            CompanionRelationshipContract(
                user_id=companion.user_id,
                companion_id=companion.id,
                relationship_role=contract_data.get("relationship_role", "companion"),
                contract_status=contract_data.get("contract_status", "active"),
                contract_summary=contract_data.get(
                    "contract_summary",
                    f"{companion.name} participates as a long-term cyber companion rather than a functional bot.",
                ),
                collaboration_style_summary=contract_data.get("collaboration_style_summary"),
                support_scope_json=contract_data.get("support_scope_json", []),
                shared_memory_policy=contract_data.get("shared_memory_policy", "candidate_review"),
                cross_companion_disclosure_policy=contract_data.get(
                    "cross_companion_disclosure_policy", "review_required"
                ),
                contract_json=contract_data.get("contract_json", {}),
            )
        )

    if _get_boundary_profile(s, companion.id) is None:
        created = True
        s.add(
            CompanionBoundaryProfile(
                user_id=companion.user_id,
                companion_id=companion.id,
                boundary_json=boundary_data.get("boundary_json", {}),
                private_memory_default=boundary_data.get("private_memory_default", "private_companion_only"),
                shared_memory_default=boundary_data.get("shared_memory_default", "candidate_review"),
                global_memory_read_scope=boundary_data.get("global_memory_read_scope", "low_risk_summary_only"),
                cross_companion_read_policy=boundary_data.get("cross_companion_read_policy", "blocked"),
                review_required_private_to_shared=boundary_data.get("review_required_private_to_shared", True),
                review_required_shared_to_private=boundary_data.get("review_required_shared_to_private", True),
                review_required_cross_companion_share=boundary_data.get("review_required_cross_companion_share", True),
                presence_interrupt_policy=boundary_data.get(
                    "presence_interrupt_policy", "respect_existing_boundary"
                ),
            )
        )

    if _get_visibility_policy(s, companion.id) is None:
        created = True
        s.add(
            CompanionVisibilityPolicy(
                user_id=companion.user_id,
                companion_id=companion.id,
                memory_visibility_policy=visibility_data.get("memory_visibility_policy", "scoped_summary"),
                user_global_memory_scope=visibility_data.get(
                    "user_global_memory_scope", "low_risk_summary_only"
                ),
                relationship_memory_scope=visibility_data.get("relationship_memory_scope", "contract_scoped"),
                allow_low_risk_summary_read=visibility_data.get("allow_low_risk_summary_read", True),
                allow_authorized_global_read=visibility_data.get("allow_authorized_global_read", True),
                allow_sensitive_global_read=visibility_data.get("allow_sensitive_global_read", False),
                allow_other_companion_private_read=visibility_data.get(
                    "allow_other_companion_private_read", False
                ),
                visibility_rules_json=visibility_data.get("visibility_rules_json", {}),
            )
        )
    return created


def _get_identity_profile(s: Session, companion_id: uuid.UUID) -> CompanionIdentityProfile | None:
    return s.execute(
        select(CompanionIdentityProfile).where(CompanionIdentityProfile.companion_id == companion_id)
    ).scalar_one_or_none()


def _get_persona_profile(s: Session, companion_id: uuid.UUID) -> CompanionPersonaProfile | None:
    return s.execute(
        select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion_id)
    ).scalar_one_or_none()


def _get_contract_profile(s: Session, companion_id: uuid.UUID) -> CompanionRelationshipContract | None:
    return s.execute(
        select(CompanionRelationshipContract).where(CompanionRelationshipContract.companion_id == companion_id)
    ).scalar_one_or_none()


def _get_boundary_profile(s: Session, companion_id: uuid.UUID) -> CompanionBoundaryProfile | None:
    return s.execute(
        select(CompanionBoundaryProfile).where(CompanionBoundaryProfile.companion_id == companion_id)
    ).scalar_one_or_none()


def _get_visibility_policy(s: Session, companion_id: uuid.UUID) -> CompanionVisibilityPolicy | None:
    return s.execute(
        select(CompanionVisibilityPolicy).where(CompanionVisibilityPolicy.companion_id == companion_id)
    ).scalar_one_or_none()


def _record_lifecycle_event(
    s: Session,
    *,
    companion_id: uuid.UUID,
    user_id: uuid.UUID,
    event_type: str,
    event_source: str,
    previous_state_json: dict[str, Any],
    new_state_json: dict[str, Any],
    review_required: bool,
    title: str | None = None,
    detail: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CompanionLifecycleEvent:
    event = CompanionLifecycleEvent(
        user_id=user_id,
        companion_id=companion_id,
        event_type=event_type,
        event_source=event_source,
        title=title,
        detail=detail,
        previous_state_json=previous_state_json,
        new_state_json=new_state_json,
        review_required=review_required,
        occurred_at=datetime.now(timezone.utc),
        metadata_=metadata or {},
    )
    s.add(event)
    return event


def _companion_to_dict(companion: Companion) -> dict[str, Any]:
    return {
        "id": str(companion.id),
        "user_id": str(companion.user_id),
        "name": companion.name,
        "subtitle": companion.subtitle,
        "identity_prompt": companion.identity_prompt,
        "base_personality": companion.base_personality,
        "tone_profile": companion.tone_profile or {},
        "companion_profile": companion.companion_profile or {},
        "current_mode": companion.current_mode,
        "current_status": companion.current_status,
        "current_focus": companion.current_focus,
        "companion_environment": companion.companion_environment,
        "provenance": companion.provenance,
        "created_at": companion.created_at.isoformat() if companion.created_at else None,
        "updated_at": companion.updated_at.isoformat() if companion.updated_at else None,
    }
