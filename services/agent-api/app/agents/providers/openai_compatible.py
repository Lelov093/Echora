"""OpenAI-compatible LLM Provider.

Uses OPENAI_BASE_URL / OPENAI_MODEL / OPENAI_API_KEY from config.

The normal Conversation path fails closed. Deterministic test generation remains available
through the explicit DeterministicTestProvider, but a real-provider outage must never be
persisted as if it were a Companion response.
"""

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable
import json

from app.agents.providers.base import LLMProvider, LLMProviderCancelled, LLMProviderError
from app.core.config import settings
from app.services.runtime_configuration_service import effective_llm_configuration


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible LLM provider."""

    def __init__(self):
        configuration = effective_llm_configuration()
        self._configured = bool(configuration["api_key"] and configuration["base_url"])
        self._model = configuration["model"]
        self._model_fallbacks = [
            str(model)
            for model in configuration.get("model_fallbacks") or []
            if str(model) and str(model) != self._model
        ]
        self._base_url = str(configuration["base_url"]).rstrip("/")
        self._api_key = configuration["api_key"]

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def is_simulation(self) -> bool:
        return not self._configured

    def generate(self, system_prompt: str, user_prompt: str,
                 context: dict[str, Any] | None = None) -> dict:
        if not self._configured:
            raise LLMProviderError(
                "LLM_PROVIDER_NOT_CONFIGURED",
                "The real LLM provider is not configured.",
                details={"provider": self.provider_name},
            )

        request_started_at = datetime.now(timezone.utc)
        request_started = perf_counter()
        model_attempts: list[dict[str, Any]] = []
        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            models = list(dict.fromkeys([self._model, *self._model_fallbacks]))
            for index, model in enumerate(models):
                payload, reasoning_evidence = _completion_payload(
                    model,
                    system_prompt,
                    user_prompt,
                    context,
                )
                try:
                    resp = httpx.post(
                        f"{self._base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=60.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPStatusError as exc:
                    model_attempts.append(_model_attempt(exc, model))
                    if index < len(models) - 1 and _fallbackable_status(exc.response.status_code):
                        continue
                    raise
                model_attempts.append({"model": model, "status": "succeeded"})
                break

            choice = data["choices"][0]
            provider_timing = _provider_timing(request_started_at, request_started)
            provider_timing["token_usage"] = _safe_token_usage(data.get("usage"))
            provider_timing["reasoning_policy"] = reasoning_evidence
            provider_timing["model_attempts"] = model_attempts
            return {
                "content": choice["message"]["content"],
                "model": data.get("model", model),
                "provider": "openai_compatible",
                "usage": data.get("usage"),
                "finish_reason": choice.get("finish_reason"),
                "warnings": [],
                "provider_timing": provider_timing,
                "reasoning_policy": reasoning_evidence,
            }
        except httpx.HTTPStatusError as exc:
            provider_error_code = None
            try:
                error_payload = exc.response.json().get("error") or {}
                provider_error_code = error_payload.get("code") or error_payload.get("type")
            except (TypeError, ValueError, AttributeError):
                pass
            details = {
                "provider": self.provider_name,
                "status_code": exc.response.status_code,
                "provider_error_code": provider_error_code,
            }
            if len(model_attempts) > 1:
                details["model_attempts"] = model_attempts
            raise LLMProviderError(
                "LLM_PROVIDER_REQUEST_REJECTED",
                "The real LLM provider rejected the request.",
                details=details,
                timing=_provider_timing(request_started_at, request_started),
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                "LLM_PROVIDER_UNREACHABLE",
                "The real LLM provider could not be reached.",
                details={
                    "provider": self.provider_name,
                    "failure_type": type(exc).__name__,
                },
                timing=_provider_timing(request_started_at, request_started),
            ) from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMProviderError(
                "LLM_PROVIDER_INVALID_RESPONSE",
                "The real LLM provider returned an invalid response.",
                details={
                    "provider": self.provider_name,
                    "failure_type": type(exc).__name__,
                },
                timing=_provider_timing(request_started_at, request_started),
            ) from exc

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        on_delta: Callable[[str], None],
        should_cancel: Callable[[], bool],
        context: dict[str, Any] | None = None,
    ) -> dict:
        if not self._configured:
            raise LLMProviderError(
                "LLM_PROVIDER_NOT_CONFIGURED",
                "The real LLM provider is not configured.",
                details={"provider": self.provider_name},
            )
        request_started_at = datetime.now(timezone.utc)
        request_started = perf_counter()
        chunks: list[str] = []
        first_byte_ms: int | None = None
        first_token_ms: int | None = None
        finish_reason = None
        usage = None
        model_attempts: list[dict[str, Any]] = []
        try:
            import httpx

            if should_cancel():
                raise LLMProviderCancelled("", timing=_stream_timing(
                    request_started_at, request_started, None, None,
                ))
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            models = list(dict.fromkeys([self._model, *self._model_fallbacks]))
            for index, model in enumerate(models):
                payload, reasoning_evidence = _completion_payload(
                    model,
                    system_prompt,
                    user_prompt,
                    context,
                    stream=True,
                )
                try:
                    with httpx.stream(
                        "POST",
                        f"{self._base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=60.0,
                    ) as response:
                        response.raise_for_status()
                        first_byte_ms = round((perf_counter() - request_started) * 1000)
                        model_attempts.append({"model": model, "status": "succeeded"})
                        for line in response.iter_lines():
                            if should_cancel():
                                raise LLMProviderCancelled(
                                    "".join(chunks),
                                    timing=_stream_timing(
                                        request_started_at, request_started, first_byte_ms, first_token_ms,
                                    ),
                                )
                            if not line or not line.startswith("data:"):
                                continue
                            data_text = line[5:].strip()
                            if data_text == "[DONE]":
                                break
                            data = json.loads(data_text)
                            usage = data.get("usage") or usage
                            choice = (data.get("choices") or [{}])[0]
                            finish_reason = choice.get("finish_reason") or finish_reason
                            delta = (choice.get("delta") or {}).get("content")
                            if not isinstance(delta, str) or not delta:
                                continue
                            if first_token_ms is None:
                                first_token_ms = round((perf_counter() - request_started) * 1000)
                            chunks.append(delta)
                            on_delta(delta)
                    break
                except httpx.HTTPStatusError as exc:
                    model_attempts.append(_model_attempt(exc, model))
                    if index < len(models) - 1 and _fallbackable_status(exc.response.status_code):
                        continue
                    raise
            content = "".join(chunks)
            if not content:
                raise LLMProviderError(
                    "LLM_PROVIDER_INVALID_RESPONSE",
                    "The streaming Provider returned no response content.",
                    details={"provider": self.provider_name},
                    timing=_stream_timing(
                        request_started_at, request_started, first_byte_ms, first_token_ms,
                    ),
                )
            timing = _stream_timing(
                request_started_at, request_started, first_byte_ms, first_token_ms,
            )
            timing["token_usage"] = _safe_token_usage(usage)
            timing["reasoning_policy"] = reasoning_evidence
            timing["model_attempts"] = model_attempts
            return {
                "content": content,
                "model": model,
                "provider": self.provider_name,
                "usage": usage,
                "finish_reason": finish_reason,
                "warnings": [],
                "provider_timing": timing,
                "reasoning_policy": reasoning_evidence,
            }
        except LLMProviderCancelled:
            raise
        except httpx.HTTPStatusError as exc:
            provider_error_code = None
            try:
                error_payload = exc.response.json().get("error") or {}
                provider_error_code = error_payload.get("code") or error_payload.get("type")
            except (TypeError, ValueError, AttributeError):
                pass
            details = {
                "provider": self.provider_name,
                "status_code": exc.response.status_code,
                "provider_error_code": provider_error_code,
            }
            if len(model_attempts) > 1:
                details["model_attempts"] = model_attempts
            raise LLMProviderError(
                "LLM_PROVIDER_REQUEST_REJECTED",
                "The real streaming Provider rejected the request.",
                details=details,
                timing=_stream_timing(
                    request_started_at, request_started, first_byte_ms, first_token_ms,
                ),
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                "LLM_PROVIDER_UNREACHABLE",
                "The real streaming Provider could not be reached.",
                details={"provider": self.provider_name, "failure_type": type(exc).__name__},
                timing=_stream_timing(
                    request_started_at, request_started, first_byte_ms, first_token_ms,
                ),
            ) from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMProviderError(
                "LLM_PROVIDER_INVALID_RESPONSE",
                "The real streaming Provider returned an invalid event.",
                details={"provider": self.provider_name, "failure_type": type(exc).__name__},
                timing=_stream_timing(
                    request_started_at, request_started, first_byte_ms, first_token_ms,
                ),
            ) from exc


def _provider_timing(started_at: datetime, started: float) -> dict[str, Any]:
    completed_at = datetime.now(timezone.utc)
    return {
        "measurement_mode": "non_streaming_full_response",
        "request_started_at": started_at.isoformat(),
        "response_completed_at": completed_at.isoformat(),
        "total_ms": round((perf_counter() - started) * 1000),
        "time_to_first_byte_ms": None,
        "time_to_first_token_ms": None,
        "time_to_last_token_ms": None,
        "first_token_measurement_status": "unavailable_until_streaming",
        "first_byte_measurement_status": "unavailable_with_buffered_client",
        "last_token_measurement_status": "unavailable_until_streaming",
    }


def _completion_payload(
    model: str,
    system_prompt: str,
    user_prompt: str,
    context: dict[str, Any] | None,
    *,
    stream: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request_context = context or {}
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": float(request_context.get("temperature", 0.7)),
        "max_tokens": int(request_context.get("max_tokens", 1024)),
    }
    if stream:
        payload["stream"] = True

    policy = request_context.get("reasoning_policy") or {}
    requested_tier = str(policy.get("tier") or "provider_default")
    requested_enable = policy.get("enable_thinking")
    requested_budget = policy.get("thinking_budget")
    model_key = model.lower()
    is_qwen37_max = model_key == "qwen3.7-max" or model_key.startswith("qwen3.7-max-")
    is_thinking_only = (
        model_key == "qwen3.7-max-preview"
        or model_key == "qwen3.7-max-2026-05-17"
    )
    parameter_mode = "provider_default"
    applied_tier = requested_tier

    if is_qwen37_max and is_thinking_only:
        parameter_mode = "qwen37_thinking_only"
        applied_tier = (
            requested_tier if requested_enable is not False else "provider_required_minimum"
        )
        payload["enable_thinking"] = True
        payload["thinking_budget"] = max(int(requested_budget or 1024), 1024)
    elif is_qwen37_max and isinstance(requested_enable, bool):
        parameter_mode = "qwen37_hybrid"
        payload["enable_thinking"] = requested_enable
        if requested_enable and isinstance(requested_budget, int):
            payload["thinking_budget"] = requested_budget

    evidence = {
        "policy_version": str(policy.get("policy_version") or "provider-default"),
        "requested_mode": str(policy.get("requested_mode") or "auto"),
        "router_selected_tier": policy.get("router_selected_tier"),
        "requested_tier": requested_tier,
        "applied_tier": applied_tier,
        "selection_reason": str(policy.get("selection_reason") or "provider_default"),
        "override_reason": (
            "model_requires_thinking"
            if applied_tier == "provider_required_minimum"
            else policy.get("override_reason")
        ),
        "parameter_mode": parameter_mode,
        "enable_thinking": payload.get("enable_thinking"),
        "thinking_budget": payload.get("thinking_budget"),
        "reasoning_content_persisted": False,
    }
    return payload, evidence


def _fallbackable_status(status_code: int) -> bool:
    return status_code in {404, 408, 409, 429} or status_code >= 500


def _model_attempt(exc: Any, model: str) -> dict[str, Any]:
    provider_error_code = None
    try:
        error_payload = exc.response.json().get("error") or {}
        provider_error_code = error_payload.get("code") or error_payload.get("type")
    except (TypeError, ValueError, AttributeError):
        pass
    return {
        "model": model,
        "status": "failed",
        "status_code": exc.response.status_code,
        "provider_error_code": provider_error_code,
    }


def _safe_token_usage(value: Any) -> dict[str, int | None]:
    usage = value if isinstance(value, dict) else {}
    return {
        "prompt_tokens": usage.get("prompt_tokens") if isinstance(usage.get("prompt_tokens"), int) else None,
        "completion_tokens": usage.get("completion_tokens") if isinstance(usage.get("completion_tokens"), int) else None,
        "total_tokens": usage.get("total_tokens") if isinstance(usage.get("total_tokens"), int) else None,
    }


def _stream_timing(
    started_at: datetime,
    started: float,
    first_byte_ms: int | None,
    first_token_ms: int | None,
) -> dict[str, Any]:
    completed_at = datetime.now(timezone.utc)
    total_ms = round((perf_counter() - started) * 1000)
    return {
        "measurement_mode": "provider_sse_stream",
        "request_started_at": started_at.isoformat(),
        "response_completed_at": completed_at.isoformat(),
        "total_ms": total_ms,
        "time_to_first_byte_ms": first_byte_ms,
        "time_to_first_token_ms": first_token_ms,
        "time_to_last_token_ms": total_ms if first_token_ms is not None else None,
        "first_token_measurement_status": "measured" if first_token_ms is not None else "not_observed",
        "first_byte_measurement_status": "measured" if first_byte_ms is not None else "not_observed",
        "last_token_measurement_status": "measured" if first_token_ms is not None else "not_observed",
    }
