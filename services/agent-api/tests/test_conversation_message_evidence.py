import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.db.models import Conversation, Message, ToolRun, TraceRun
from app.services import conversation_evidence_service, conversation_service


class _Scalars:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return _Scalars(self.rows)


class _Session:
    def __init__(self, objects, query_rows):
        self.objects = objects
        self.query_rows = list(query_rows)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, model, object_id):
        return self.objects.get((model, object_id))

    def execute(self, _statement):
        return _Result(self.query_rows.pop(0))


def _scoped_fixture():
    now = datetime.now(timezone.utc)
    conversation_id = uuid.uuid4()
    companion_id = uuid.uuid4()
    message_id = uuid.uuid4()
    trace_id = uuid.uuid4()
    memory_id = uuid.uuid4()
    tool_run_id = uuid.uuid4()
    task_run_id = uuid.uuid4()
    conversation = SimpleNamespace(
        id=conversation_id,
        companion_id=companion_id,
        deleted_at=None,
        retention_mode="standard",
        retention_expires_at=None,
        metadata_={},
        title="Long-running conversation",
        mode_key="daily",
        current_topic="A clear topic",
        current_goal="A clear goal",
    )
    message = SimpleNamespace(
        id=message_id,
        companion_id=companion_id,
        conversation_id=conversation_id,
        deleted_at=None,
        role="assistant",
        metadata_={"trace_run_id": str(trace_id), "generation_status": "completed"},
    )
    trace = SimpleNamespace(
        id=trace_id,
        companion_id=companion_id,
        conversation_id=conversation_id,
        agent_graph_name="conversation_graph",
        status="completed",
        model_provider="ark",
        model_name="model-a",
        input_summary="What did you use for this answer?",
        elapsed_ms=1240,
        metadata_={
            "provider_timing": {"total_ms": 1100, "secret": "must-not-leak"},
            "post_turn_effects": {
                "status": "completed",
                "receipts": [{"effect": "memory_candidate", "status": "completed", "elapsed_ms": 20, "payload": "private"}],
            },
        },
        selected_memory_ids=[memory_id],
        tool_run_ids=[tool_run_id],
        generated_memory_candidate_ids=[uuid.uuid4()],
        generated_growth_candidate_ids=[],
        generated_presence_opportunity_ids=[],
    )
    steps = [
        SimpleNamespace(step_name="memory_retrieval", step_order=3, status="completed", output_json={"candidates_retrieved": 4, "selected_count": 1, "excluded_count": 3, "boundary_exclusion_counts": {"other_companion": 3}, "raw_payload": "private"}, provider_json={}, decision=None),
        SimpleNamespace(step_name="context_pack", step_order=4, status="completed", output_json={"manifest": {"contract_version": "conversation_context_pack_v3", "recent_conversation": {"message_count": 6}, "sections": [
            {"name": "identity", "selected": True, "availability": "available", "freshness": {"status": "versioned"}},
            {"name": "room", "selected": False, "availability": "empty", "exclusion_reason": "source_empty"},
            {"name": "unknown_internal_section", "selected": True, "availability": "available"},
        ]}}, provider_json={}, decision=None),
        SimpleNamespace(step_name="response_generation", step_order=5, status="completed", output_json={"is_simulation": False}, provider_json={"provider_mode": "live", "provider_name": "ark", "model_name": "model-a", "raw_request": "private"}, decision=None),
        SimpleNamespace(step_name="conversation_task_runtime", step_order=44, status="completed", output_json={"task_run_id": str(task_run_id), "internal_plan": "private"}, provider_json={}, decision=None),
        SimpleNamespace(step_name="persona_guard", step_order=107, status="skipped", output_json={"reason": "no_companion_context"}, provider_json={}, decision=None),
    ]
    memory = SimpleNamespace(id=memory_id, companion_id=companion_id, deleted_at=None, summary="Safe memory summary", updated_at=now)
    tool_run = SimpleNamespace(
        id=tool_run_id,
        user_id=uuid.uuid4(),
        companion_id=companion_id,
        conversation_id=conversation_id,
        tool_definition_id=uuid.uuid4(),
        parent_tool_run_id=None,
        requested_by="conversation",
        trace_run_id=trace_id,
        capability="weather",
        status="succeeded",
        risk_level="low",
        permission_required=False,
        permission_granted=True,
        confirmation_required=False,
        confirmation_summary=None,
        input_json={"location": "Shanghai", "api_key": "must-not-leak"},
        output_json={"temperature_max_c": 28, "reasoning_content": "must-not-leak"},
        error_json={},
        evidence_refs=[{"type": "provider", "secret": "must-not-leak"}],
        attempt_count=1,
        max_attempts=3,
        timeout_seconds=20,
        terminal_reason=None,
        request_message_id=uuid.uuid4(),
        result_message_id=uuid.uuid4(),
        created_at=now,
        started_at=now,
        completed_at=now,
        elapsed_ms=300,
        deleted_at=None,
    )
    explanation = SimpleNamespace(id=uuid.uuid4(), dimension="trust", title="Trust", explanation="The relationship signal was reviewed.")
    session = _Session(
        {
            (Conversation, conversation_id): conversation,
            (Message, message_id): message,
            (TraceRun, trace_id): trace,
        },
        [steps, [tool_run], [memory], [explanation]],
    )
    return session, conversation_id, message_id, companion_id, tool_run_id, task_run_id


def test_message_evidence_is_scoped_and_uses_an_explicit_safe_projection(monkeypatch):
    session, conversation_id, message_id, companion_id, tool_run_id, task_run_id = _scoped_fixture()
    monkeypatch.setattr(conversation_service, "get_session", lambda: session)

    result = conversation_evidence_service.get_message_evidence(conversation_id, message_id, companion_id)

    assert result["contract_version"] == "conversation-message-evidence.v1"
    assert result["assistant_message_id"] == str(message_id)
    assert result["response"]["provider_mode"] == "live"
    assert result["context"]["memories"]["selected"][0]["summary"] == "Safe memory summary"
    assert result["context"]["memories"]["policy_mode"] == "shadow"
    assert result["context"]["pack"]["included_count"] == 1
    assert result["context"]["pack"]["input_summary"] == "What did you use for this answer?"
    assert result["context"]["pack"]["recent_message_count"] == 6
    assert result["context"]["pack"]["sections"][0]["label"] == "伙伴身份"
    assert result["context"]["pack"]["sections"][1]["explanation"] == "本轮没有可用内容"
    assert result["boundaries"] == []
    assert result["tools"]["run_count"] == 1
    assert result["tools"]["runs"][0]["output_json"] == {"temperature_max_c": 28}
    assert result["activity"]["tool_run_ids"] == [str(tool_run_id)]
    assert result["activity"]["task_run_id"] == str(task_run_id)
    assert result["post_turn"]["effects"] == [{"effect": "memory_candidate", "status": "completed", "elapsed_ms": 20}]
    assert result["workflow"]["version"] == "conversation-response-process.v1"
    assert [stage["key"] for stage in result["workflow"]["stages"]] == [
        "understand", "context", "memory", "action", "respond", "after_response",
    ]
    assert result["workflow"]["stages"][2]["summary"] == "找到 4 条可能相关的伙伴私有记忆，其中 1 条用于本轮回应。"
    assert "1 次工具活动" in result["workflow"]["stages"][3]["summary"]
    assert "1 条记忆候选" in result["workflow"]["stages"][-1]["summary"]
    serialized = repr(result)
    assert "must-not-leak" not in serialized
    assert "raw_payload" not in serialized
    assert "raw_request" not in serialized
    assert "no_companion_context" not in serialized
    assert "no_companion_context" not in serialized
    assert "执行受控步骤" not in serialized
    assert "skipped" not in serialized


def test_message_evidence_rejects_cross_companion_scope(monkeypatch):
    session, conversation_id, message_id, _companion_id, _tool_run_id, _task_run_id = _scoped_fixture()
    monkeypatch.setattr(conversation_service, "get_session", lambda: session)

    with pytest.raises(conversation_service.ConversationTurnError) as exc:
        conversation_evidence_service.get_message_evidence(conversation_id, message_id, uuid.uuid4())

    assert exc.value.code == "CONVERSATION_MESSAGE_EVIDENCE_NOT_FOUND"


def test_user_visible_workflow_omits_skipped_and_unused_internal_paths():
    workflow = conversation_evidence_service._user_visible_workflow(
        steps={"memory_retrieval": SimpleNamespace(status="skipped")},
        context_pack={
            "status": "available",
            "sections": [{"label": "伙伴身份", "included": True}],
        },
        retrieval={},
        boundaries=[],
        tool_runs=[],
        task_run_id=None,
        generation_status="completed",
        memory_candidate_count=0,
        growth_candidate_count=0,
        post_turn={},
    )

    assert [stage["key"] for stage in workflow["stages"]] == [
        "understand", "context", "respond", "after_response",
    ]
    assert workflow["stages"][-1]["summary"] == "没有形成需要你确认的新记忆或成长变化。"
    assert "skipped" not in repr(workflow)
