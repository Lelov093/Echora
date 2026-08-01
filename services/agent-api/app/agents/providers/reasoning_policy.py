"""Bounded, explainable reasoning policy for one Conversation response."""

from __future__ import annotations

from typing import Any


POLICY_VERSION = "conversation-reasoning-policy.v1"
REASONING_MODES = {"auto", "fast", "thinking", "deep_thinking"}
_TIER_RANK = {"direct": 0, "balanced": 1, "deliberate": 2}


def select_conversation_reasoning_policy(state: dict[str, Any]) -> dict[str, Any]:
    """Choose a small reasoning tier from already-computed, safe turn signals."""
    requested_mode = str(state.get("requested_reasoning_mode") or "auto")
    if requested_mode not in REASONING_MODES:
        requested_mode = "auto"
    automatic = _automatic_policy(state)
    router_tier = automatic["tier"]
    if requested_mode == "auto":
        selected = automatic
        override_reason = None
    else:
        requested_tier = {
            "fast": "direct",
            "thinking": "balanced",
            "deep_thinking": "deliberate",
        }[requested_mode]
        safety_floor = (
            router_tier
            if automatic["selection_reason"] == "boundary_or_guard_risk"
            else "direct"
        )
        applied_tier = max(
            (requested_tier, safety_floor),
            key=lambda tier: _TIER_RANK[tier],
        )
        override_reason = (
            "boundary_safety_floor"
            if applied_tier != requested_tier
            else None
        )
        selected = _policy_for_tier(
            applied_tier,
            "manual_selection" if override_reason is None else override_reason,
        )
    return {
        **selected,
        "requested_mode": requested_mode,
        "router_selected_tier": router_tier,
        "override_reason": override_reason,
    }


def _automatic_policy(state: dict[str, Any]) -> dict[str, Any]:
    strategy = state.get("response_strategy") or {}
    signals = strategy.get("signals") or {}
    boundary_risk = float(strategy.get("boundary_risk") or 0.0)
    guard = state.get("persona_guard_result") or {}
    guard_status = str(
        guard.get("check_status") or guard.get("decision") or ""
    ).lower()

    if boundary_risk >= 0.75 or guard_status in {"blocked", "block", "review_required"}:
        return _policy(
            "deliberate",
            "boundary_or_guard_risk",
            enable_thinking=True,
            thinking_budget=8192,
        )

    structured_signal = max(
        (
            float(signals.get(name) or 0.0)
            for name in ("planning", "reflection", "correction", "goal")
        ),
        default=0.0,
    )
    has_tool_evidence = bool(state.get("tool_runs") or state.get("tool_run_ids"))
    long_structured_input = len(str(state.get("user_input") or "")) >= 320
    if has_tool_evidence or structured_signal >= 0.75 or long_structured_input:
        reason = (
            "tool_result_synthesis"
            if has_tool_evidence
            else "structured_or_complex_request"
        )
        return _policy(
            "balanced",
            reason,
            enable_thinking=True,
            thinking_budget=4096,
        )

    return _policy(
        "direct",
        "ordinary_companionship",
        enable_thinking=False,
        thinking_budget=None,
    )


def _policy_for_tier(tier: str, reason: str) -> dict[str, Any]:
    if tier == "deliberate":
        return _policy(tier, reason, enable_thinking=True, thinking_budget=8192)
    if tier == "balanced":
        return _policy(tier, reason, enable_thinking=True, thinking_budget=4096)
    return _policy("direct", reason, enable_thinking=False, thinking_budget=None)


def _policy(
    tier: str,
    reason: str,
    *,
    enable_thinking: bool,
    thinking_budget: int | None,
) -> dict[str, Any]:
    return {
        "policy_version": POLICY_VERSION,
        "tier": tier,
        "selection_reason": reason,
        "enable_thinking": enable_thinking,
        "thinking_budget": thinking_budget,
    }
