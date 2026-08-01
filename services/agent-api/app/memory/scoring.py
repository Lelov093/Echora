"""Memory Candidate Scoring — Core conversation heuristic formula.

Official thresholds (per docs/Echora Core conversation 首轮 Coding 闭环范围 V1.txt):
  score >= 0.80 → high priority candidate
  0.55 <= score < 0.80 → normal candidate
  0.35 <= score < 0.55 → working memory only (no long-term candidate)
  score < 0.35 → no candidate
  correction_value >= 0.80 → force correction memory candidate
"""

from typing import Any

from app.core.algorithm_contract import (
    MEMORY_CANDIDATE_CONTRACT,
    clamp01,
    contract_trace,
    weighted_score,
)


def score_memory_candidate(
    user_input: str,
    assistant_response: str = "",
    sensory_signals: dict[str, Any] | None = None,
    working_memory: dict[str, Any] | None = None,
) -> dict:
    """Compute memory_candidate_score using Core conversation heuristic weights.

    Returns dict with score, factors, decision, reason, and trace data.
    """
    sigs = sensory_signals or {}

    # ── Factor extraction ──────────────────────────────────────────
    detected = {
        "user_explicitness": _detect_explicitness(user_input),
        "goal_relevance": _detect_goal_relevance(user_input),
        "correction_value": _detect_correction(user_input),
        "relationship_impact": 0.1,
        "emotional_intensity": 0.1,
        "novelty": _detect_novelty(user_input),
        "recurrence": 0.0,
        "triviality": _detect_triviality(user_input),
        "sensitivity_risk": 0.05,
    }
    factors = {
        name: clamp01(sigs.get(name, default), default)
        for name, default in detected.items()
    }
    feature_sources = {
        name: "sensory_signals" if name in sigs else "heuristic_detector"
        for name in detected
    }
    adjustments: list[str] = []

    # ── Boost when user explicitly says "remember" ─────────────────
    # If the user explicitly signals memory intent, the content is
    # inherently important across multiple dimensions.
    if factors["user_explicitness"] >= 0.7:
        factors["goal_relevance"] = max(factors["goal_relevance"], 0.85)
        factors["relationship_impact"] = max(factors["relationship_impact"], 0.60)
        factors["emotional_intensity"] = max(factors["emotional_intensity"], 0.40)
        factors["novelty"] = max(factors["novelty"], 0.85)
        factors["recurrence"] = max(factors["recurrence"], 0.60)
        adjustments.append("explicit_memory_intent_boost")

    # ── Weighted scoring formula ───────────────────────────────────
    score = weighted_score(factors, MEMORY_CANDIDATE_CONTRACT)
    thresholds = MEMORY_CANDIDATE_CONTRACT["thresholds"]

    # ── Decision (official Core conversation thresholds) ─────────────────────
    if factors["correction_value"] >= thresholds["correction_force"]:
        decision = "create_correction_candidate"
        reason = "High correction signal forces memory candidate"
        create_candidate = True
        working_memory_only = False
        forced_by_correction = True
    elif score >= thresholds["high_priority"]:
        decision = "create_high_priority_candidate"
        reason = "High score — important memory, recommend user confirmation"
        create_candidate = True
        working_memory_only = False
        forced_by_correction = False
    elif score >= thresholds["candidate"]:
        decision = "create_candidate"
        reason = "Normal score — store as candidate for review"
        create_candidate = True
        working_memory_only = False
        forced_by_correction = False
    elif score >= thresholds["working_memory"]:
        decision = "working_memory_only"
        reason = "Moderate score — keep in working memory, no long-term candidate"
        create_candidate = False
        working_memory_only = True
        forced_by_correction = False
    else:
        decision = "no_candidate"
        reason = "Score too low — no candidate"
        create_candidate = False
        working_memory_only = False
        forced_by_correction = False

    return {
        "score": round(score, 4),
        "decision": decision,
        "reason": reason,
        "factors": factors,
        "algorithm": contract_trace(
            MEMORY_CANDIDATE_CONTRACT,
            feature_sources=feature_sources,
        ),
        "adjustments": adjustments,
        "create_candidate": create_candidate,
        "working_memory_only": working_memory_only,
        "forced_by_correction": forced_by_correction,
        "suggested_type": (
            "correction" if factors["correction_value"] >= thresholds["correction_force"]
            else "preference" if factors["user_explicitness"] >= 0.7
            else "goal" if factors["goal_relevance"] >= 0.7
            else "episodic"
        ),
    }


# ── Heuristic detectors ──────────────────────────────────────────────

MEMORY_SIGNAL_WORDS = [
    "记住", "不要忘", "以后都要", "我一直", "我的习惯", "我喜欢",
    "我的目标", "我正在做", "我的原则", "我偏好", "我希望",
    "长期目标", "我的计划", "我最", "我从不", "请记住", "不要忘记",
    "记下", "记录", "保存", "备忘",
]

CORRECTION_WORDS = [
    "纠正", "不对", "误解", "你错了", "不是这样", "理解错了",
    "你说的不对", "搞错了", "重新理解", "再想一下",
    "你之前说的不对", "更正", "修正",
]

GOAL_WORDS = [
    "目标", "计划", "项目", "阶段", "下一步", "路线", "规划",
    "实现", "完成", "推进", "方向", "蓝图", "原则", "策略",
    "方案", "设计", "架构", "开发",
]

TRIVIAL_WORDS = [
    "天气", "你好", "嗨", "嗯", "哦", "行", "知道了",
    "哈哈", "是的", "对的", "ok", "hi", "hello",
    "随便", "困", "还行", "一般", "没事",
]


def _detect_explicitness(text: str) -> float:
    lower = text.lower()
    matches = sum(1 for w in MEMORY_SIGNAL_WORDS if w in lower)
    if matches >= 2:
        return 0.95
    if matches == 1:
        return 0.80
    return 0.05


def _detect_correction(text: str) -> float:
    lower = text.lower()
    matches = sum(1 for w in CORRECTION_WORDS if w in lower)
    if matches >= 2:
        return 0.92
    if matches == 1:
        return 0.82
    return 0.0


def _detect_goal_relevance(text: str) -> float:
    lower = text.lower()
    matches = sum(1 for w in GOAL_WORDS if w in lower)
    if matches >= 3:
        return 0.88
    if matches >= 1:
        return 0.65
    return 0.1


def _detect_triviality(text: str) -> float:
    lower = text.lower()
    if len(text) < 5:
        return 0.90
    if len(text) < 10 and any(w in lower for w in TRIVIAL_WORDS):
        return 0.80
    if any(w in lower for w in TRIVIAL_WORDS) and len(text) < 20:
        return 0.60
    return 0.08


def _detect_novelty(text: str) -> float:
    """Novelty: longer, content-rich inputs are more novel."""
    if len(text) < 5:
        return 0.1
    if len(text) < 15:
        return 0.4
    if len(text) < 30:
        return 0.6
    return 0.75
