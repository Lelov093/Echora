import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.agents.providers import openai_compatible
from app.agents.providers.base import LLMProviderCancelled
from app.agents.graphs import conversation_graph
from app.agents.nodes import post_turn_effects_node
from app.agents.nodes import response_generation_node
from app.agents.nodes import trace_logging_node
from app.api.routes import conversations as conversation_routes
from app.schemas.conversation_crud import ConversationTurnStartRequest
from app.services import (
    conversation_application_service,
    conversation_post_turn_runtime_service,
    conversation_turn_event_service,
    conversation_turn_journal_service,
    conversation_turn_runtime_service,
    post_turn_effects_service,
)


def _context():
    return conversation_application_service.ConversationTurnContext(
        conversation_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        companion_id=uuid.uuid4(),
        mode_key="daily",
    )


def test_reasoning_mode_is_part_of_durable_turn_identity():
    conversation_id = uuid.uuid4()
    companion_id = uuid.uuid4()

    auto_hash = conversation_turn_journal_service._turn_request_hash(
        conversation_id, companion_id, "daily", "auto", "hello", None,
    )
    thinking_hash = conversation_turn_journal_service._turn_request_hash(
        conversation_id, companion_id, "daily", "thinking", "hello", None,
    )

    assert auto_hash != thinking_hash


def test_accept_turn_persists_async_claim_without_running_graph(monkeypatch):
    context = _context()
    claim = conversation_turn_journal_service.ConversationTurnClaim(
        "turn-key",
        uuid.uuid4(),
        uuid.uuid4(),
        transport_mode="async_web",
    )
    captured = {}
    monkeypatch.setattr(
        conversation_application_service,
        "_resolve_turn_context",
        lambda _command: context,
    )

    def claim_turn(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return claim

    monkeypatch.setattr(conversation_application_service, "_claim_turn", claim_turn)
    monkeypatch.setattr(
        conversation_application_service.conversation_turn_journal_service,
        "get_turn_status",
        lambda **_kwargs: {
            "trace_run_id": str(claim.trace_run_id),
            "status": "accepted",
        },
    )
    monkeypatch.setattr(
        conversation_application_service,
        "execute_agent_turn",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Graph must not run during acceptance")),
    )

    status = conversation_application_service.accept_conversation_turn(
        conversation_application_service.ConversationTurnCommand(
            conversation_id=context.conversation_id,
            requested_companion_id=context.companion_id,
            content="  hello  ",
            idempotency_key="turn-key",
        )
    )

    assert status["status"] == "accepted"
    assert status["idempotent_replay"] is False
    assert captured["args"][1] == "hello"
    assert captured["kwargs"] == {
        "transport_mode": "async_web",
        "allow_incomplete_replay": True,
        "continuation_of_trace_run_id": None,
    }


def test_start_route_uses_typed_async_contract(monkeypatch):
    conversation_id = uuid.uuid4()
    companion_id = uuid.uuid4()
    captured = {}

    def accept(command):
        captured["command"] = command
        return {"trace_run_id": str(uuid.uuid4()), "status": "accepted"}

    monkeypatch.setattr(
        conversation_routes.conversation_application_service,
        "accept_conversation_turn",
        accept,
    )
    response = conversation_routes.start_conversation_turn(
        str(conversation_id),
        ConversationTurnStartRequest(
            companion_id=companion_id,
            content="hello",
            idempotency_key="client-key",
        ),
    )

    assert response["error"] is None
    assert response["data"]["status"] == "accepted"
    assert captured["command"].conversation_id == conversation_id
    assert captured["command"].requested_companion_id == companion_id
    assert captured["command"].transport_mode == "async_web"


def test_worker_executes_claimed_turn_without_creating_another_user_message(monkeypatch):
    context = _context()
    claim = conversation_turn_journal_service.ConversationTurnClaim(
        "turn-key",
        uuid.uuid4(),
        uuid.uuid4(),
        transport_mode="async_web",
    )
    captured = {}
    claims = iter([claim, None])
    monkeypatch.setattr(
        conversation_turn_runtime_service.conversation_turn_journal_service,
        "claim_next_async_turn",
        lambda **_kwargs: next(claims),
    )
    monkeypatch.setattr(
        conversation_turn_runtime_service,
        "_load_claim_context",
        lambda _trace_id: (context, "persisted content"),
    )
    monkeypatch.setattr(
        conversation_turn_runtime_service.conversation_application_service,
        "_execute_claimed_turn",
        lambda received_context, content, received_claim: captured.update(
            context=received_context,
            content=content,
            claim=received_claim,
        ),
    )

    processed = conversation_turn_runtime_service.run_scheduler_tick(
        worker_id="test-worker",
        max_items=2,
        lease_seconds=60,
    )

    assert processed == 1
    assert captured == {
        "context": context,
        "content": "persisted content",
        "claim": claim,
    }


def test_async_generation_releases_worker_after_durable_effect_enqueue(monkeypatch):
    context = _context()
    claim = conversation_turn_journal_service.ConversationTurnClaim(
        "turn-key",
        uuid.uuid4(),
        uuid.uuid4(),
        transport_mode="async_web",
        reasoning_mode="thinking",
    )
    captured = {}
    state = {
        "trace_run_id": str(claim.trace_run_id),
        "turn_idempotency_key": claim.idempotency_key,
        "assistant_message_id": str(uuid.uuid4()),
        "assistant_response": "answer",
        "provider_timing": {"total_ms": 10},
        "turn_stage_timings": [],
        "errors": [],
    }

    def execute(**kwargs):
        captured["agent_kwargs"] = kwargs
        return state

    monkeypatch.setattr(conversation_application_service, "execute_agent_turn", execute)
    monkeypatch.setattr(
        conversation_application_service,
        "project_conversation_turn",
        lambda *_args: {"turn": {}, "_run_errors": []},
    )
    monkeypatch.setattr(
        conversation_application_service,
        "_store_turn_response",
        lambda trace_id, result: captured.update(stored=(trace_id, result)),
    )
    monkeypatch.setattr(
        conversation_application_service.post_turn_effects_service,
        "enqueue_job",
        lambda trace_id, received_state, planned_effects: captured.update(
            enqueued=(trace_id, received_state, planned_effects)
        ),
    )
    monkeypatch.setattr(
        conversation_application_service.conversation_turn_journal_service,
        "finalize_turn_runtime",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("generation worker must not wait for Post-turn completion")
        ),
    )

    result = conversation_application_service._execute_claimed_turn(
        context,
        "hello",
        claim,
    )

    assert result["_run_errors"] == []
    assert captured["agent_kwargs"]["stream_response"] is True
    assert captured["agent_kwargs"]["defer_post_turn_effects"] is True
    assert captured["agent_kwargs"]["reasoning_mode"] == "thinking"
    assert captured["enqueued"][0] == claim.trace_run_id
    assert captured["enqueued"][1] is state
    assert "affect" in captured["enqueued"][2]
    assert "context_documents" in captured["enqueued"][2]


def test_graph_defers_only_successful_async_post_turn_work():
    assert conversation_graph._route_after_response_generation({
        "defer_post_turn_effects": True,
        "errors": [],
    }) == "deferred"
    assert conversation_graph._route_after_response_generation({
        "defer_post_turn_effects": False,
        "errors": [],
    }) == "completed"
    assert conversation_graph._route_after_response_generation({
        "defer_post_turn_effects": True,
        "errors": [{"step": "response_generation"}],
    }) == "failed"


def test_post_turn_scheduler_isolated_from_generation_worker(monkeypatch):
    claim = post_turn_effects_service.PostTurnJobClaim(
        uuid.uuid4(),
        attempt_count=1,
        resume_from="queued",
    )
    claims = iter([claim, None])
    processed = []
    monkeypatch.setattr(
        conversation_post_turn_runtime_service.post_turn_effects_service,
        "claim_next_job",
        lambda **_kwargs: next(claims),
    )
    monkeypatch.setattr(
        conversation_post_turn_runtime_service,
        "_execute_claimed_job",
        lambda received: processed.append(received),
    )

    count = conversation_post_turn_runtime_service.run_scheduler_tick(
        worker_id="effects-worker",
        max_items=2,
        lease_seconds=60,
        max_attempts=3,
    )

    assert count == 1
    assert processed == [claim]


def test_post_turn_resume_after_effect_checkpoint_does_not_repeat_effects(monkeypatch):
    trace_run_id = uuid.uuid4()
    claim = post_turn_effects_service.PostTurnJobClaim(
        trace_run_id,
        attempt_count=1,
        resume_from="effects_completed",
    )
    state = {
        "trace_run_id": str(trace_run_id),
        "turn_idempotency_key": "turn-key",
        "user_input": "hello",
        "post_turn_effects": {},
        "turn_stage_timings": [],
        "provider_timing": {"total_ms": 10},
    }
    calls = []
    monkeypatch.setattr(
        conversation_post_turn_runtime_service.post_turn_effects_service,
        "load_journal",
        lambda _trace_id: {
            "status": "started",
            "recovery_state": state,
            "contract": {"status": "completed", "receipts": []},
        },
    )
    monkeypatch.setattr(
        conversation_post_turn_runtime_service,
        "run_post_turn_effects",
        lambda _state: (_ for _ in ()).throw(
            AssertionError("completed effects must not repeat")
        ),
    )
    monkeypatch.setattr(
        conversation_post_turn_runtime_service,
        "_trace_is_terminal",
        lambda _trace_id: True,
    )
    monkeypatch.setattr(
        conversation_post_turn_runtime_service.conversation_application_service,
        "project_conversation_turn",
        lambda *_args: {"turn": {}, "_run_errors": []},
    )
    monkeypatch.setattr(
        conversation_post_turn_runtime_service.conversation_turn_journal_service,
        "store_turn_response",
        lambda *_args, **_kwargs: calls.append("store"),
    )
    monkeypatch.setattr(
        conversation_post_turn_runtime_service.conversation_turn_journal_service,
        "finalize_turn_runtime",
        lambda *_args, **_kwargs: calls.append("finalize"),
    )
    monkeypatch.setattr(
        conversation_post_turn_runtime_service.post_turn_effects_service,
        "complete_job",
        lambda *_args, **_kwargs: calls.append("complete"),
    )
    monkeypatch.setattr(
        conversation_post_turn_runtime_service.conversation_turn_event_service,
        "publish",
        lambda *_args, **_kwargs: calls.append("publish"),
    )

    conversation_post_turn_runtime_service._execute_claimed_job(claim)

    assert calls == ["store", "finalize", "complete", "publish"]


def test_terminal_effect_failure_preserves_successful_response_truth():
    now = datetime.now(timezone.utc)
    trace = SimpleNamespace(status="started", completed_at=None)
    metadata = {
        "turn_transport": {
            "mode": "async_web",
            "lifecycle_status": "effects_processing",
        },
        "turn_response_json": {
            "assistant_message": {"id": str(uuid.uuid4())},
            "turn": {"response": {"status": "persisted"}},
        },
        "post_turn_effects": {
            "contract_version": post_turn_effects_service.CONTRACT_VERSION,
            "status": "partial_failed",
            "receipts": [{"effect": "affect", "status": "failed"}],
        },
    }
    job = {
        "contract_version": post_turn_effects_service.JOB_CONTRACT_VERSION,
        "status": "running",
        "attempt_count": 3,
        "lease": {"worker_id": "worker"},
    }

    post_turn_effects_service._set_terminal_job_failure(
        trace,
        metadata,
        job,
        code="POST_TURN_RUNTIME_FAILED",
        now=now,
    )

    assert trace.status == "completed"
    assert metadata["turn_transport"]["lifecycle_status"] == "completed"
    assert metadata["turn_transport"]["post_turn_failure"]["code"] == "POST_TURN_RUNTIME_FAILED"
    assert metadata["turn_response_json"]["assistant_message"]["id"]
    assert metadata["turn_response_json"]["turn"]["response"]["status"] == "persisted"
    assert metadata["turn_response_json"]["post_turn_effects"]["status"] == "partial_failed"
    assert job["status"] == "failed"
    assert job["lease"] == {}


def test_status_projection_exposes_safe_timing_without_payloads():
    trace = SimpleNamespace(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        companion_id=uuid.uuid4(),
    )
    user_message = SimpleNamespace(
        id=uuid.uuid4(), role="user", content="hello", content_format="text",
        model_provider=None, model_name=None, created_at=None,
    )
    transport = {
        "mode": "async_web",
        "lifecycle_status": "provider_waiting",
        "accepted_at": "2026-07-22T00:00:00+00:00",
        "stage_timings": [{"stage": "input", "elapsed_ms": 12}],
        "provider_timing": {
            "measurement_mode": "non_streaming_full_response",
            "total_ms": 800,
            "time_to_first_token_ms": None,
            "first_token_measurement_status": "unavailable_until_streaming",
        },
    }

    result = conversation_turn_journal_service._status_projection(
        trace,
        user_message,
        None,
        {"turn_idempotency_key": "turn-key"},
        transport,
    )

    assert result["status"] == "provider_waiting"
    assert result["provider_timing"]["time_to_first_token_ms"] is None
    assert "lease" not in result
    assert "metadata" not in result


def test_runtime_transition_contract_is_monotonic():
    transitions = conversation_turn_journal_service.TURN_RUNTIME_TRANSITIONS

    assert transitions["completed"] == set()
    assert transitions["failed"] == set()
    assert transitions["cancelled"] == set()
    assert "cancellation_requested" not in transitions["response_persisted"]
    assert "completed" in transitions["cancellation_requested"]


def test_provider_reports_full_response_timing_without_fake_first_token(monkeypatch):
    provider = openai_compatible.OpenAICompatibleProvider()
    provider._configured = True
    provider._api_key = "test-key"
    provider._base_url = "https://provider.invalid"
    provider._model = "test-model"

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "test-model",
                "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            }

    import httpx

    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: _Response())
    result = provider.generate("system", "user")

    assert result["provider_timing"]["measurement_mode"] == "non_streaming_full_response"
    assert result["provider_timing"]["total_ms"] >= 0
    assert result["provider_timing"]["time_to_first_token_ms"] is None
    assert result["provider_timing"]["first_token_measurement_status"] == "unavailable_until_streaming"


def test_provider_streams_real_deltas_and_measures_first_token(monkeypatch):
    provider = openai_compatible.OpenAICompatibleProvider()
    provider._configured = True
    provider._api_key = "test-key"
    provider._base_url = "https://provider.invalid"
    provider._model = "test-model"
    captured = {}

    class _StreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"你"}}]}'
            yield 'data: {"choices":[{"delta":{"content":"好"},"finish_reason":"stop"}]}'
            yield "data: [DONE]"

    import httpx

    def stream(*_args, **kwargs):
        captured["payload"] = kwargs["json"]
        return _StreamResponse()

    monkeypatch.setattr(httpx, "stream", stream)
    deltas = []
    result = provider.generate_stream(
        "system", "user", on_delta=deltas.append, should_cancel=lambda: False,
    )

    assert captured["payload"]["stream"] is True
    assert deltas == ["你", "好"]
    assert result["content"] == "你好"
    assert result["provider_timing"]["measurement_mode"] == "provider_sse_stream"
    assert result["provider_timing"]["first_token_measurement_status"] == "measured"


def test_provider_cancellation_closes_stream_with_only_observed_partial(monkeypatch):
    provider = openai_compatible.OpenAICompatibleProvider()
    provider._configured = True
    provider._api_key = "test-key"
    provider._base_url = "https://provider.invalid"
    checks = iter([False, False, True])

    class _StreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"partial"}}]}'
            yield 'data: {"choices":[{"delta":{"content":" hidden"}}]}'

    import httpx
    monkeypatch.setattr(httpx, "stream", lambda *_args, **_kwargs: _StreamResponse())

    with pytest.raises(LLMProviderCancelled) as caught:
        provider.generate_stream(
            "system", "user", on_delta=lambda _delta: None,
            should_cancel=lambda: next(checks),
        )

    assert caught.value.partial_content == "partial"


def test_cancelled_partial_is_persisted_once_and_skips_response_ready(monkeypatch):
    trace_run_id = uuid.uuid4()
    saved = []
    events = []

    class _CancelledProvider:
        provider_name = "openai_compatible"
        _model = "test-model"
        is_simulation = False

        def generate_stream(self, *_args, **_kwargs):
            raise LLMProviderCancelled("partial answer", timing={"measurement_mode": "provider_sse_stream"})

    monkeypatch.setattr(response_generation_node, "_get_provider", lambda: _CancelledProvider())
    monkeypatch.setattr(response_generation_node, "build_prompt", lambda _state: ("system", "user"))
    monkeypatch.setattr(response_generation_node, "create_message", lambda payload: saved.append(payload) or SimpleNamespace(id=uuid.uuid4()))
    monkeypatch.setattr(response_generation_node.conversation_turn_journal_service, "update_turn_lifecycle", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(response_generation_node.conversation_turn_event_service, "publish", lambda _trace, event, data: events.append((event, data)))
    monkeypatch.setattr(response_generation_node, "notify_response_ready", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("cancelled partial must not dispatch")))

    state = response_generation_node.response_generation_node({
        "user_id": str(uuid.uuid4()),
        "companion_id": str(uuid.uuid4()),
        "conversation_id": str(uuid.uuid4()),
        "trace_run_id": str(trace_run_id),
        "turn_idempotency_key": "turn-key",
        "stream_response": True,
    })

    assert len(saved) == 1
    assert saved[0]["metadata_"]["generation_status"] == "interrupted"
    assert state["turn_cancelled"] is True
    assert state["assistant_response"] == "partial answer"
    assert [event for event, _data in events] == ["response_persisted"]


def test_turn_event_stream_contains_transient_delta_without_retention():
    trace_run_id = uuid.uuid4()
    stream = conversation_turn_event_service.iter_sse_events(
        trace_run_id,
        {"trace_run_id": str(trace_run_id), "status": "provider_waiting", "result": {"private": "must-not-stream"}},
    )
    snapshot = next(stream)
    conversation_turn_event_service.publish(trace_run_id, "delta", {"delta": "token"})
    delta = next(stream)
    stream.close()

    assert "event: snapshot" in snapshot
    assert "must-not-stream" not in snapshot
    assert "event: delta" in delta
    assert '"delta": "token"' in delta
    assert trace_run_id not in conversation_turn_event_service._subscribers


def test_graph_stage_wrapper_records_real_timing_and_lifecycle(monkeypatch):
    trace_run_id = uuid.uuid4()
    lifecycle = []
    monkeypatch.setattr(
        conversation_graph.conversation_turn_journal_service,
        "update_turn_lifecycle",
        lambda received_id, status: lifecycle.append((received_id, status)),
    )
    wrapped = conversation_graph._timed_node(
        "response_generation",
        lambda state: {**state, "assistant_message_id": str(uuid.uuid4())},
        lifecycle_before="provider_waiting",
        lifecycle_after="response_persisted",
    )

    result = wrapped({"trace_run_id": str(trace_run_id), "errors": []})

    assert lifecycle == [
        (trace_run_id, "provider_waiting"),
        (trace_run_id, "response_persisted"),
    ]
    assert result["turn_stage_timings"][0]["stage"] == "response_generation"
    assert result["turn_stage_timings"][0]["elapsed_ms"] >= 0
    assert result["turn_stage_timings"][0]["status"] == "completed"


def test_post_turn_receipts_measure_each_domain_effect(monkeypatch):
    monkeypatch.setattr(
        post_turn_effects_node.post_turn_effects_service,
        "persist_checkpoint",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        post_turn_effects_node,
        "EFFECT_DEFINITIONS",
        (
            post_turn_effects_node.EffectDefinition(
                "memory_candidate",
                "review_gated",
                lambda state: state,
                lambda _state: [],
            ),
        ),
    )

    result = post_turn_effects_node.run_post_turn_effects({
        "trace_run_id": str(uuid.uuid4()),
        "turn_idempotency_key": "turn-key",
        "trace_steps": [],
        "post_turn_effect_errors": [],
        "companion_context_snapshot": {},
    })
    receipt = result["post_turn_effects"]["receipts"][0]

    assert receipt["started_at"]
    assert receipt["completed_at"]
    assert receipt["elapsed_ms"] >= 0


def test_trace_warning_is_normalized_without_losing_effect_payload():
    assert trace_logging_node._persisted_step_status("warning") == "completed"
    assert trace_logging_node._persisted_step_status("failed") == "failed"
