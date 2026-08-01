"""Atomic product-facing configuration for Companion Presence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import (
    BoundarySetting,
    Companion,
    CompanionBoundaryProfile,
    CompanionPersonaProfile,
    PresenceSchedule,
)
from app.services import presence_schedule_service
from app.services.companion_roster_service import _ensure_companion_profiles, _record_lifecycle_event


class PresenceConfigurationError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def get_configuration(user_id: uuid.UUID, companion_id: uuid.UUID) -> dict[str, Any]:
    with presence_schedule_service.get_session() as session:
        companion = _require_companion(session, user_id, companion_id)
        persona = session.execute(
            select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion_id)
        ).scalar_one_or_none()
        boundary = session.execute(
            select(CompanionBoundaryProfile).where(CompanionBoundaryProfile.companion_id == companion_id)
        ).scalar_one_or_none()
        if persona is None or boundary is None:
            raise PresenceConfigurationError(
                "PRESENCE_CONFIGURATION_PROFILE_MISSING",
                "The Companion profile is incomplete. Open the Companion profile before editing Presence.",
            )
        policy = session.execute(
            select(BoundarySetting).where(
                BoundarySetting.user_id == user_id,
                BoundarySetting.companion_id == companion_id,
            )
        ).scalar_one_or_none()
        schedule = session.execute(
            select(PresenceSchedule).where(
                PresenceSchedule.user_id == user_id,
                PresenceSchedule.companion_id == companion_id,
            )
        ).scalar_one_or_none()
        return _configuration_dict(companion, policy, persona, boundary, schedule)


def update_configuration(
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    data = dict(payload)
    with presence_schedule_service.get_session() as session:
        try:
            companion = session.execute(
                select(Companion).where(Companion.id == companion_id).with_for_update()
            ).scalar_one_or_none()
            if (
                companion is None
                or companion.deleted_at is not None
                or companion.user_id != user_id
            ):
                raise PresenceConfigurationError(
                    "PRESENCE_CONFIGURATION_SCOPE_MISMATCH",
                    "Companion not found for this owner.",
                )

            _ensure_companion_profiles(session, companion)
            session.flush()
            persona = session.execute(
                select(CompanionPersonaProfile)
                .where(CompanionPersonaProfile.companion_id == companion_id)
                .with_for_update()
            ).scalar_one()
            boundary = session.execute(
                select(CompanionBoundaryProfile)
                .where(CompanionBoundaryProfile.companion_id == companion_id)
                .with_for_update()
            ).scalar_one()
            policy = session.execute(
                select(BoundarySetting)
                .where(
                    BoundarySetting.user_id == user_id,
                    BoundarySetting.companion_id == companion_id,
                )
                .with_for_update()
            ).scalar_one_or_none()

            expected_policy = data.pop("expected_policy_updated_at")
            expected_persona = data.pop("expected_persona_updated_at")
            expected_boundary = data.pop("expected_boundary_updated_at")
            expected_schedule = data.pop("expected_schedule_revision")
            _require_versions(
                policy=policy,
                persona=persona,
                boundary=boundary,
                expected_policy=expected_policy,
                expected_persona=expected_persona,
                expected_boundary=expected_boundary,
            )

            previous = _audit_projection(policy, persona, boundary)
            enabled = bool(data["enabled"])
            quiet_input = dict(data["quiet_hours"])
            quiet = {**quiet_input, "timezone": data["timezone"]}
            cadence_floor = (
                data["fixed_interval_minutes"]
                if data["cadence_mode"] == "fixed"
                else data["random_interval_min_minutes"]
            )

            if policy is None:
                policy = BoundarySetting(user_id=user_id, companion_id=companion_id)
                session.add(policy)
            policy.proactive_level = data["proactive_level"]
            policy.notification_surface = data["notification_surface"]
            policy.allow_proactive_presence = enabled
            policy.quiet_hours = quiet
            policy.max_presence_per_day = data["max_presence_per_day"]
            policy.min_presence_interval_minutes = cadence_floor
            policy.meaningful_silence_enabled = data["meaningful_silence_enabled"]
            policy.updated_at = now

            persona.presence_style = data["presence_style"]
            persona.updated_at = now
            boundary.presence_interrupt_policy = (
                "respect_existing_boundary" if enabled else "user_initiated_only"
            )
            boundary.boundary_json = {
                **(boundary.boundary_json or {}),
                "quiet_hours": quiet,
            }
            boundary.updated_at = now
            companion.updated_at = now

            schedule_payload = {
                "expected_revision": expected_schedule,
                "status": "active" if enabled else "paused",
                "destination_mode": data["destination_mode"],
                "bound_conversation_id": data["bound_conversation_id"],
                "timezone": data["timezone"],
                "weekdays": data["weekdays"],
                "timing_mode": data["timing_mode"],
                "fixed_minute_of_day": data["fixed_minute_of_day"],
                "window_start_minute": data["window_start_minute"],
                "window_end_minute": data["window_end_minute"],
                "cadence_mode": data["cadence_mode"],
                "fixed_interval_minutes": data["fixed_interval_minutes"],
                "random_interval_min_minutes": data["random_interval_min_minutes"],
                "random_interval_max_minutes": data["random_interval_max_minutes"],
            }
            schedule = presence_schedule_service.upsert_schedule_in_session(
                session,
                user_id,
                companion_id,
                schedule_payload,
                now=now,
            )
            session.flush()
            current = _audit_projection(policy, persona, boundary)
            _record_lifecycle_event(
                session,
                companion_id=companion_id,
                user_id=user_id,
                # The lifecycle table intentionally has a closed event vocabulary.
                # Product-setting updates reuse the existing user-governed event and
                # are distinguished by metadata instead of widening the DB contract.
                event_type="relationship_contract_initialized",
                event_source="user",
                title="Presence 设置已更新",
                detail="主动联系、时间、频率与边界通过统一配置入口原子保存。",
                previous_state_json=previous,
                new_state_json=current,
                review_required=False,
                metadata={
                    "surface": "presence_configuration",
                    "contract_version": "presence-configuration.v1",
                    "schedule_revision": schedule.revision,
                },
            )
            session.commit()
            session.refresh(policy)
            session.refresh(persona)
            session.refresh(boundary)
            session.refresh(schedule)
            return _configuration_dict(companion, policy, persona, boundary, schedule)
        except PresenceConfigurationError:
            session.rollback()
            raise
        except presence_schedule_service.PresenceScheduleError as exc:
            session.rollback()
            raise PresenceConfigurationError(exc.code, exc.message, exc.details) from exc
        except SQLAlchemyError as exc:
            session.rollback()
            raise PresenceConfigurationError(
                "PRESENCE_CONFIGURATION_SAVE_FAILED",
                "Presence settings could not be saved. No changes were applied.",
            ) from exc


def _require_companion(session: Session, user_id: uuid.UUID, companion_id: uuid.UUID) -> Companion:
    companion = session.get(Companion, companion_id)
    if companion is None or companion.deleted_at is not None or companion.user_id != user_id:
        raise PresenceConfigurationError(
            "PRESENCE_CONFIGURATION_SCOPE_MISMATCH",
            "Companion not found for this owner.",
        )
    return companion


def _require_versions(
    *,
    policy: BoundarySetting | None,
    persona: CompanionPersonaProfile,
    boundary: CompanionBoundaryProfile,
    expected_policy: datetime | None,
    expected_persona: datetime,
    expected_boundary: datetime,
) -> None:
    policy_matches = (
        (policy is None and expected_policy is None)
        or (policy is not None and policy.updated_at == expected_policy)
    )
    if not policy_matches or persona.updated_at != expected_persona or boundary.updated_at != expected_boundary:
        raise PresenceConfigurationError(
            "PRESENCE_CONFIGURATION_VERSION_CONFLICT",
            "Presence settings changed elsewhere. Refresh before saving again.",
            {
                "policy_updated_at": policy.updated_at.isoformat() if policy and policy.updated_at else None,
                "persona_updated_at": persona.updated_at.isoformat(),
                "boundary_updated_at": boundary.updated_at.isoformat(),
            },
        )


def _configuration_dict(
    companion: Companion,
    policy: BoundarySetting | None,
    persona: CompanionPersonaProfile,
    boundary: CompanionBoundaryProfile,
    schedule: PresenceSchedule | None,
) -> dict[str, Any]:
    schedule_values = _schedule_values(schedule)
    policy_quiet = dict(policy.quiet_hours or {}) if policy else {}
    profile_quiet = dict((boundary.boundary_json or {}).get("quiet_hours") or {})
    quiet = policy_quiet or profile_quiet
    warnings: list[str] = []
    schedule_active = schedule is not None and schedule.status == "active"
    policy_allowed = policy.allow_proactive_presence if policy else True
    boundary_allows = boundary.presence_interrupt_policy not in {"user_initiated_only", "silent_only"}
    if schedule is not None and schedule_active != policy_allowed:
        warnings.append("schedule_and_policy_activation_differ")
    if policy_allowed != boundary_allows:
        warnings.append("policy_and_interrupt_boundary_differ")
    if policy_quiet and profile_quiet and _quiet_projection(policy_quiet) != _quiet_projection(profile_quiet):
        warnings.append("quiet_hours_projection_differ")
    if quiet.get("timezone") and quiet.get("timezone") != schedule_values["timezone"]:
        warnings.append("quiet_hours_timezone_differs")
    cadence_floor = (
        schedule_values["fixed_interval_minutes"]
        if schedule_values["cadence_mode"] == "fixed"
        else schedule_values["random_interval_min_minutes"]
    )
    if policy and policy.min_presence_interval_minutes not in {None, cadence_floor}:
        warnings.append("policy_interval_differs_from_schedule")

    proactive_level = policy.proactive_level if policy and policy.proactive_level in {"low", "medium", "high"} else "medium"
    if policy and policy.proactive_level == "off":
        warnings.append("proactive_level_off_migrated")
    enabled = schedule_active and policy_allowed and boundary_allows
    return {
        "contract_version": "presence-configuration.v1",
        "user_id": str(companion.user_id),
        "companion_id": str(companion.id),
        "versions": {
            "schedule_revision": schedule.revision if schedule else None,
            "policy_updated_at": policy.updated_at.isoformat() if policy and policy.updated_at else None,
            "persona_updated_at": persona.updated_at.isoformat(),
            "boundary_updated_at": boundary.updated_at.isoformat(),
        },
        "configuration": {
            "enabled": enabled,
            "proactive_level": proactive_level,
            "presence_style": persona.presence_style,
            "notification_surface": policy.notification_surface if policy else "hub_queue_only",
            "meaningful_silence_enabled": policy.meaningful_silence_enabled if policy else True,
            "quiet_hours": {
                "enabled": bool(quiet.get("enabled", True)),
                "start": str(quiet.get("start") or "23:00"),
                "end": str(quiet.get("end") or "08:00"),
            },
            "max_presence_per_day": policy.max_presence_per_day if policy and policy.max_presence_per_day is not None else 3,
            **schedule_values,
        },
        "runtime": {
            "next_occurrence_at": schedule.next_occurrence_at.isoformat() if schedule and schedule.next_occurrence_at else None,
            "last_delivered_at": schedule.last_delivered_at.isoformat() if schedule and schedule.last_delivered_at else None,
        },
        "consistency": {
            "status": "aligned" if not warnings else "needs_save_to_align",
            "warnings": warnings,
            "canonical_quiet_hours_source": "boundary_settings",
            "derived_profile_projection": True,
            "derived_min_interval_from_schedule": True,
        },
    }


def _schedule_values(schedule: PresenceSchedule | None) -> dict[str, Any]:
    if schedule is None:
        return {
            "destination_mode": "bound_conversation",
            "bound_conversation_id": None,
            "timezone": "UTC",
            "weekdays": list(range(7)),
            "timing_mode": "fixed",
            "fixed_minute_of_day": 1200,
            "window_start_minute": 1140,
            "window_end_minute": 1320,
            "cadence_mode": "fixed",
            "fixed_interval_minutes": 1440,
            "random_interval_min_minutes": 1440,
            "random_interval_max_minutes": 4320,
        }
    return {
        "destination_mode": schedule.destination_mode,
        "bound_conversation_id": str(schedule.bound_conversation_id) if schedule.bound_conversation_id else None,
        "timezone": schedule.timezone,
        "weekdays": list(schedule.weekdays or []),
        "timing_mode": schedule.timing_mode,
        "fixed_minute_of_day": schedule.fixed_minute_of_day,
        "window_start_minute": schedule.window_start_minute,
        "window_end_minute": schedule.window_end_minute,
        "cadence_mode": schedule.cadence_mode,
        "fixed_interval_minutes": schedule.fixed_interval_minutes,
        "random_interval_min_minutes": schedule.random_interval_min_minutes,
        "random_interval_max_minutes": schedule.random_interval_max_minutes,
    }


def _quiet_projection(value: dict[str, Any]) -> tuple[bool, str, str, str]:
    return (
        bool(value.get("enabled", True)),
        str(value.get("start") or "23:00"),
        str(value.get("end") or "08:00"),
        str(value.get("timezone") or ""),
    )


def _audit_projection(
    policy: BoundarySetting | None,
    persona: CompanionPersonaProfile,
    boundary: CompanionBoundaryProfile,
) -> dict[str, Any]:
    return {
        "allow_proactive_presence": policy.allow_proactive_presence if policy else None,
        "proactive_level": policy.proactive_level if policy else None,
        "notification_surface": policy.notification_surface if policy else None,
        "quiet_hours": dict(policy.quiet_hours or {}) if policy else {},
        "max_presence_per_day": policy.max_presence_per_day if policy else None,
        "min_presence_interval_minutes": policy.min_presence_interval_minutes if policy else None,
        "meaningful_silence_enabled": policy.meaningful_silence_enabled if policy else None,
        "presence_style": persona.presence_style,
        "presence_interrupt_policy": boundary.presence_interrupt_policy,
    }
