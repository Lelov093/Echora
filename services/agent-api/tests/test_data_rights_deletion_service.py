"""Focused tests for safe Companion deletion dependency planning."""

import app.db.models  # noqa: F401

from app.services import data_rights_deletion_service as service
from app.services import data_rights_export_service as export_service


def test_nullable_scope_constraint_is_not_treated_as_cycle() -> None:
    scoped = {"companions", "scoped_hard_stop_events"}

    assert service._cyclic_table_groups(scoped) == []
    assert service._child_first_order(scoped) == [
        "scoped_hard_stop_events",
        "companions",
    ]


def test_conversation_cycle_is_discovered_for_targeted_detachment() -> None:
    scoped = {
        "co_presence_sessions",
        "continuity_snapshots",
        "conversations",
        "feedback_events",
        "messages",
        "shared_scenes",
        "trace_runs",
    }

    groups = service._cyclic_table_groups(scoped)

    assert len(groups) == 1
    assert groups[0] == scoped
    # Once nullable cycle links are detached, the required message ->
    # conversation relationship still determines deletion order.
    order = service._child_first_order(scoped)
    assert order.index("messages") < order.index("conversations")


def test_export_recursively_redacts_secret_like_fields() -> None:
    value = {
        "query": "weather",
        "nested": {
            "api_key": "must-not-leak",
            "Authorization": "Bearer must-not-leak",
            "safe": ["visible", {"bot_token": "must-not-leak"}],
        },
    }

    assert export_service._safe_value(value) == {
        "query": "weather",
        "nested": {
            "api_key": "[redacted]",
            "Authorization": "[redacted]",
            "safe": ["visible", {"bot_token": "[redacted]"}],
        },
    }
