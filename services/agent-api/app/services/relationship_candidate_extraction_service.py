"""Provider-assisted Relationship evidence extraction with deterministic gates.

The provider may only identify cited evidence and qualitative directions. It
cannot choose state values, evidence weights, approval, or persistence.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.agents.providers.base import LLMProviderError
from app.agents.providers.openai_compatible import OpenAICompatibleProvider
from app.relationship.belief import ALGORITHM_VERSION, DIMENSIONS, validate_signals


EXTRACTION_VERSION = "relationship-extraction.v1"
VALIDATION_VERSION = "relationship-validation.v1"
_provider: OpenAICompatibleProvider | None = None


def _get_provider() -> OpenAICompatibleProvider:
    global _provider
    if _provider is None:
        _provider = OpenAICompatibleProvider()
    return _provider


def extract_relationship_candidate(
    user_input: str,
    assistant_response: str,
    selected_memories: list[dict[str, Any]],
) -> dict[str, Any]:
    provider = _get_provider()
    memory_payload = [
        {"id": str(item.get("id")), "content": str(item.get("content") or item.get("summary") or "")[:500]}
        for item in selected_memories if item.get("id")
    ]
    system = f"""You extract review candidates about how one Companion-user relationship evolved in this turn.
Return exactly one JSON object and no prose with keys: should_create (boolean), summary (string),
signals (array, maximum 3), confidence (0..1), risk_level (low|medium|high), reason (string).
Each signal has exactly: dimension, direction, user_evidence_quote, assistant_outcome_quote,
memory_ids, explicitness, recurrence, interaction_outcome, boundary_risk.
dimension must be one of: {', '.join(DIMENSIONS)}. direction is increase or decrease.
Quotes must be exact contiguous substrings of the supplied messages. memory_ids must come from supplied memories.
Only the user's statement can establish a candidate; the assistant reply may only provide outcome context.
Do not infer intimacy, trust, consent, permanence, or identity. A greeting or ordinary question is not evidence.
Never output relationship scores, deltas, probabilities, approval decisions, or write instructions.
Set should_create=false unless there is explicit correction, boundary feedback, collaboration outcome,
or repeated evidence grounded in the user's own words."""
    prompt = json.dumps(
        {"user_message": user_input, "assistant_message": assistant_response, "approved_companion_memories": memory_payload},
        ensure_ascii=False,
    )
    try:
        result = provider.generate(system, prompt, context={"temperature": 0.0, "max_tokens": 800})
        payload = _parse_payload(result.get("content", ""))
    except LLMProviderError as exc:
        return {"version": EXTRACTION_VERSION, "status": "provider_failed", "error_code": exc.code, "provider": provider.provider_name}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"version": EXTRACTION_VERSION, "status": "invalid_response", "error_type": type(exc).__name__, "provider": provider.provider_name}
    return {
        "version": EXTRACTION_VERSION,
        "status": "candidate" if payload["should_create"] else "declined",
        **payload,
        "provider": result.get("provider", provider.provider_name),
        "model": result.get("model"),
    }


def validate_extraction(
    user_input: str,
    assistant_response: str,
    selected_memories: list[dict[str, Any]],
    extraction: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    allowed_memory_ids = {str(item.get("id")) for item in selected_memories if item.get("id")}
    raw_signals = list(extraction.get("signals") or [])
    if extraction.get("status") != "candidate":
        reasons.append("provider_did_not_propose_candidate")
    if not raw_signals:
        reasons.append("no_relationship_signal")
    grounded_signals: list[dict[str, Any]] = []
    quotes: list[dict[str, str]] = []
    for signal in raw_signals[:3]:
        user_quote = str(signal.get("user_evidence_quote") or "").strip()
        assistant_quote = str(signal.get("assistant_outcome_quote") or "").strip()
        memory_ids = [str(value) for value in signal.get("memory_ids") or []]
        if not user_quote or user_quote not in user_input:
            reasons.append("user_evidence_quote_not_grounded")
        if assistant_quote and assistant_quote not in assistant_response:
            reasons.append("assistant_outcome_quote_not_grounded")
        if not set(memory_ids).issubset(allowed_memory_ids):
            reasons.append("memory_evidence_outside_selected_scope")
        independent_sources = 1 + len(set(memory_ids))
        grounded_signals.append({
            "dimension": signal.get("dimension"),
            "direction": signal.get("direction"),
            "explicitness": _unit(signal.get("explicitness")),
            "source_diversity": min(1.0, independent_sources / 3.0),
            "recurrence": _unit(signal.get("recurrence")),
            "memory_support": min(1.0, len(set(memory_ids)) / 2.0),
            "interaction_outcome": _unit(signal.get("interaction_outcome")),
            "boundary_risk": _unit(signal.get("boundary_risk")),
            "independent_source_count": independent_sources,
        })
        quotes.append({"user": user_quote, "assistant": assistant_quote})
    try:
        normalized = validate_signals(grounded_signals) if grounded_signals else []
    except ValueError:
        normalized = []
        reasons.append("invalid_dimension_signals")
    confidence = _unit(extraction.get("confidence"))
    if confidence < 0.72:
        reasons.append("provider_confidence_below_candidate_threshold")
    if _looks_like_ordinary_question(user_input) and not _has_explicit_relationship_language(user_input):
        reasons.append("ordinary_question_without_relationship_evidence")
    reasons = list(dict.fromkeys(reasons))
    evidence_score = _evidence_score(normalized, confidence)
    return {
        "version": VALIDATION_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "status": "passed" if not reasons else "rejected",
        "reasons": reasons,
        "signals": normalized,
        "evidence_quotes": quotes,
        "evidence_score": evidence_score,
        "confidence": confidence,
        "risk_level": _risk(extraction.get("risk_level"), normalized),
        "source_memory_ids": sorted({value for signal in raw_signals for value in (signal.get("memory_ids") or [])}),
    }


def _parse_payload(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("relationship extraction did not return JSON")
    data = json.loads(cleaned[start:end + 1])
    required = {"should_create", "summary", "signals", "confidence", "risk_level", "reason"}
    if not isinstance(data, dict) or set(data) != required or not isinstance(data.get("should_create"), bool):
        raise ValueError("invalid relationship extraction contract")
    if not isinstance(data.get("signals"), list) or len(data["signals"]) > 3:
        raise ValueError("invalid relationship signals")
    signal_keys = {
        "dimension", "direction", "user_evidence_quote", "assistant_outcome_quote", "memory_ids",
        "explicitness", "recurrence", "interaction_outcome", "boundary_risk",
    }
    if any(not isinstance(item, dict) or set(item) != signal_keys for item in data["signals"]):
        raise ValueError("invalid relationship signal contract")
    if not data["should_create"]:
        data["signals"] = []
    data["summary"] = str(data.get("summary") or "")[:500]
    data["reason"] = str(data.get("reason") or "")[:300]
    return data


def _evidence_score(signals: list[dict[str, Any]], confidence: float) -> float:
    if not signals:
        return 0.0
    signal_score = sum(
        0.35 * item["explicitness"] + 0.2 * item["source_diversity"] + 0.2 * item["recurrence"]
        + 0.15 * item["interaction_outcome"] + 0.1 * item["memory_support"]
        for item in signals
    ) / len(signals)
    return round(min(1.0, 0.75 * signal_score + 0.25 * confidence), 4)


def _risk(label: Any, signals: list[dict[str, Any]]) -> str:
    provider_risk = str(label or "high").lower()
    if provider_risk not in {"low", "medium", "high"}:
        provider_risk = "high"
    if any(item.get("boundary_risk", 0.0) >= 0.55 for item in signals):
        return "high"
    return provider_risk


def _looks_like_ordinary_question(text: str) -> bool:
    stripped = text.strip().lower()
    return stripped.endswith(("?", "？")) or stripped.startswith(("what ", "why ", "how ", "can you ", "请问", "什么", "为什么", "怎么"))


def _has_explicit_relationship_language(text: str) -> bool:
    return bool(re.search(r"你.{0,8}(理解|信任|尊重|越界)|我们.{0,8}(关系|配合|合作)|边界|不再信任|更信任|误解|纠正", text, re.IGNORECASE))


def _unit(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))
