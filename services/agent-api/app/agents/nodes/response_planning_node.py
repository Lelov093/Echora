"""Select an explainable, Companion-scoped response strategy."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import co_presence_service
from app.services.relationship_service import get_relationship_state
from app.services.strategy_service import (
    get_companion_strategy_preferences,
    score_companionship_strategies,
)

_CORRECTION_KEYWORDS = (
    "纠正", "不对", "误解", "你错了", "不是这样", "理解错了",
    "correct", "wrong", "misunderstood",
)
_PLANNING_KEYWORDS = (
    "规划", "计划", "下一步", "结构", "整理", "阶段",
    "plan", "next step", "organize", "roadmap",
)
_REFLECTION_KEYWORDS = (
    "总结", "回顾", "复盘", "之前", "上次", "记录",
    "reflect", "review", "summarize", "recap",
)
_CREATIVE_KEYWORDS = (
    "创意", "灵感", "想象", "故事", "设计",
    "creative", "brainstorm", "imagine", "story",
)
_GOAL_KEYWORDS = (
    "目标", "完成", "推进", "交付", "项目",
    "goal", "finish", "deliver", "project",
)
_EMOTIONAL_KEYWORDS = (
    "难过", "焦虑", "担心", "压力", "开心", "兴奋",
    "sad", "anxious", "worried", "stressed", "happy", "excited",
)
_BOUNDARY_KEYWORDS = (
    "不要", "停止", "别再", "不想", "边界", "隐私",
    "stop", "do not", "don't", "boundary", "privacy",
)


def response_planning_node(state: ConversationAgentState) -> ConversationAgentState:
    user_input = state.get("user_input", "").lower()
    mode = state.get("current_mode", "project")
    memories = state.get("selected_memories", [])
    co_present_companions = state.get("co_present_companions", [])
    shared_scene = state.get("shared_scene") or {}
    boundary_settings = state.get("boundary_settings") or {}
    persona_guard = state.get("persona_guard_result") or {}
    companion_id = uuid.UUID(state["companion_id"])

    relationship = (
        (state.get("companion_context_snapshot") or {})
        .get("relationship", {})
        .get("data", {})
    ) or get_relationship_state(companion_id) or {}
    preferences = get_companion_strategy_preferences(companion_id)
    boundary_risk = _boundary_risk(user_input, boundary_settings, persona_guard)
    guard_status = str(
        persona_guard.get("check_status")
        or persona_guard.get("decision")
        or ""
    ).lower()
    utility_boundary_risk = (
        min(boundary_risk, 0.65)
        if guard_status == "review_required"
        else boundary_risk
    )
    co_presence_utility = (
        co_presence_service.build_co_presence_utility_decision(
            companion_id,
            co_present_companions,
            context={
                "mode": mode,
                "has_goal": bool(
                    _keyword_signal(user_input, _GOAL_KEYWORDS)
                ),
                "has_shared_scene": bool(shared_scene),
                "shared_scene_id": shared_scene.get("id"),
                "boundary_risk": utility_boundary_risk,
            },
        )
        if co_present_companions
        else {}
    )
    if co_presence_utility:
        awareness = dict(state.get("participant_awareness") or {})
        awareness["co_presence_utility"] = co_presence_utility
        awareness["selected_speaker_companion_id"] = (
            co_presence_utility.get("selected_speaker_companion_id")
        )
        state["participant_awareness"] = awareness
    signals = {
        "correction": _keyword_signal(user_input, _CORRECTION_KEYWORDS),
        "planning": _keyword_signal(user_input, _PLANNING_KEYWORDS),
        "reflection": _keyword_signal(user_input, _REFLECTION_KEYWORDS),
        "creative": max(
            _keyword_signal(user_input, _CREATIVE_KEYWORDS),
            0.85 if mode == "creative" else 0.0,
        ),
        "memory": min(1.0, len(memories) / 3.0),
        "co_presence": 1.0 if co_present_companions else 0.0,
        "shared_scene": 1.0 if shared_scene else 0.0,
        "goal": _keyword_signal(user_input, _GOAL_KEYWORDS),
        "emotional": _keyword_signal(user_input, _EMOTIONAL_KEYWORDS),
    }
    decision = score_companionship_strategies(
        {
            "signals": signals,
            "relationship": relationship,
            "preferences": preferences,
            "boundary_risk": boundary_risk,
        }
    )
    strategy = decision["selected_strategy"]
    utility_veto = (
        str(persona_guard.get("check_status") or "").lower() == "blocked"
        or bool(persona_guard.get("blocks_auto_apply"))
        or boundary_risk >= 0.9
    )
    if utility_veto:
        strategy = "boundary_preserving_support"

    state["response_strategy"] = {
        "strategy": strategy,
        "mode": mode,
        "selected_memory_count": len(memories),
        "co_present_companion_count": len(co_present_companions),
        "shared_scene_id": shared_scene.get("id"),
        "selected_score": decision["selected_score"],
        "selection_reason": decision["selection_reason"],
        "fallback_applied": decision["fallback_applied"],
        "signals": signals,
        "relationship_features": relationship,
        "companion_preferences": preferences,
        "boundary_risk": boundary_risk,
        "candidate_scores": decision["candidates"],
        "algorithm_version": decision["algorithm_version"],
        "policy_mode": decision["policy_mode"],
        "co_presence_utility": co_presence_utility,
        "co_presence_utility_veto": utility_veto,
    }

    state.setdefault("trace_steps", []).append({
        "step": "response_planning",
        "order": 4,
        "status": "completed",
        "strategy": strategy,
        "selected_score": decision["selected_score"],
        "selection_reason": decision["selection_reason"],
        "fallback_applied": decision["fallback_applied"],
        "boundary_risk": boundary_risk,
        "signals": signals,
        "candidate_scores": decision["candidates"],
        "ranking": decision["ranking"],
        "weights": decision["weights"],
        "preference_lambda": decision["preference_lambda"],
        "algorithm_version": decision["algorithm_version"],
        "policy_mode": decision["policy_mode"],
        "co_presence_utility": co_presence_utility,
        "co_presence_utility_veto": utility_veto,
    })
    return state


def _keyword_signal(text: str, keywords: tuple[str, ...]) -> float:
    matches = sum(1 for keyword in keywords if keyword in text)
    if matches >= 2:
        return 1.0
    if matches == 1:
        return 0.75
    return 0.0


def _boundary_risk(user_input: str, settings: dict, persona_guard: dict) -> float:
    risk = _keyword_signal(user_input, _BOUNDARY_KEYWORDS)
    if settings.get("allow_presence") is False:
        risk = max(risk, 0.55)
    if str(settings.get("proactive_level", "")).lower() in {"off", "disabled", "none"}:
        risk = max(risk, 0.65)
    guard_status = str(persona_guard.get("check_status") or persona_guard.get("decision") or "").lower()
    if guard_status in {"blocked", "block", "review_required"}:
        risk = max(risk, 0.9)
    return min(1.0, risk)
