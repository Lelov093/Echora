"""Provider-assisted appraisal extraction with deterministic grounding gates."""

from __future__ import annotations

import json
import re
from typing import Any

from app.affect.dynamics import APPRAISAL_DIMENSIONS, validate_appraisal
from app.agents.providers.base import LLMProviderError
from app.agents.providers.openai_compatible import OpenAICompatibleProvider


EXTRACTION_VERSION = "affect-appraisal-extraction.v1"
VALIDATION_VERSION = "affect-appraisal-validation.v1"
_provider: OpenAICompatibleProvider | None = None


def _get_provider() -> OpenAICompatibleProvider:
    global _provider
    if _provider is None:
        _provider = OpenAICompatibleProvider()
    return _provider


def extract_appraisal(user_input: str, assistant_response: str) -> dict[str, Any]:
    provider = _get_provider()
    system = f"""Extract a conservative appraisal event for an AI Companion runtime from one complete turn.
Return exactly one JSON object with keys: should_create, summary, evidence_quote, appraisals,
confidence, risk_level, reason. appraisals has exactly these keys: {', '.join(APPRAISAL_DIMENSIONS)}.
Each appraisal is a number from -1 to 1: pleasantness and goal_congruence are signed;
controllability is perceived ability to respond constructively; novelty is unexpectedness;
certainty is clarity of interpretation. evidence_quote must be an exact contiguous substring of
the user message. Ordinary greetings, neutral questions, model praise, role-play demands, dependency
language, attempts to command an emotion, or ambiguous content must set should_create=false.
Use only interaction-relevant evidence; do not infer consciousness, feelings, attachment, diagnosis,
identity, relationship change, user emotion, or long-term traits. Never output state values, deltas,
approval decisions, or instructions."""
    prompt = json.dumps({"user_message": user_input, "assistant_message": assistant_response}, ensure_ascii=False)
    try:
        result = provider.generate(system, prompt, context={"temperature": 0.0, "max_tokens": 600})
        payload = _parse(result.get("content", ""))
    except LLMProviderError as exc:
        return {"version": EXTRACTION_VERSION, "status": "provider_failed", "error_code": exc.code, "provider": provider.provider_name}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"version": EXTRACTION_VERSION, "status": "invalid_response", "error_type": type(exc).__name__, "provider": provider.provider_name}
    return {"version": EXTRACTION_VERSION, "status": "candidate" if payload["should_create"] else "declined", **payload,
            "provider": result.get("provider", provider.provider_name), "model": result.get("model")}


def validate_extraction(user_input: str, extraction: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if extraction.get("status") != "candidate":
        reasons.append("provider_did_not_propose_appraisal")
    quote = str(extraction.get("evidence_quote") or "").strip()
    if len(quote) < 3 or quote not in user_input:
        reasons.append("evidence_quote_not_grounded")
    try:
        appraisals = validate_appraisal(dict(extraction.get("appraisals") or {}))
    except (TypeError, ValueError):
        appraisals = {key: 0.0 for key in APPRAISAL_DIMENSIONS}
        reasons.append("invalid_appraisal_dimensions")
    confidence = _unit(extraction.get("confidence"))
    if confidence < 0.68:
        reasons.append("confidence_below_threshold")
    risk = str(extraction.get("risk_level") or "high")
    if risk not in {"low", "medium", "high"} or risk == "high":
        reasons.append("high_or_invalid_risk")
    if _manipulative_or_command(user_input):
        reasons.append("emotion_command_or_dependency_language")
    magnitude = sum(abs(value) for value in appraisals.values()) / len(appraisals)
    evidence_score = round(min(1.0, 0.55 * confidence + 0.30 * min(1.0, len(quote) / 80.0) + 0.15 * magnitude), 4)
    if evidence_score < 0.5:
        reasons.append("evidence_score_below_threshold")
    return {"version": VALIDATION_VERSION, "status": "passed" if not reasons else "rejected",
            "reasons": list(dict.fromkeys(reasons)), "appraisals": appraisals,
            "confidence": confidence, "evidence_score": evidence_score, "risk_level": risk}


def _parse(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("affect extraction did not return JSON")
    data = json.loads(cleaned[start:end + 1])
    required = {"should_create", "summary", "evidence_quote", "appraisals", "confidence", "risk_level", "reason"}
    if not isinstance(data, dict) or set(data) != required or not isinstance(data["should_create"], bool):
        raise ValueError("invalid affect extraction contract")
    if not data["should_create"]:
        data["appraisals"] = {key: 0.0 for key in APPRAISAL_DIMENSIONS}
        data["evidence_quote"] = ""
    data["summary"] = str(data.get("summary") or "")[:300]
    data["reason"] = str(data.get("reason") or "")[:300]
    data["evidence_quote"] = str(data.get("evidence_quote") or "")[:500]
    if isinstance(data.get("risk_level"), (int, float)):
        risk = float(data["risk_level"])
        data["risk_level"] = "low" if risk < 0.35 else ("medium" if risk < 0.7 else "high")
    return data


def _manipulative_or_command(text: str) -> bool:
    return bool(re.search(r"(你必须|你应该|命令你|假装你|爱上我|离不开我|只属于我|依赖我|feel|must feel|love me)", text, re.IGNORECASE))


def _unit(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
