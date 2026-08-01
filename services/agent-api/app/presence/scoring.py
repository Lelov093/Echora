"""Presence Priority Scoring — Core conversation heuristic formula."""

from typing import Any

from app.core.algorithm_contract import (
    PRESENCE_PRIORITY_CONTRACT,
    clamp01,
    contract_trace,
    weighted_score,
)


def score_presence_priority(
    goal_relevance: float = 0.0,
    continuity_importance: float = 0.0,
    user_interest_match: float = 0.0,
    memory_importance: float = 0.0,
    growth_relevance: float = 0.0,
    time_sensitivity: float = 0.0,
    relationship_fit: float = 0.0,
    interruption_risk: float = 0.0,
    recent_dismissal_penalty: float = 0.0,
    sensitivity_penalty: float = 0.0,
    user_input: str = "",
    selected_memories: list[dict[str, Any]] | None = None,
) -> dict:
    """Compute opportunity_priority using Core conversation heuristic weights.

    Core conversation thresholds:
      priority >= 0.80 → hub priority
      0.55 <= priority < 0.80 → queue
      0.35 <= priority < 0.55 → low-priority queue
      priority < 0.35 → no opportunity
    """
    # Auto-detect signals from input
    if goal_relevance <= 0:
        goal_relevance = _detect_goal(user_input)
    if continuity_importance <= 0:
        continuity_importance = _detect_continuity(user_input)
    if time_sensitivity <= 0:
        time_sensitivity = _detect_time_sensitivity(user_input)

    # Apply sensible defaults for non-zero factors
    if user_interest_match <= 0:
        user_interest_match = 0.53
    if memory_importance <= 0 and selected_memories:
        memory_importance = 0.4
    if growth_relevance <= 0:
        growth_relevance = 0.05
    if relationship_fit <= 0:
        relationship_fit = 0.45

    # Boost goal_relevance when continuity is high (implies ongoing work)
    if continuity_importance >= 0.70 and goal_relevance < 0.45:
        goal_relevance = max(goal_relevance, 0.45)

    factors = {
        "goal_relevance": clamp01(goal_relevance),
        "continuity_importance": clamp01(continuity_importance),
        "user_interest_match": clamp01(user_interest_match),
        "memory_importance": clamp01(memory_importance),
        "growth_relevance": clamp01(growth_relevance),
        "time_sensitivity": clamp01(time_sensitivity),
        "relationship_fit": clamp01(relationship_fit),
        "interruption_risk": clamp01(interruption_risk),
        "recent_dismissal_penalty": clamp01(recent_dismissal_penalty),
        "sensitivity_penalty": clamp01(sensitivity_penalty),
    }
    score = weighted_score(factors, PRESENCE_PRIORITY_CONTRACT)
    thresholds = PRESENCE_PRIORITY_CONTRACT["thresholds"]

    if score >= thresholds["hub"]:
        decision = "create_hub_priority"
        reason = "High-value opportunity eligible for hub priority"
        recommended_surface = "hub"
    elif score >= thresholds["queue"]:
        decision = "create_queue"
        reason = "Opportunity eligible for presence queue"
        recommended_surface = "queue"
    elif score >= thresholds["low_priority_queue"]:
        decision = "create_low_priority_queue"
        reason = "Opportunity retained in low-priority queue"
        recommended_surface = "queue"
    else:
        decision = "no_opportunity"
        reason = "Priority too low"
        recommended_surface = "none"

    return {
        "score": round(score, 4),
        "decision": decision,
        "reason": reason,
        "create_opportunity": decision != "no_opportunity",
        "recommended_surface": recommended_surface,
        "factors": factors,
        "algorithm": contract_trace(PRESENCE_PRIORITY_CONTRACT),
    }


def personalize_presence_priority(
    base_result: dict[str, Any],
    *,
    acceptance_rate: float,
    recent_dismissal_penalty: float = 0.0,
) -> dict[str, Any]:
    """Calibrate a deterministic base score with Companion-scoped feedback."""
    base_score = clamp01(base_result.get("score"))
    acceptance_rate = clamp01(acceptance_rate, 0.5)
    dismissal_penalty = clamp01(recent_dismissal_penalty)
    acceptance_multiplier = 0.7 + (0.6 * acceptance_rate)
    dismissal_multiplier = 1.0 - (0.45 * dismissal_penalty)
    score = clamp01(base_score * acceptance_multiplier * dismissal_multiplier)
    thresholds = PRESENCE_PRIORITY_CONTRACT["thresholds"]

    if score >= thresholds["hub"]:
        decision = "create_hub_priority"
        surface = "hub"
    elif score >= thresholds["queue"]:
        decision = "create_queue"
        surface = "queue"
    elif score >= thresholds["low_priority_queue"]:
        decision = "create_low_priority_queue"
        surface = "queue"
    else:
        decision = "no_opportunity"
        surface = "none"

    return {
        **base_result,
        "base_score": round(base_score, 4),
        "score": round(score, 4),
        "decision": decision,
        "create_opportunity": decision != "no_opportunity",
        "recommended_surface": surface,
        "personalization": {
            "acceptance_rate": round(acceptance_rate, 4),
            "acceptance_multiplier": round(acceptance_multiplier, 4),
            "recent_dismissal_penalty": round(dismissal_penalty, 4),
            "dismissal_multiplier": round(dismissal_multiplier, 4),
            "formula": "base_priority * (0.7 + 0.6 * acceptance_rate) * (1 - 0.45 * recent_dismissal_penalty)",
            "policy_mode": "heuristic",
        },
    }


CONTINUATION_WORDS = [
    "下次", "之后", "继续", "提醒我", "后续", "明天", "改天",
    "以后再", "稍后", "等下", "过几天", "未来", "接下来",
    "下一步", "改日", "回头", "等我回来",
]

GOAL_WORDS = ["目标", "计划", "项目", "阶段", "推进", "完成"]

TIME_WORDS = ["明天", "下周", "改天", "今晚", "稍后", "过几天", "尽快"]


def _detect_continuity(text: str) -> float:
    lower = text.lower()
    matches = sum(1 for w in CONTINUATION_WORDS if w in lower)
    if matches >= 2: return 0.88
    if matches == 1: return 0.70
    return 0.05


def _detect_goal(text: str) -> float:
    lower = text.lower()
    matches = sum(1 for w in GOAL_WORDS if w in lower)
    if matches >= 2: return 0.80
    if matches == 1: return 0.50
    return 0.1


def _detect_time_sensitivity(text: str) -> float:
    lower = text.lower()
    matches = sum(1 for w in TIME_WORDS if w in lower)
    if matches >= 1: return 0.75
    return 0.05


def _has_continuation_signal(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in CONTINUATION_WORDS)
