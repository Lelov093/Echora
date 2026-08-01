from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.presence_configuration import PresenceConfigurationUpdateRequest
from app.services import presence_configuration_service


NOW = datetime.now(timezone.utc)


def payload(**overrides):
    return {
        "expected_schedule_revision": None,
        "expected_policy_updated_at": None,
        "expected_persona_updated_at": NOW,
        "expected_boundary_updated_at": NOW,
        "enabled": False,
        "destination_mode": "bound_conversation",
        "bound_conversation_id": None,
        "timezone": "Asia/Shanghai",
        **overrides,
    }


def test_presence_configuration_allows_paused_unbound_but_requires_binding_when_enabled():
    paused = PresenceConfigurationUpdateRequest(**payload())
    assert paused.enabled is False
    with pytest.raises(ValidationError, match="bound_conversation_id"):
        PresenceConfigurationUpdateRequest(**payload(enabled=True))
    active = PresenceConfigurationUpdateRequest(
        **payload(enabled=True, bound_conversation_id=UUID(int=1))
    )
    assert active.enabled is True


def test_presence_configuration_rejects_ambiguous_quiet_and_random_windows():
    with pytest.raises(ValidationError, match="quiet hours"):
        PresenceConfigurationUpdateRequest(
            **payload(quiet_hours={"enabled": True, "start": "22:00", "end": "22:00"})
        )
    with pytest.raises(ValidationError, match="random delivery window"):
        PresenceConfigurationUpdateRequest(
            **payload(timing_mode="random_window", window_start_minute=120, window_end_minute=120)
        )


def test_presence_configuration_projection_fails_closed_for_historical_drift():
    companion = SimpleNamespace(id=UUID(int=1), user_id=UUID(int=2))
    policy = SimpleNamespace(
        updated_at=NOW,
        proactive_level="medium",
        notification_surface="hub_queue_only",
        allow_proactive_presence=True,
        quiet_hours={"enabled": True, "start": "23:00", "end": "08:00", "timezone": "Asia/Shanghai"},
        max_presence_per_day=3,
        min_presence_interval_minutes=120,
        meaningful_silence_enabled=True,
    )
    persona = SimpleNamespace(updated_at=NOW, presence_style="balanced")
    boundary = SimpleNamespace(
        updated_at=NOW,
        presence_interrupt_policy="user_initiated_only",
        boundary_json={"quiet_hours": {"enabled": False, "start": "22:00", "end": "07:00"}},
    )
    schedule = SimpleNamespace(
        status="active",
        revision=2,
        destination_mode="new_conversation_per_delivery",
        bound_conversation_id=None,
        timezone="Asia/Shanghai",
        weekdays=list(range(7)),
        timing_mode="fixed",
        fixed_minute_of_day=1200,
        window_start_minute=1140,
        window_end_minute=1320,
        cadence_mode="fixed",
        fixed_interval_minutes=1440,
        random_interval_min_minutes=1440,
        random_interval_max_minutes=4320,
        next_occurrence_at=None,
        last_delivered_at=None,
    )
    result = presence_configuration_service._configuration_dict(
        companion, policy, persona, boundary, schedule
    )
    assert result["configuration"]["enabled"] is False
    assert result["consistency"]["status"] == "needs_save_to_align"
    assert "policy_and_interrupt_boundary_differ" in result["consistency"]["warnings"]
    assert "quiet_hours_projection_differ" in result["consistency"]["warnings"]


def test_presence_configuration_versions_block_stale_partial_updates():
    policy = SimpleNamespace(updated_at=NOW)
    persona = SimpleNamespace(updated_at=NOW)
    boundary = SimpleNamespace(updated_at=NOW)
    presence_configuration_service._require_versions(
        policy=policy,
        persona=persona,
        boundary=boundary,
        expected_policy=NOW,
        expected_persona=NOW,
        expected_boundary=NOW,
    )
    with pytest.raises(
        presence_configuration_service.PresenceConfigurationError,
        match="changed elsewhere",
    ):
        presence_configuration_service._require_versions(
            policy=policy,
            persona=persona,
            boundary=boundary,
            expected_policy=None,
            expected_persona=NOW,
            expected_boundary=NOW,
        )


def test_presence_configuration_wraps_database_failures_and_rolls_back(monkeypatch):
    class FailingSession:
        rolled_back = False

        def execute(self, _statement):
            raise SQLAlchemyError("database rejected write")

        def rollback(self):
            self.rolled_back = True

    session = FailingSession()

    @contextmanager
    def failing_session():
        yield session

    monkeypatch.setattr(
        presence_configuration_service.presence_schedule_service,
        "get_session",
        failing_session,
    )

    with pytest.raises(presence_configuration_service.PresenceConfigurationError) as exc_info:
        presence_configuration_service.update_configuration(UUID(int=1), UUID(int=2), {})

    assert exc_info.value.code == "PRESENCE_CONFIGURATION_SAVE_FAILED"
    assert exc_info.value.details is None
    assert session.rolled_back is True
