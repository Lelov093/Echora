"""Companion companion identity and persona service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from app.db.models import (
    Companion,
    CompanionBoundaryProfile,
    CompanionIdentityProfile,
    CompanionPersonaProfile,
    CompanionRelationshipContract,
    CompanionVisibilityPolicy,
    CompanionPresenceOpportunity,
    PresenceOpportunity,
)
from app.schemas.companion_identity import (
    CompanionBoundaryProfileRead,
    CompanionIdentityProfileRead,
    CompanionPersonaProfileRead,
    CompanionRelationshipContractRead,
    CompanionVisibilityPolicyRead,
)
from app.services.companion_roster_service import (
    _record_lifecycle_event,
    _ensure_companion_profiles,
    get_session,
)


def _owner_settings_versions_match(profiles: dict[str, Any], payload: dict[str, Any]) -> bool:
    return all(profile.updated_at == payload[f"expected_{key}_updated_at"] for key, profile in profiles.items())


def get_identity(companion_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        if _ensure_companion_profiles(s, companion):
            s.commit()
        profile = s.execute(
            select(CompanionIdentityProfile).where(CompanionIdentityProfile.companion_id == companion_id)
        ).scalar_one()
        return CompanionIdentityProfileRead.model_validate(profile).model_dump(mode="json")


def patch_owner_settings(companion_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        _ensure_companion_profiles(s, companion)
        identity = s.execute(select(CompanionIdentityProfile).where(CompanionIdentityProfile.companion_id == companion_id)).scalar_one()
        persona = s.execute(select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion_id)).scalar_one()
        contract = s.execute(select(CompanionRelationshipContract).where(CompanionRelationshipContract.companion_id == companion_id)).scalar_one()
        boundary = s.execute(select(CompanionBoundaryProfile).where(CompanionBoundaryProfile.companion_id == companion_id)).scalar_one()
        profiles = {"identity": identity, "persona": persona, "contract": contract, "boundary": boundary}
        if not _owner_settings_versions_match(profiles, payload):
            raise ValueError("伙伴档案已在其他页面更新，请刷新后重新确认。")

        previous = {
            "identity": CompanionIdentityProfileRead.model_validate(identity).model_dump(mode="json"),
            "persona": CompanionPersonaProfileRead.model_validate(persona).model_dump(mode="json"),
            "contract": CompanionRelationshipContractRead.model_validate(contract).model_dump(mode="json"),
            "boundary": CompanionBoundaryProfileRead.model_validate(boundary).model_dump(mode="json"),
        }
        changed_fields: list[str] = []
        direct_fields = {
            "display_name": identity,
            "identity_summary": identity,
            "origin_story": identity,
            "self_continuity_summary": identity,
            "core_traits_json": identity,
            "identity_labels_json": identity,
            "persona_summary": persona,
            "communication_style_summary": persona,
            "tone_descriptors_json": persona,
            "core_values_json": persona,
            "presence_style": persona,
            "relationship_role": contract,
            "contract_summary": contract,
            "collaboration_style_summary": contract,
            "support_scope_json": contract,
            "presence_interrupt_policy": boundary,
        }
        for field, profile in direct_fields.items():
            if field in payload:
                setattr(profile, field, payload[field])
                changed_fields.append(field)
        if "display_name" in payload:
            companion.name = payload["display_name"]
        if "user_preferred_name" in payload:
            contract.contract_json = {**(contract.contract_json or {}), "user_preferred_name": payload["user_preferred_name"]}
            changed_fields.append("user_preferred_name")
        if "response_preferences_json" in payload:
            persona.response_preferences_json = {
                **(persona.response_preferences_json or {}),
                **payload["response_preferences_json"],
            }
            changed_fields.append("response_preferences_json")
        quiet_hours = dict((boundary.boundary_json or {}).get("quiet_hours") or {})
        for field, key in (("quiet_hours_enabled", "enabled"), ("quiet_hours_start", "start"), ("quiet_hours_end", "end")):
            if field in payload:
                quiet_hours[key] = payload[field]
                changed_fields.append(field)
        if quiet_hours:
            boundary.boundary_json = {**(boundary.boundary_json or {}), "quiet_hours": quiet_hours}

        now = datetime.now(timezone.utc)
        companion.updated_at = now
        for profile in profiles.values():
            profile.updated_at = now
        s.flush()
        current = {
            "identity": CompanionIdentityProfileRead.model_validate(identity).model_dump(mode="json"),
            "persona": CompanionPersonaProfileRead.model_validate(persona).model_dump(mode="json"),
            "contract": CompanionRelationshipContractRead.model_validate(contract).model_dump(mode="json"),
            "boundary": CompanionBoundaryProfileRead.model_validate(boundary).model_dump(mode="json"),
        }
        _record_lifecycle_event(
            s,
            companion_id=companion.id,
            user_id=companion.user_id,
            event_type="relationship_contract_initialized",
            event_source="user",
            title="主人翁设置已更新",
            detail="用户直接配置的身份表达、关系意图与陪伴边界已同步保存。",
            previous_state_json=previous,
            new_state_json=current,
            review_required=False,
            metadata={"implementation_origin": "companion_profile", "surface": "owner_settings", "changed_fields": changed_fields},
        )
        s.commit()
        return current


def set_companion_archived(
    companion_id: uuid.UUID, expected_identity_updated_at: datetime, *, archived: bool, confirmed: bool,
) -> dict[str, Any] | None:
    if not confirmed:
        raise ValueError("必须确认历史保留与边界状态后才能继续。")
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        _ensure_companion_profiles(s, companion)
        identity = s.execute(select(CompanionIdentityProfile).where(CompanionIdentityProfile.companion_id == companion_id)).scalar_one()
        if identity.updated_at != expected_identity_updated_at:
            raise ValueError("伙伴生命周期已在其他页面更新，请刷新后重新确认。")
        target = "archived" if archived else "active"
        if identity.profile_status == target:
            raise ValueError("伙伴已经处于目标生命周期状态。")
        previous = {"profile_status": identity.profile_status, "current_status": companion.current_status}
        identity.profile_status = target
        companion.current_status = "archived" if archived else "idle"
        now = datetime.now(timezone.utc)
        identity.updated_at = now
        companion.updated_at = now
        if archived:
            s.execute(update(PresenceOpportunity).where(PresenceOpportunity.companion_id == companion_id, PresenceOpportunity.status.in_(["queued", "shown", "snoozed"])).values(status="suppressed", user_action="companion_archived", updated_at=now))
            s.execute(update(CompanionPresenceOpportunity).where(CompanionPresenceOpportunity.companion_id == companion_id, CompanionPresenceOpportunity.opportunity_status.in_(["queued", "shown", "snoozed"])).values(opportunity_status="suppressed", updated_at=now))
        current = {"profile_status": target, "current_status": companion.current_status}
        _record_lifecycle_event(
            s, companion_id=companion.id, user_id=companion.user_id,
            event_type="identity_profile_initialized", event_source="user",
            title="伙伴已归档" if archived else "伙伴已恢复",
            detail="历史对话、记忆、共同历程与审计继续保留；归档期间 Presence 与渠道外发被阻断。" if archived else "已重新确认边界与渠道状态；旧的 Presence 队列不会自动恢复。",
            previous_state_json=previous, new_state_json=current, review_required=False,
            metadata={"implementation_origin": "companion_profile", "surface": "lifecycle", "action": target},
        )
        s.commit()
        return current


def patch_identity(companion_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        _ensure_companion_profiles(s, companion)
        profile = s.execute(
            select(CompanionIdentityProfile).where(CompanionIdentityProfile.companion_id == companion_id)
        ).scalar_one()
        previous = CompanionIdentityProfileRead.model_validate(profile).model_dump(mode="json")
        for field in [
            "display_name",
            "identity_summary",
            "origin_story",
            "self_continuity_summary",
            "core_traits_json",
            "identity_labels_json",
            "voice_style_hint",
            "avatar_style_hint",
            "profile_status",
        ]:
            if field in payload and payload[field] is not None:
                setattr(profile, field, payload[field])
        profile.updated_at = datetime.now(timezone.utc)
        if "display_name" in payload and payload["display_name"]:
            companion.name = payload["display_name"]
            companion.updated_at = datetime.now(timezone.utc)
        s.flush()
        _record_lifecycle_event(
            s,
            companion_id=companion.id,
            user_id=companion.user_id,
            event_type="identity_profile_initialized",
            event_source="api",
            title="Identity profile updated",
            detail="Companion identity fields changed",
            previous_state_json=previous,
            new_state_json=CompanionIdentityProfileRead.model_validate(profile).model_dump(mode="json"),
            review_required=False,
            metadata={"implementation_origin": "companion_profile", "surface": "identity"},
        )
        s.commit()
        return CompanionIdentityProfileRead.model_validate(profile).model_dump(mode="json")


def get_persona(companion_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        if _ensure_companion_profiles(s, companion):
            s.commit()
        profile = s.execute(
            select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion_id)
        ).scalar_one()
        return CompanionPersonaProfileRead.model_validate(profile).model_dump(mode="json")


def patch_persona(companion_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        _ensure_companion_profiles(s, companion)
        profile = s.execute(
            select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion_id)
        ).scalar_one()
        previous = CompanionPersonaProfileRead.model_validate(profile).model_dump(mode="json")
        for field in [
            "persona_summary",
            "communication_style_summary",
            "tone_descriptors_json",
            "core_values_json",
            "response_preferences_json",
            "persona_lock_level",
            "drift_guard_level",
            "presence_style",
        ]:
            if field in payload and payload[field] is not None:
                setattr(profile, field, payload[field])
        profile.updated_at = datetime.now(timezone.utc)
        s.flush()
        _record_lifecycle_event(
            s,
            companion_id=companion.id,
            user_id=companion.user_id,
            event_type="persona_profile_initialized",
            event_source="api",
            title="Persona profile updated",
            detail="Persona changes recorded for drift-safe evolution",
            previous_state_json=previous,
            new_state_json=CompanionPersonaProfileRead.model_validate(profile).model_dump(mode="json"),
            review_required=True,
            metadata={"implementation_origin": "companion_profile", "surface": "persona"},
        )
        s.commit()
        return CompanionPersonaProfileRead.model_validate(profile).model_dump(mode="json")


def get_visibility(companion_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        if _ensure_companion_profiles(s, companion):
            s.commit()
        policy = s.execute(select(CompanionVisibilityPolicy).where(CompanionVisibilityPolicy.companion_id == companion_id)).scalar_one()
        return CompanionVisibilityPolicyRead.model_validate(policy).model_dump(mode="json")


def patch_visibility(companion_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        _ensure_companion_profiles(s, companion)
        policy = s.execute(select(CompanionVisibilityPolicy).where(CompanionVisibilityPolicy.companion_id == companion_id)).scalar_one()
        previous = CompanionVisibilityPolicyRead.model_validate(policy).model_dump(mode="json")
        fields = ["memory_visibility_policy", "user_global_memory_scope", "relationship_memory_scope", "allow_low_risk_summary_read", "allow_authorized_global_read", "allow_sensitive_global_read", "allow_other_companion_private_read", "visibility_rules_json"]
        touched = {field for field in fields if field in payload and payload[field] is not None}
        for field in touched:
            setattr(policy, field, payload[field])
        policy.updated_at = datetime.now(timezone.utc)
        s.flush()
        _record_lifecycle_event(s, companion_id=companion.id, user_id=companion.user_id, event_type="visibility_policy_updated", event_source="api", title="Visibility policy updated", detail="Memory visibility and cross-companion access changes recorded", previous_state_json=previous, new_state_json=CompanionVisibilityPolicyRead.model_validate(policy).model_dump(mode="json"), review_required=bool(touched), metadata={"implementation_origin": "companion_profile", "surface": "visibility", "trace_required": bool(touched), "changed_fields": sorted(touched)})
        s.commit()
        return CompanionVisibilityPolicyRead.model_validate(policy).model_dump(mode="json")
