"""Provider-assisted, source-grounded Growth candidate extraction."""

from __future__ import annotations

import json
import re
from typing import Any

from app.agents.providers.base import LLMProviderError
from app.agents.providers.openai_compatible import OpenAICompatibleProvider


VERSION = "growth-extraction.v1"
ALLOWED_TYPES = {"understanding_update", "correction", "response_strategy"}
_provider: OpenAICompatibleProvider | None = None


def _get_provider() -> OpenAICompatibleProvider:
    global _provider
    if _provider is None:
        _provider = OpenAICompatibleProvider()
    return _provider


def extract_growth_candidate(user_input: str, assistant_response: str) -> dict[str, Any]:
    provider = _get_provider()
    system = """Extract a review-gated Companion Growth candidate from one completed turn.
Return exactly one JSON object with keys should_create, type, source_quote, assistant_outcome_quote,
content, confidence, risk_level, reason. type is understanding_update, correction, or response_strategy.
source_quote must be an exact user-message substring. assistant_outcome_quote is optional and, if present,
must be an exact assistant-message substring. Create only for an explicit correction, a demonstrated
understanding gap, or concrete feedback about how the Companion should respond. Never change persona core,
relationship contract, relationship state, consent, or boundaries. Do not treat an ordinary question,
greeting, or the assistant's own claim as Growth. Return JSON only."""
    prompt = json.dumps({"user_message": user_input, "assistant_message": assistant_response}, ensure_ascii=False)
    try:
        result = provider.generate(system, prompt, context={"temperature": 0.0, "max_tokens": 420})
        data = _parse(result.get("content", ""))
    except LLMProviderError as exc:
        return {"version": VERSION, "status": "provider_failed", "error_code": exc.code, "provider": provider.provider_name}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"version": VERSION, "status": "invalid_response", "error_type": type(exc).__name__, "provider": provider.provider_name}
    reasons = []
    quote = str(data.get("source_quote") or "").strip()
    outcome = str(data.get("assistant_outcome_quote") or "").strip()
    if data["should_create"] and (not quote or quote not in user_input):
        reasons.append("user_source_quote_not_grounded")
    if outcome and outcome not in assistant_response:
        reasons.append("assistant_outcome_quote_not_grounded")
    if data["type"] not in ALLOWED_TYPES:
        reasons.append("unsupported_growth_type")
    confidence = _unit(data.get("confidence"))
    if confidence < 0.72:
        reasons.append("provider_confidence_below_candidate_threshold")
    status = "validated" if data["should_create"] and not reasons else ("declined" if not data["should_create"] else "rejected")
    return {
        "version": VERSION, "status": status, **data, "confidence": confidence,
        "validation_reasons": reasons, "provider": result.get("provider", provider.provider_name), "model": result.get("model"),
    }


def _parse(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("growth extraction did not return JSON")
    data = json.loads(cleaned[start:end + 1])
    keys = {"should_create", "type", "source_quote", "assistant_outcome_quote", "content", "confidence", "risk_level", "reason"}
    if not isinstance(data, dict) or set(data) != keys or not isinstance(data.get("should_create"), bool):
        raise ValueError("invalid growth extraction contract")
    data["source_quote"] = str(data.get("source_quote") or "")[:500]
    data["assistant_outcome_quote"] = str(data.get("assistant_outcome_quote") or "")[:500]
    data["content"] = str(data.get("content") or "")[:500]
    data["reason"] = str(data.get("reason") or "")[:300]
    data["risk_level"] = str(data.get("risk_level") or "high").lower()
    if data["risk_level"] not in {"low", "medium", "high"}:
        data["risk_level"] = "high"
    return data


def _unit(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))
