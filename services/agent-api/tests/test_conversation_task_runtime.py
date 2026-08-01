from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.agents.nodes.delegated_execution_planning_node import (
    delegated_execution_planning_node,
)
from app.agents.prompts.conversation_prompt import _task_context
from app.services import conversation_task_runtime_service as runtime
from app.services import tool_runtime_service
from app.tasks import planning


def _provider_payload(payload: str) -> dict:
    return {
        "content": payload,
        "provider": "test-provider",
        "model": "test-model",
        "usage": {"total_tokens": 17},
    }


def test_planner_gate_keeps_chat_and_single_tool_on_fast_path() -> None:
    assert planning.may_plan_task("今天有点累，陪我聊聊") is False
    assert planning.may_plan_task("查询上海今天的天气") is False
    assert planning.may_plan_task("先查询上海天气，然后换算 100 美元并验证结果") is True


def test_planner_rejects_schema_invalid_tool_plan(monkeypatch) -> None:
    monkeypatch.setattr(
        planning.OpenAICompatibleProvider,
        "generate",
        lambda *_args, **_kwargs: _provider_payload(
            """{"should_plan":true,"goal":"查天气并验证","steps":[
            {"title":"查天气","executor_type":"tool","capability":"weather",
             "arguments":{},"dependencies":[],"acceptance_criteria":["有天气"]},
            {"title":"验证","executor_type":"verify","capability":null,
             "arguments":{},"dependencies":[1],"acceptance_criteria":["证据完整"]}
            ]}"""
        ),
    )

    result = planning.plan_task("计划并执行查询天气，然后验证结果")

    assert result.should_plan is False
    assert result.rationale == "plan_requires_multiple_valid_steps"


def test_side_effect_plan_keeps_explicit_confirmation_gate(monkeypatch) -> None:
    monkeypatch.setattr(
        planning.OpenAICompatibleProvider,
        "generate",
        lambda *_args, **_kwargs: _provider_payload(
            """{"should_plan":true,"goal":"查天气后创建提醒","steps":[
            {"title":"查天气","executor_type":"tool","capability":"weather",
             "arguments":{"location":"上海"},"dependencies":[],"acceptance_criteria":["有结果"]},
            {"title":"建提醒","executor_type":"tool","capability":"reminder",
             "arguments":{"title":"带伞","due_at":"2026-07-29T08:00:00+08:00","timezone":"Asia/Shanghai"},
             "dependencies":[1],"acceptance_criteria":["提醒已创建"]}
            ]}"""
        ),
    )

    result = planning.plan_task("先查询上海天气，然后创建带伞提醒并验证")

    assert result.should_plan is True
    assert result.steps[1].confirmation_required is True
    assert result.steps[-1].executor_type == "verify"


def test_replan_invalid_retry_arguments_fail_closed_to_await_input(monkeypatch) -> None:
    monkeypatch.setattr(
        planning.OpenAICompatibleProvider,
        "generate",
        lambda *_args, **_kwargs: _provider_payload(
            """{"action":"retry","rationale":"repair","arguments":{},
            "goal":null,"acceptance_criteria":[]}"""
        ),
    )

    decision = planning.replan_step(
        goal="查询天气",
        step={
            "capability": "weather",
            "arguments": {"location": "上海"},
            "error": {"code": "PROVIDER_FAILED"},
        },
        completed_steps=[],
        trigger="structured_step_failure",
    )

    assert decision.action == "await_input"
    assert decision.arguments == {"location": "上海"}


def test_replan_goal_change_requires_explicit_user_correction(monkeypatch) -> None:
    monkeypatch.setattr(
        planning.OpenAICompatibleProvider,
        "generate",
        lambda *_args, **_kwargs: _provider_payload(
            """{"action":"retry","rationale":"goal correction",
            "arguments":{"location":"北京"},"goal":"改查北京天气",
            "acceptance_criteria":["北京天气有证据"]}"""
        ),
    )
    without_user = planning.replan_step(
        goal="查询上海天气",
        step={"capability": "weather", "arguments": {"location": "上海"}},
        completed_steps=[],
        trigger="structured_step_failure",
    )
    with_user = planning.replan_step(
        goal="查询上海天气",
        step={"capability": "weather", "arguments": {"location": "上海"}},
        completed_steps=[],
        trigger="user_goal_correction",
        user_input="把任务改为查询北京天气",
    )

    assert without_user.goal is None
    assert with_user.goal == "改查北京天气"


def test_dependency_repair_preserves_success_and_unblocks_only_dependents() -> None:
    succeeded = SimpleNamespace(
        step_order=1,
        status="succeeded",
        dependencies_json=[],
        error_json={},
        completed_at=object(),
    )
    repaired = SimpleNamespace(
        step_order=2,
        status="failed",
        dependencies_json=[1],
        error_json={"code": "FAILED"},
        completed_at=object(),
    )
    dependent = SimpleNamespace(
        step_order=3,
        status="blocked",
        dependencies_json=[2],
        error_json={"code": "TASK_DEPENDENCY_FAILED"},
        completed_at=object(),
    )

    runtime._reset_dependency_blocks([succeeded, repaired, dependent], 2)

    assert succeeded.status == "succeeded"
    assert dependent.status == "pending"
    assert dependent.error_json == {}
    assert dependent.completed_at is None


def test_pause_and_resume_are_monotonic_and_do_not_complete_work() -> None:
    task = SimpleNamespace(
        status="running",
        paused_at=None,
        stop_reason=None,
        revision=1,
    )

    runtime._pause_task(task, "user_paused")
    assert task.status == "paused"
    assert task.stop_reason == "user_paused"
    assert task.revision == 2

    runtime._resume_task(task)
    assert task.status == "ready"
    assert task.stop_reason is None
    assert task.revision == 3


def test_verifier_rejects_missing_structured_evidence() -> None:
    session = SimpleNamespace(added=[], add=lambda value: session.added.append(value))
    task = SimpleNamespace(trace_run_id=None)
    dependency = SimpleNamespace(
        step_order=1,
        status="succeeded",
        output_json={},
        evidence_refs=[],
        error_json={},
    )
    verifier = SimpleNamespace(
        id=None,
        step_order=2,
        attempt_count=0,
        acceptance_criteria_json=["必须有证据"],
        dependencies_json=[1],
        status="ready",
        output_json={},
        error_json={},
        evidence_refs=[],
        started_at=None,
        completed_at=None,
    )

    runtime._execute_verify_step(session, task, verifier, [dependency, verifier])

    assert verifier.status == "failed"
    assert verifier.error_json == {"code": "TASK_VERIFICATION_REJECTED"}
    assert session.added[0].verification_json["status"] == "rejected"


def test_task_context_never_duplicates_raw_step_output() -> None:
    context = runtime._safe_task_context({
        "id": "task-1",
        "goal": "完成任务",
        "status": "completed",
        "acceptance_state": "verified",
        "current_step_order": None,
        "steps": [{
            "order": 1,
            "title": "读取",
            "executor_type": "tool",
            "capability": "web_read",
            "status": "succeeded",
            "output": {"raw_html": "secret"},
            "error": {},
            "evidence_refs": [{"type": "tool_run", "id": "run-1"}],
        }],
        "budgets": {},
    })

    assert "output" not in context["steps"][0]
    assert context["steps"][0]["observation"] == {}
    assert context["steps"][0]["evidence_refs"] == [
        {"type": "tool_run", "id": "run-1"}
    ]
    assert context["reasoning_content_persisted"] is False


def test_durable_task_truth_suppresses_superseded_delegation_writer() -> None:
    state = {
        "user_input": "计划并执行这个任务",
        "task_run": {"id": "task-1", "status": "running"},
        "co_presence_session": {"id": "room-1"},
        "trace_steps": [],
    }

    delegated_execution_planning_node(state)

    assert state["delegation_intent"] == {}
    assert state["trace_steps"][-1]["reason"] == "durable_task_run_is_authoritative"


def test_task_prompt_receives_bounded_observation_without_raw_payload() -> None:
    rendered = _task_context({
        "task_run_id": "task-1",
        "goal": "compare",
        "status": "completed",
        "acceptance_state": "verified",
        "steps": [{
            "order": 1,
            "title": "weather",
            "status": "succeeded",
            "executor_type": "tool",
            "observation": {"location": "上海", "temperature_max_c": 30},
        }],
    })

    assert "location=上海" in rendered
    assert "temperature_max_c=30" in rendered
    assert "{'location':" not in rendered


def test_read_only_specialists_are_bounded_to_two_and_run_concurrently(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_provider(_system: str, prompt: str):
        calls.append(prompt)
        time.sleep(0.15)
        return {"ok": True, "output": {"summary": prompt}, "raw": {}}

    monkeypatch.setattr(runtime, "_call_research_provider", fake_provider)
    started = time.monotonic()
    results = runtime._run_research_jobs([
        ("system", "first"),
        ("system", "second"),
        ("system", "must-not-run"),
    ])
    elapsed = time.monotonic() - started

    assert [item["output"]["summary"] for item in results] == ["first", "second"]
    assert sorted(calls) == ["first", "second"]
    assert elapsed < 0.27


def test_task_run_lease_prevents_live_work_from_being_stolen() -> None:
    session = SimpleNamespace(flush=lambda: None)
    task = SimpleNamespace(lease_owner=None, lease_expires_at=None)

    assert runtime._claim_task_lease(session, task, "turn-a") is True
    assert runtime._claim_task_lease(session, task, "scheduler-b") is False

    task.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert runtime._claim_task_lease(session, task, "scheduler-b") is True
    runtime._release_task_lease(task, "turn-a")
    assert task.lease_owner == "scheduler-b"
    runtime._release_task_lease(task, "scheduler-b")
    assert task.lease_owner is None
    assert task.lease_expires_at is None


def test_low_risk_task_tool_exhausts_bounded_retry_before_reply(monkeypatch) -> None:
    run = SimpleNamespace(
        status="queued",
        attempt_count=0,
        max_attempts=3,
        confirmation_required=False,
        risk_level="low",
        requested_by="conversation",
        metadata_={},
        next_attempt_at=None,
    )
    session = SimpleNamespace(commit_count=0)
    session.commit = lambda: setattr(session, "commit_count", session.commit_count + 1)
    monkeypatch.setattr(
        tool_runtime_service,
        "_scope_context",
        lambda *_args: {"user_id": "u", "companion_id": "c", "conversation_id": "v"},
    )
    monkeypatch.setattr(tool_runtime_service, "_create_run", lambda *_args, **_kwargs: run)

    def execute(_session, current):
        current.attempt_count += 1
        current.status = "succeeded" if current.attempt_count == 3 else "retry_scheduled"

    monkeypatch.setattr(tool_runtime_service, "_execute_locked", execute)

    result = tool_runtime_service.execute_task_tool_step(
        session,
        {},
        capability="weather",
        arguments={"location": "任意地点"},
        task_step_id=uuid.uuid4(),
        attempt_number=1,
    )

    assert result.status == "succeeded"
    assert result.attempt_count == 3
    assert session.commit_count == 2
