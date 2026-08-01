"""ResponseGenerationNode — calls LLM provider, saves assistant message."""

import uuid
from datetime import datetime, timezone
from time import monotonic

from app.agents.state import ConversationAgentState
from app.agents.providers.base import LLMProviderCancelled, LLMProviderError
from app.agents.providers.openai_compatible import OpenAICompatibleProvider
from app.agents.providers.reasoning_policy import select_conversation_reasoning_policy
from app.agents.prompts.conversation_prompt import build_prompt
from app.services.conversation_service import create_message
from app.services.response_ready_hook_service import notify_response_ready
from app.services import conversation_turn_event_service, conversation_turn_journal_service


def _get_provider():
    # Provider configuration is small and must reflect the latest protected
    # local revision on the next turn without restarting the resident backend.
    return OpenAICompatibleProvider()


def response_generation_node(state: ConversationAgentState) -> ConversationAgentState:
    provider = _get_provider()
    system_prompt, user_prompt = build_prompt(state)
    state.setdefault("trace_steps", []).append({
        "step": "context_pack",
        "order": 48,
        "status": "completed",
        "manifest": state.get("context_pack_manifest", {}),
    })
    reasoning_policy = select_conversation_reasoning_policy(state)
    state["reasoning_policy"] = reasoning_policy
    provider_context = {"reasoning_policy": reasoning_policy}
    try:
        result = (
            provider.generate_stream(
                system_prompt,
                user_prompt,
                on_delta=_delta_publisher(state),
                should_cancel=_CancellationProbe(state.get("trace_run_id")),
                context=provider_context,
            )
            if state.get("stream_response")
            else provider.generate(system_prompt, user_prompt, provider_context)
        )
    except LLMProviderCancelled as exc:
        return _record_cancelled_response(state, provider, exc)
    except LLMProviderError as exc:
        state["assistant_response"] = ""
        state["provider_mode"] = "unavailable"
        state["provider_name"] = provider.provider_name
        state["model_name"] = None
        state["provider_timing"] = exc.timing
        state.setdefault("errors", []).append({
            "step": "response_generation",
            "code": exc.code,
            "message": str(exc),
            "details": exc.details,
        })
        state.setdefault("trace_steps", []).append({
            "step": "response_generation",
            "order": 5,
            "status": "failed",
            "provider_json": {
                "provider_mode": "unavailable",
                "provider_name": provider.provider_name,
                "error_code": exc.code,
                "provider_timing": state["provider_timing"],
                "reasoning_policy": reasoning_policy,
                **exc.details,
            },
        })
        return state

    response_text = result["content"]
    state["assistant_response"] = response_text
    state["provider_mode"] = "live"
    state["provider_name"] = result["provider"]
    state["model_name"] = result.get("model", "unknown")
    state["provider_timing"] = result.get("provider_timing", {})
    state.setdefault("warnings", []).extend(result.get("warnings", []))

    # Save assistant message
    uid = uuid.UUID(state["user_id"])
    cid = uuid.UUID(state["companion_id"])
    conv_id = uuid.UUID(state["conversation_id"])

    msg = create_message({
        "user_id": uid, "companion_id": cid, "conversation_id": conv_id,
        "role": "assistant", "content": response_text, "content_format": "markdown",
        "model_provider": result["provider"],
        "model_name": result.get("model"),
        "metadata_": {
            "trace_run_id": state.get("trace_run_id"),
            "turn_idempotency_key": state.get("turn_idempotency_key"),
            "room_turn_id": state.get("room_turn_id"),
            "room_turn_step_id": state.get("room_turn_step_id"),
            "generation_status": "completed",
            "reasoning_mode": reasoning_policy.get("requested_mode"),
            "reasoning_tier": result.get("reasoning_policy", reasoning_policy).get("applied_tier"),
        },
    })
    state["assistant_message_id"] = str(msg.id)
    if state.get("stream_response"):
        _publish_response_persisted(state, str(msg.id))

    dispatch_status = notify_response_ready({
        "user_id": state["user_id"],
        "companion_id": state["companion_id"],
        "conversation_id": state["conversation_id"],
        "user_message_id": state.get("user_message_id"),
        "assistant_message_id": str(msg.id),
        "content": response_text,
        "trace_run_id": state.get("trace_run_id"),
    })
    if dispatch_status == "dispatch_failed":
        state.setdefault("warnings", []).append("response_ready_dispatch_failed")

    state.setdefault("trace_steps", []).append({
        "step": "response_generation",
        "order": 5,
        "status": "completed",
        "provider": result["provider"],
        "is_simulation": provider.is_simulation,
        "response_ready_dispatch": dispatch_status,
        "provider_json": {
            "provider_mode": "live",
            "provider_name": result["provider"],
            "model_name": result.get("model"),
            "provider_timing": state["provider_timing"],
            "reasoning_policy": result.get("reasoning_policy", reasoning_policy),
        },
    })
    return state


class _CancellationProbe:
    def __init__(self, trace_run_id: str | None):
        self.trace_run_id = uuid.UUID(trace_run_id) if trace_run_id else None
        self.last_check = 0.0
        self.requested = False

    def __call__(self) -> bool:
        if self.requested or self.trace_run_id is None:
            return self.requested
        now = monotonic()
        if now - self.last_check < 0.2:
            return False
        self.last_check = now
        self.requested = conversation_turn_journal_service.is_cancellation_requested(
            self.trace_run_id,
        )
        return self.requested


def _delta_publisher(state: ConversationAgentState):
    trace_run_id = uuid.UUID(state["trace_run_id"])
    streaming_started = False

    def publish(delta: str) -> None:
        nonlocal streaming_started
        if not streaming_started:
            streaming_started = True
            updated = conversation_turn_journal_service.update_turn_lifecycle(
                trace_run_id,
                "streaming",
            )
            if updated:
                conversation_turn_event_service.publish(
                    trace_run_id,
                    "lifecycle",
                    {"status": "streaming"},
                )
        conversation_turn_event_service.publish(trace_run_id, "delta", {"delta": delta})

    return publish


def _record_cancelled_response(
    state: ConversationAgentState,
    provider: OpenAICompatibleProvider,
    exc: LLMProviderCancelled,
) -> ConversationAgentState:
    partial = exc.partial_content
    state["assistant_response"] = partial
    state["provider_mode"] = "live"
    state["provider_name"] = provider.provider_name
    state["model_name"] = getattr(provider, "_model", None)
    state["provider_timing"] = exc.timing
    state["turn_cancelled"] = True
    if partial:
        msg = create_message({
            "user_id": uuid.UUID(state["user_id"]),
            "companion_id": uuid.UUID(state["companion_id"]),
            "conversation_id": uuid.UUID(state["conversation_id"]),
            "role": "assistant",
            "content": partial,
            "content_format": "markdown",
            "model_provider": provider.provider_name,
            "model_name": state["model_name"],
            "metadata_": {
                "trace_run_id": state.get("trace_run_id"),
                "turn_idempotency_key": state.get("turn_idempotency_key"),
                "generation_status": "interrupted",
            },
        })
        state["assistant_message_id"] = str(msg.id)
    state.setdefault("errors", []).append({
        "step": "response_generation",
        "code": "CONVERSATION_TURN_CANCELLED",
        "message": "Generation was stopped by the user.",
        "details": {"partial_response_persisted": bool(partial)},
    })
    state.setdefault("trace_steps", []).append({
        "step": "response_generation",
        "order": 5,
        "status": "failed",
        "provider_json": {
            "provider_mode": "live",
            "provider_name": provider.provider_name,
            "generation_status": "interrupted",
            "partial_response_persisted": bool(partial),
            "provider_timing": exc.timing,
        },
    })
    if state.get("assistant_message_id"):
        _publish_response_persisted(state, state["assistant_message_id"])
    return state


def _publish_response_persisted(
    state: ConversationAgentState,
    assistant_message_id: str,
) -> None:
    trace_run_id = uuid.UUID(state["trace_run_id"])
    conversation_turn_journal_service.update_turn_lifecycle(
        trace_run_id,
        "response_persisted",
    )
    conversation_turn_event_service.publish(
        trace_run_id,
        "response_persisted",
        {"status": "response_persisted", "assistant_message_id": assistant_message_id},
    )
