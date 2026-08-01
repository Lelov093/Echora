"""Conservative Companion-scoped contextual presence policy in shadow mode."""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.db.models import Companion, PresencePolicyFeedbackSample, PresencePolicyRun
from app.services.feedback_service import sanitize_learning_payload
from app.services.persistence_helpers import get_session, row_to_dict


ALGORITHM_VERSION = "core-r10-contextual-presence-shadow-v1"
POLICY_MODE = "shadow"
SAFE_ACTIONS = ("no_show", "silence", "defer", "hub", "queue")
FEATURE_SCHEMA = (
    "relationship_fit",
    "focus_load",
    "goal_progress",
    "continuity_importance",
    "recent_acceptance",
    "recent_dismissal",
    "interruption_risk",
    "has_scene_context",
    "has_channel_context",
    "surface",
)
_PRIOR_REWARD = {
    "no_show": 0.12,
    "silence": 0.15,
    "defer": 0.08,
    "hub": 0.03,
    "queue": 0.02,
}


def evaluate_shadow_policy(
    companion_id: uuid.UUID,
    opportunity_type: str,
    heuristic_action: str,
    *,
    context: dict[str, Any] | None = None,
    suppression: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score safe actions and persist a non-executing shadow decision."""
    features = _context_features(context or {})
    suppression = suppression or {}
    samples = _load_samples(companion_id, opportunity_type)
    grouped: dict[str, list[float]] = defaultdict(list)
    for sample in samples:
        if sample.action_taken in SAFE_ACTIONS:
            grouped[sample.action_taken].append(max(-1.0, min(1.0, sample.reward)))

    action_details = []
    for action in SAFE_ACTIONS:
        rewards = grouped[action]
        count = len(rewards)
        posterior = (sum(rewards) + (2.0 * _PRIOR_REWARD[action])) / (count + 2.0)
        context_adjustment = _context_adjustment(action, features)
        exploration_bonus = min(0.04, 0.04 / math.sqrt(count + 1.0))
        score = max(
            -1.0,
            min(1.0, posterior + context_adjustment + exploration_bonus),
        )
        action_details.append(
            {
                "action": action,
                "sample_count": count,
                "reward_sum": round(sum(rewards), 6),
                "posterior_reward": round(posterior, 6),
                "context_adjustment": round(context_adjustment, 6),
                "conservative_exploration_bonus": round(exploration_bonus, 6),
                "score": round(score, 6),
            }
        )

    safety_forced_action = None
    if suppression.get("hard_block"):
        safety_forced_action = "no_show"
    elif suppression.get("suppress"):
        safety_forced_action = "silence"
    if safety_forced_action:
        selected = next(
            item for item in action_details if item["action"] == safety_forced_action
        )
        selection_reason = f"safety_gate:{suppression.get('reason') or 'suppressed'}"
    else:
        selected = max(
            action_details,
            key=lambda item: (item["score"], -SAFE_ACTIONS.index(item["action"])),
        )
        selection_reason = "highest_conservative_shadow_value"

    propensities = _softmax_propensities(action_details)
    for item in action_details:
        item["propensity"] = propensities[item["action"]]
        item["selected"] = item["action"] == selected["action"]

    with get_session() as session:
        companion = session.get(Companion, companion_id)
        if companion is None:
            raise ValueError("Companion not found")
        row = PresencePolicyRun(
            user_id=companion.user_id,
            companion_id=companion_id,
            conversation_id=_optional_uuid((context or {}).get("conversation_id")),
            trace_run_id=_optional_uuid((context or {}).get("trace_run_id")),
            presence_opportunity_id=_optional_uuid(
                (context or {}).get("presence_opportunity_id")
            ),
            learning_mode=POLICY_MODE,
            action_space=list(SAFE_ACTIONS),
            selected_action=selected["action"],
            reward_prediction=selected["posterior_reward"],
            explanation_json=sanitize_learning_payload(
                {
                    "algorithm_version": ALGORITHM_VERSION,
                    "feature_schema": list(FEATURE_SCHEMA),
                    "policy_mode": POLICY_MODE,
                    "user_visible_policy": "heuristic",
                    "heuristic_action": _normalize_heuristic_action(heuristic_action),
                    "shadow_action": selected["action"],
                    "selection_reason": selection_reason,
                    "selected_propensity": propensities[selected["action"]],
                    "opportunity_type": opportunity_type,
                    "context_features": features,
                    "action_details": action_details,
                    "sample_scope": {
                        "companion_id": str(companion_id),
                        "opportunity_type": opportunity_type,
                        "sample_count": len(samples),
                    },
                    "suppression": {
                        "suppress": bool(suppression.get("suppress")),
                        "hard_block": bool(suppression.get("hard_block")),
                        "reason": suppression.get("reason"),
                    },
                    "actual_action_changed": False,
                    "random_user_exploration": False,
                }
            ),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        result = row_to_dict(row)
    return {
        **result,
        "policy_mode": POLICY_MODE,
        "heuristic_action": _normalize_heuristic_action(heuristic_action),
        "shadow_action": selected["action"],
        "selected_propensity": propensities[selected["action"]],
        "actual_action_changed": False,
        "safety_forced_action": safety_forced_action,
    }


def _load_samples(
    companion_id: uuid.UUID,
    opportunity_type: str,
) -> list[PresencePolicyFeedbackSample]:
    with get_session() as session:
        rows = list(
            session.execute(
                select(PresencePolicyFeedbackSample).where(
                    PresencePolicyFeedbackSample.companion_id == companion_id,
                    PresencePolicyFeedbackSample.deleted_at.is_(None),
                )
            ).scalars()
        )
        result = [
            row
            for row in rows
            if str((row.feature_json or {}).get("opportunity_type") or "unknown")
            == opportunity_type
        ]
        session.expunge_all()
        return result


def _context_features(context: dict[str, Any]) -> dict[str, Any]:
    user_state = context.get("user_state") or {}
    relationship = context.get("relationship") or {}
    feedback = context.get("feedback_profile") or {}
    return {
        "relationship_fit": _clamp01(
            context.get("relationship_fit", relationship.get("collaboration", 0.5))
        ),
        "focus_load": _clamp01(
            context.get("focus_load", user_state.get("focus_load", 0.5))
        ),
        "goal_progress": _clamp01(context.get("goal_progress", 0.0)),
        "continuity_importance": _clamp01(
            context.get("continuity_importance", 0.0)
        ),
        "recent_acceptance": _clamp01(
            context.get("recent_acceptance", feedback.get("acceptance_rate", 0.5))
        ),
        "recent_dismissal": _clamp01(
            context.get(
                "recent_dismissal",
                feedback.get("recent_dismissal_penalty", 0.0),
            )
        ),
        "interruption_risk": _clamp01(context.get("interruption_risk", 0.0)),
        "has_scene_context": bool(context.get("shared_scene_id")),
        "has_channel_context": bool(context.get("channel_id")),
        "surface": str(context.get("surface") or "queue"),
    }


def _context_adjustment(action: str, features: dict[str, Any]) -> float:
    interruption = features["interruption_risk"]
    dismissal = features["recent_dismissal"]
    focus = features["focus_load"]
    goal = features["goal_progress"]
    continuity = features["continuity_importance"]
    acceptance = features["recent_acceptance"]
    if action == "no_show":
        return (0.16 * interruption) + (0.10 * dismissal) + (0.06 * focus)
    if action == "silence":
        return (0.18 * interruption) + (0.08 * dismissal) + (0.08 * focus)
    if action == "defer":
        return (0.08 * interruption) + (0.06 * focus) + (0.03 * continuity)
    if action == "hub":
        return (
            (0.07 * goal)
            + (0.07 * continuity)
            + (0.03 * features["relationship_fit"])
            - (0.10 * interruption)
        )
    return (
        (0.08 * goal)
        + (0.08 * continuity)
        + (0.06 * acceptance)
        - (0.12 * interruption)
        - (0.08 * dismissal)
    )


def _softmax_propensities(action_details: list[dict[str, Any]]) -> dict[str, float]:
    exponentials = {
        item["action"]: math.exp(2.0 * item["score"]) for item in action_details
    }
    total = sum(exponentials.values()) or 1.0
    return {
        action: round(value / total, 6) for action, value in exponentials.items()
    }


def _normalize_heuristic_action(action: str) -> str:
    mapping = {
        "none": "no_show",
        "silent": "silence",
        "scene_panel": "hub",
        "session_surface": "hub",
        "hub_queue": "queue",
        "invite_scene": "hub",
    }
    normalized = mapping.get(str(action), str(action))
    return normalized if normalized in SAFE_ACTIONS else "queue"


def _clamp01(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))


def _optional_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
