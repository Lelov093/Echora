"""Real-database contract checks for Work Block 0 read projections."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from app.services.companion_roster_service import list_companions
from app.services.companion_workspace_service import (
    get_chronicle,
    get_review_inbox,
    get_workspace,
    _workspace_continuity,
)


FORBIDDEN_AGGREGATE_KEYS = {
    "candidate_payload_json",
    "suggested_memory_content",
    "raw_content_ref",
    "raw_payload",
    "payload_json",
    "policy_json",
}


def _keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def test_two_companions_are_isolated_and_review_gated():
    companions = list_companions()
    assert len(companions) >= 2, "Work Block 0 acceptance requires two real Companions"

    for companion in companions[:2]:
        workspace = get_workspace(companion.id)
        chronicle = get_chronicle(companion.id, 100, 0)
        inbox = get_review_inbox(companion.id, 100, 0)

        assert workspace is not None and chronicle is not None and inbox is not None
        assert workspace["companion"]["id"] == str(companion.id)
        assert all(item["companion_id"] == str(companion.id) for item in chronicle["items"])
        assert all(item["companion_id"] == str(companion.id) for item in inbox["items"])
        assert workspace["boundary"]["cross_companion_read_policy"] == "blocked"
        assert workspace["boundary"]["private_to_shared_review_required"] is True
        assert workspace["boundary"]["shared_to_private_review_required"] is True
        assert workspace["boundary"]["cross_companion_review_required"] is True
        assert all(item["status"] in {"pending", "pending_review", "candidate"} for item in inbox["items"])
        if inbox["items"]:
            kind = inbox["items"][0]["kind"]
            filtered_inbox = get_review_inbox(companion.id, 8, 0, kind)
            assert filtered_inbox is not None
            assert filtered_inbox["counts"] == inbox["counts"]
            assert filtered_inbox["total"] == inbox["counts"][kind]
            assert all(item["kind"] == kind for item in filtered_inbox["items"])
        assert FORBIDDEN_AGGREGATE_KEYS.isdisjoint(_keys(workspace))
        assert FORBIDDEN_AGGREGATE_KEYS.isdisjoint(_keys(chronicle))
        assert FORBIDDEN_AGGREGATE_KEYS.isdisjoint(_keys(inbox))


def test_missing_companion_returns_no_projection():
    import uuid

    missing = uuid.uuid4()
    assert get_workspace(missing) is None
    assert get_chronicle(missing, 10, 0) is None
    assert get_review_inbox(missing, 10, 0) is None


def test_first_meeting_conversation_is_workspace_continuity_before_first_snapshot():
    updated_at = datetime.now(timezone.utc)
    conversation = SimpleNamespace(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        current_topic="认识彼此",
        current_goal="从双方确认的关系与边界开始",
        summary=None,
        continuity_state={"origin": "companion_creation"},
        updated_at=updated_at,
    )

    continuity = _workspace_continuity(None, conversation)

    assert continuity == {
        "conversation_id": "11111111-1111-4111-8111-111111111111",
        "current_topic": "认识彼此",
        "current_goal": "从双方确认的关系与边界开始",
        "current_phase": "first_meeting",
        "last_assistant_summary": None,
        "suggested_next_steps": ["从第一次相识开始"],
        "updated_at": updated_at,
    }
