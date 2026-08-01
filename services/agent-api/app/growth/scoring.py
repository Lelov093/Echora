"""Growth Trigger Scoring — Core conversation heuristic formula.

Official thresholds:
  growth_trigger_score >= 0.75 → generate Growth Candidate
  0.50 <= score < 0.75 → queue reflection signal, no candidate
  score < 0.50 → no candidate
  correction_signal >= 0.85 → force Growth Candidate
"""

from typing import Any

from app.core.algorithm_contract import (
    GROWTH_TRIGGER_CONTRACT,
    clamp01,
    contract_trace,
    weighted_score,
)


def score_growth_trigger(
    user_input: str,
    correction_signal: float = 0.0,
    topic_recurrence: float = 0.0,
    emotional_intensity: float = 0.0,
    relationship_change: float = 0.0,
    understanding_gap: float = 0.0,
    selected_memories: list[dict[str, Any]] | None = None,
) -> dict:
    """Compute growth_trigger_score.

    At least one of correction_signal / understanding_gap / topic_recurrence
    should come from detected signals or selected memories context.
    """
    if correction_signal <= 0:
        correction_signal = _detect_correction(user_input)
    if understanding_gap <= 0:
        understanding_gap = _detect_understanding_gap(user_input)
    if topic_recurrence <= 0 and selected_memories:
        topic_recurrence = 0.3
    if emotional_intensity <= 0:
        emotional_intensity = 0.15

    factors = {
        "correction_signal": clamp01(correction_signal),
        "topic_recurrence": clamp01(topic_recurrence),
        "emotional_intensity": clamp01(emotional_intensity),
        "relationship_change": clamp01(relationship_change),
        "understanding_gap": clamp01(understanding_gap),
    }
    score = weighted_score(factors, GROWTH_TRIGGER_CONTRACT)
    thresholds = GROWTH_TRIGGER_CONTRACT["thresholds"]

    # Decision
    if factors["correction_signal"] >= thresholds["correction_force"]:
        decision = "force_candidate"
        reason = "High correction signal forces Growth Candidate"
        create_candidate = True
    elif score >= thresholds["candidate"]:
        decision = "create_candidate"
        reason = "Growth trigger score above threshold"
        create_candidate = True
    elif score >= thresholds["reflection_queue"]:
        decision = "reflection_queued"
        reason = "Growth signal queued for reflection below candidate threshold"
        create_candidate = False
    else:
        decision = "no_candidate"
        reason = "No significant growth signal"
        create_candidate = False

    return {
        "score": round(score, 4),
        "decision": decision,
        "reason": reason,
        "create_candidate": create_candidate,
        "factors": factors,
        "algorithm": contract_trace(GROWTH_TRIGGER_CONTRACT),
    }


CORRECTION_WORDS = [
    "纠正", "不对", "误解", "你错了", "不是这样", "理解错了", "更正", "修正",
    "准确来说", "你说的不对", "搞错了", "重新理解",
    "纠正", "不对", "误解", "你错了", "不是这样", "理解错了",
    "你说的不对", "搞错了", "重新理解", "你之前说的不对", "更正", "修正",
    "准确来说", "不是x", "不是游戏", "你理解错了",
]

UNDERSTANDING_GAP_WORDS = [
    "你不太理解", "你没理解", "你不明白", "你还没明白", "你漏掉了",
    "你忽略了", "请先理解", "不要这样回答", "我希望你以后", "回答时请",
    "你不太理解", "你没理解", "你搞不清楚", "你不明白", "你不懂",
    "你还没明白", "你再想想", "重新考虑", "你忘了一个重要",
    "你漏掉了", "你没注意到", "你之前忽略了",
]


def _detect_correction(text: str) -> float:
    lower = text.lower()
    matches = sum(1 for w in CORRECTION_WORDS if w in lower)
    if matches >= 2:
        return 0.92
    if matches == 1:
        return 0.82
    return 0.05


def _detect_understanding_gap(text: str) -> float:
    lower = text.lower()
    matches = sum(1 for w in UNDERSTANDING_GAP_WORDS if w in lower)
    if matches >= 2:
        return 0.80
    if matches == 1:
        return 0.60
    return 0.05
