"""Reasoning policy and Provider request compatibility."""

import httpx

from app.agents.providers.openai_compatible import (
    OpenAICompatibleProvider,
    _completion_payload,
)
from app.agents.providers.reasoning_policy import select_conversation_reasoning_policy
from app.services import runtime_configuration_service


def test_ordinary_companionship_uses_direct_tier():
    policy = select_conversation_reasoning_policy({
        "user_input": "今天有点累，陪我聊一会儿吧。",
        "response_strategy": {"signals": {}, "boundary_risk": 0.0},
    })

    assert policy == {
        "policy_version": "conversation-reasoning-policy.v1",
        "requested_mode": "auto",
        "router_selected_tier": "direct",
        "override_reason": None,
        "tier": "direct",
        "selection_reason": "ordinary_companionship",
        "enable_thinking": False,
        "thinking_budget": None,
    }


def test_structured_planning_and_tool_results_use_balanced_tier():
    planning = select_conversation_reasoning_policy({
        "user_input": "帮我规划下一步",
        "response_strategy": {"signals": {"planning": 0.75}, "boundary_risk": 0.0},
    })
    tool = select_conversation_reasoning_policy({
        "user_input": "总结查询结果",
        "tool_runs": [{"status": "succeeded"}],
        "response_strategy": {"signals": {}, "boundary_risk": 0.0},
    })

    assert planning["tier"] == "balanced"
    assert planning["thinking_budget"] == 4096
    assert tool["tier"] == "balanced"
    assert tool["selection_reason"] == "tool_result_synthesis"


def test_boundary_risk_uses_deliberate_tier():
    policy = select_conversation_reasoning_policy({
        "user_input": "不要再联系我",
        "response_strategy": {"signals": {}, "boundary_risk": 0.9},
    })

    assert policy["tier"] == "deliberate"
    assert policy["thinking_budget"] == 8192


def test_manual_modes_map_to_stable_reasoning_tiers():
    cases = {
        "fast": ("direct", None),
        "thinking": ("balanced", 4096),
        "deep_thinking": ("deliberate", 8192),
    }

    for requested_mode, (tier, budget) in cases.items():
        policy = select_conversation_reasoning_policy({
            "requested_reasoning_mode": requested_mode,
            "user_input": "普通对话",
            "response_strategy": {"signals": {}, "boundary_risk": 0.0},
        })

        assert policy["requested_mode"] == requested_mode
        assert policy["tier"] == tier
        assert policy["thinking_budget"] == budget
        assert policy["override_reason"] is None


def test_boundary_safety_floor_can_raise_manual_fast_mode():
    policy = select_conversation_reasoning_policy({
        "requested_reasoning_mode": "fast",
        "user_input": "不要再联系我",
        "response_strategy": {"signals": {}, "boundary_risk": 0.9},
    })

    assert policy["requested_mode"] == "fast"
    assert policy["router_selected_tier"] == "deliberate"
    assert policy["tier"] == "deliberate"
    assert policy["override_reason"] == "boundary_safety_floor"


def test_qwen37_hybrid_direct_payload_disables_thinking():
    payload, evidence = _completion_payload(
        "qwen3.7-max-2026-05-20",
        "system",
        "user",
        {"reasoning_policy": select_conversation_reasoning_policy({})},
        stream=True,
    )

    assert payload["stream"] is True
    assert payload["enable_thinking"] is False
    assert "thinking_budget" not in payload
    assert evidence["parameter_mode"] == "qwen37_hybrid"
    assert evidence["reasoning_content_persisted"] is False


def test_qwen37_thinking_only_fallback_never_receives_disable():
    payload, evidence = _completion_payload(
        "qwen3.7-max-preview",
        "system",
        "user",
        {"reasoning_policy": select_conversation_reasoning_policy({})},
    )

    assert payload["enable_thinking"] is True
    assert payload["thinking_budget"] == 1024
    assert evidence["applied_tier"] == "provider_required_minimum"
    assert evidence["override_reason"] == "model_requires_thinking"


def test_unknown_openai_compatible_model_keeps_provider_default():
    payload, evidence = _completion_payload(
        "unknown-model",
        "system",
        "user",
        {"reasoning_policy": {"tier": "direct", "enable_thinking": False}},
    )

    assert "enable_thinking" not in payload
    assert "thinking_budget" not in payload
    assert evidence["parameter_mode"] == "provider_default"


def test_environment_model_fallbacks_enter_effective_configuration(monkeypatch):
    monkeypatch.setattr(runtime_configuration_service, "_public", lambda: {
        "revision": 0,
        "llm": {
            "provider": "openai_compatible",
            "base_url": "",
            "model": "",
            "model_fallbacks": [],
        },
    })
    monkeypatch.setattr(runtime_configuration_service, "_secret_values", lambda: {})
    monkeypatch.setattr(
        runtime_configuration_service.settings,
        "OPENAI_MODEL_FALLBACKS",
        "qwen-a, qwen-b,qwen-a",
    )

    result = runtime_configuration_service.effective_llm_configuration()

    assert result["model_fallbacks"] == ["qwen-a", "qwen-b"]


def test_non_streaming_retries_fallback_model_on_retryable_status(monkeypatch):
    provider = OpenAICompatibleProvider()
    provider._configured = True
    provider._api_key = "test-key"
    provider._base_url = "https://provider.invalid"
    provider._model = "primary-model"
    provider._model_fallbacks = ["fallback-model"]
    payloads = []

    def post(*_args, **kwargs):
        payloads.append(kwargs["json"])
        if len(payloads) == 1:
            return httpx.Response(
                503,
                request=httpx.Request("POST", "https://provider.invalid/chat/completions"),
                json={"error": {"code": "model_unavailable"}},
            )
        return httpx.Response(
            200,
            request=httpx.Request("POST", "https://provider.invalid/chat/completions"),
            json={
                "model": "fallback-model",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            },
        )

    monkeypatch.setattr(httpx, "post", post)

    result = provider.generate("system", "user")

    assert [payload["model"] for payload in payloads] == [
        "primary-model",
        "fallback-model",
    ]
    assert result["model"] == "fallback-model"
    assert result["provider_timing"]["model_attempts"] == [
        {
            "model": "primary-model",
            "status": "failed",
            "status_code": 503,
            "provider_error_code": "model_unavailable",
        },
        {"model": "fallback-model", "status": "succeeded"},
    ]


def test_streaming_retries_fallback_before_any_delta(monkeypatch):
    provider = OpenAICompatibleProvider()
    provider._configured = True
    provider._api_key = "test-key"
    provider._base_url = "https://provider.invalid"
    provider._model = "primary-model"
    provider._model_fallbacks = ["fallback-model"]
    payloads = []

    class StreamResponse:
        def __init__(self, status_code, lines=()):
            self.response = httpx.Response(
                status_code,
                request=httpx.Request("POST", "https://provider.invalid/chat/completions"),
                json={"error": {"code": "model_unavailable"}} if status_code != 200 else None,
            )
            self.lines = lines

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            self.response.raise_for_status()

        def iter_lines(self):
            yield from self.lines

    def stream(*_args, **kwargs):
        payloads.append(kwargs["json"])
        if len(payloads) == 1:
            return StreamResponse(503)
        return StreamResponse(
            200,
            (
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            ),
        )

    monkeypatch.setattr(httpx, "stream", stream)
    deltas = []

    result = provider.generate_stream(
        "system",
        "user",
        on_delta=deltas.append,
        should_cancel=lambda: False,
    )

    assert [payload["model"] for payload in payloads] == [
        "primary-model",
        "fallback-model",
    ]
    assert deltas == ["ok"]
    assert result["model"] == "fallback-model"


def test_streaming_never_emits_or_returns_reasoning_content(monkeypatch):
    provider = OpenAICompatibleProvider()
    provider._configured = True
    provider._api_key = "test-key"
    provider._base_url = "https://provider.invalid"
    provider._model = "qwen3.7-max-2026-05-20"
    provider._model_fallbacks = []

    class StreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"reasoning_content":"private chain"}}]}'
            yield 'data: {"choices":[{"delta":{"content":"visible answer"}}]}'
            yield "data: [DONE]"

    monkeypatch.setattr(httpx, "stream", lambda *_args, **_kwargs: StreamResponse())
    deltas = []

    result = provider.generate_stream(
        "system",
        "user",
        on_delta=deltas.append,
        should_cancel=lambda: False,
        context={
            "reasoning_policy": {
                "policy_version": "conversation-reasoning-policy.v1",
                "tier": "balanced",
                "selection_reason": "test",
                "enable_thinking": True,
                "thinking_budget": 4096,
            },
        },
    )

    assert deltas == ["visible answer"]
    assert result["content"] == "visible answer"
    assert "reasoning_content" not in result
    assert result["reasoning_policy"]["reasoning_content_persisted"] is False
