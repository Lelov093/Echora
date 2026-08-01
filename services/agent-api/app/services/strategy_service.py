"""Strategy learning services."""

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.core.algorithm_contract import clamp01
from app.db.models import (
    FeedbackEvent,
    Memory,
    MemoryUsageEvent,
    MemoryRerankerRun,
    PresencePolicyFeedbackSample,
    PresencePolicyRun,
    RerankerTrainingExample,
)
from app.memory.learned_reranker import memory_feature_vector, train_shadow_model
from app.services.feedback_service import sanitize_learning_payload
from app.services.persistence_helpers import create_row, default_ids, get_session, list_rows, row_to_dict


STRATEGY_WEIGHTS = {
    "context_fit": 0.25,
    "user_need_match": 0.20,
    "memory_support": 0.18,
    "relationship_fit": 0.15,
    "goal_progress_value": 0.12,
    "emotional_fit": 0.10,
    "boundary_risk": -0.20,
}

_COMPAT_PRESENCE_TYPE_KEY = "phase4_type"
_COMPAT_PRESENCE_SURFACE_KEY = "phase4_surface"
STRATEGY_PREFERENCE_LAMBDA = 0.10
STRATEGY_TIE_BREAK = (
    "boundary_preserving_support",
    "acknowledge_and_reframe",
    "co_presence_coordination",
    "multi_companion_presence",
    "structure_and_plan",
    "reflect_and_summarize",
    "creative_expand",
    "memory_based_continuation",
    "gentle_check_in",
)


def score_companionship_strategies(context: dict[str, Any]) -> dict[str, Any]:
    """Score every response strategy with deterministic, replayable factors."""
    signals = _normalized_signals(context.get("signals") or {})
    relationship = {
        key: clamp01(value, 0.5)
        for key, value in (context.get("relationship") or {}).items()
    }
    preferences = {
        key: max(-1.0, min(1.0, float(value)))
        for key, value in (context.get("preferences") or {}).items()
    }
    boundary_risk = clamp01(context.get("boundary_risk"))
    candidate_factors = _candidate_factors(signals, relationship, boundary_risk)
    candidates = []

    for tie_index, strategy in enumerate(STRATEGY_TIE_BREAK):
        factors = candidate_factors[strategy]
        base_score = sum(
            STRATEGY_WEIGHTS[name] * clamp01(factors.get(name))
            for name in STRATEGY_WEIGHTS
        )
        preference = preferences.get(strategy, 0.0)
        preference_adjustment = STRATEGY_PREFERENCE_LAMBDA * preference
        adjusted = max(0.0, min(1.0, base_score + preference_adjustment))
        candidates.append(
            {
                "strategy": strategy,
                "base_score": round(max(0.0, min(1.0, base_score)), 4),
                "preference": round(preference, 4),
                "preference_adjustment": round(preference_adjustment, 4),
                "adjusted_score": round(adjusted, 4),
                "factors": {key: round(value, 4) for key, value in factors.items()},
                "tie_break_order": tie_index,
            }
        )

    signal_strength = max(signals.values(), default=0.0)
    fallback = signal_strength < 0.20 and boundary_risk < 0.40
    if fallback:
        selected = next(item for item in candidates if item["strategy"] == "gentle_check_in")
        selection_reason = "deterministic_fallback_no_sufficient_signal"
    else:
        selected = max(
            candidates,
            key=lambda item: (item["adjusted_score"], -item["tie_break_order"]),
        )
        selection_reason = "highest_adjusted_score_stable_tie_break"

    ranked = sorted(
        candidates,
        key=lambda item: (-item["adjusted_score"], item["tie_break_order"]),
    )
    for item in candidates:
        item["selected"] = item["strategy"] == selected["strategy"]
        item["exclusion_reason"] = (
            None
            if item["selected"]
            else (
                "fallback_requires_gentle_check_in"
                if fallback
                else "lower_adjusted_score_or_later_tie_break"
            )
        )

    return {
        "selected_strategy": selected["strategy"],
        "selected_score": selected["adjusted_score"],
        "selection_reason": selection_reason,
        "fallback_applied": fallback,
        "signal_strength": round(signal_strength, 4),
        "boundary_risk": round(boundary_risk, 4),
        "candidates": candidates,
        "ranking": [item["strategy"] for item in ranked],
        "weights": dict(STRATEGY_WEIGHTS),
        "preference_lambda": STRATEGY_PREFERENCE_LAMBDA,
        "policy_mode": "heuristic",
        "algorithm_version": "core-r7-strategy-v1",
    }


def get_companion_strategy_preferences(companion_id: uuid.UUID) -> dict[str, float]:
    """Aggregate explicit strategy feedback without crossing Companion scope."""
    with get_session() as session:
        feedback = list(
            session.execute(
                select(FeedbackEvent).where(
                    FeedbackEvent.companion_id == companion_id,
                    FeedbackEvent.target_type.in_(["assistant_response", "strategy"]),
                    FeedbackEvent.feedback_source == "explicit",
                    FeedbackEvent.deleted_at.is_(None),
                )
            ).scalars().all()
        )
    rewards: dict[str, list[float]] = defaultdict(list)
    for event in feedback:
        strategy = str((event.context_json or {}).get("response_strategy") or "")
        if strategy in STRATEGY_TIE_BREAK:
            rewards[strategy].append(max(-1.0, min(1.0, float(event.reward))))
    return {
        strategy: round(sum(values) / len(values), 4)
        for strategy, values in rewards.items()
        if values
    }


def _normalized_signals(signals: dict[str, Any]) -> dict[str, float]:
    keys = (
        "correction",
        "planning",
        "reflection",
        "creative",
        "memory",
        "co_presence",
        "shared_scene",
        "goal",
        "emotional",
    )
    return {key: clamp01(signals.get(key)) for key in keys}


def _candidate_factors(
    signals: dict[str, float],
    relationship: dict[str, float],
    boundary_risk: float,
) -> dict[str, dict[str, float]]:
    familiarity = relationship.get("familiarity", 0.5)
    understanding = relationship.get("understanding", 0.5)
    collaboration = relationship.get("collaboration", 0.5)
    trust = relationship.get("trust", 0.5)
    closeness = relationship.get("emotional_closeness", 0.5)
    boundary_awareness = relationship.get("boundary_awareness", 0.5)
    continuity = relationship.get("continuity", 0.5)
    co_signal = max(signals["co_presence"], signals["shared_scene"])

    def factors(context_fit, user_need, memory, relationship_fit, goal, emotional, residual_risk=None):
        return {
            "context_fit": clamp01(context_fit),
            "user_need_match": clamp01(user_need),
            "memory_support": clamp01(memory),
            "relationship_fit": clamp01(relationship_fit),
            "goal_progress_value": clamp01(goal),
            "emotional_fit": clamp01(emotional),
            "boundary_risk": clamp01(boundary_risk if residual_risk is None else residual_risk),
        }

    return {
        "acknowledge_and_reframe": factors(
            signals["correction"], signals["correction"], signals["memory"] * 0.5,
            understanding, signals["goal"] * 0.4, max(0.6, signals["emotional"]),
        ),
        "co_presence_coordination": factors(
            signals["shared_scene"], co_signal, signals["memory"] * 0.5,
            (collaboration + trust) / 2, max(0.6, signals["goal"]), 0.5,
        ),
        "multi_companion_presence": factors(
            signals["co_presence"], signals["co_presence"], signals["memory"] * 0.4,
            (familiarity + collaboration) / 2, max(0.5, signals["goal"]), 0.55,
        ),
        "structure_and_plan": factors(
            max(signals["planning"], signals["goal"] * 0.7), signals["planning"],
            signals["memory"] * 0.5, collaboration, max(0.8, signals["goal"]), 0.35,
        ),
        "reflect_and_summarize": factors(
            signals["reflection"], max(signals["reflection"], signals["emotional"] * 0.6),
            signals["memory"], (understanding + closeness) / 2, signals["goal"] * 0.4,
            max(0.75, signals["emotional"]),
        ),
        "creative_expand": factors(
            signals["creative"], signals["creative"], signals["memory"] * 0.3,
            collaboration, max(0.55, signals["goal"]), 0.75,
        ),
        "memory_based_continuation": factors(
            signals["memory"], max(signals["memory"], signals["reflection"] * 0.5),
            signals["memory"], continuity, max(0.45, signals["goal"]), 0.55,
        ),
        "boundary_preserving_support": factors(
            max(boundary_risk, signals["emotional"] * 0.5), max(boundary_risk, signals["emotional"]),
            signals["memory"] * 0.2, boundary_awareness, signals["goal"] * 0.25,
            max(0.8, signals["emotional"]), residual_risk=boundary_risk * 0.1,
        ),
        "gentle_check_in": factors(
            0.35, 1.0 - max(signals.values()), signals["memory"] * 0.2,
            (familiarity + closeness) / 2, signals["goal"] * 0.2, 0.8,
        ),
    }


def _ensure_learning_mode(data: dict) -> dict:
    data.pop("allow_active", None)
    if data.get("learning_mode", "shadow") not in {"disabled", "shadow"}:
        raise ValueError(
            "assistive/active policy modes require a separately approved task"
        )
    return data


def _feedback_label_score(feedback: FeedbackEvent) -> float:
    raw = (feedback.label or feedback.action or "").lower()
    if raw in {"positive", "helpful", "accepted", "accept", "continued", "useful", "correct"}:
        return 1.0
    if raw in {"negative", "strong_negative", "irrelevant", "rejected", "reject", "wrong", "outdated", "deleted", "delete"}:
        return -1.0
    return 0.0


def create_reranker_example(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        payload = dict(data)
        feedback = None
        memory = session.get(Memory, uuid.UUID(str(payload["memory_id"]))) if payload.get("memory_id") else None
        if memory is not None:
            requested_companion = payload.get("companion_id")
            if requested_companion and uuid.UUID(str(requested_companion)) != memory.companion_id:
                raise ValueError("Reranker sample violates Companion ownership boundary")
            uid, cid = memory.user_id, memory.companion_id
        payload.setdefault("user_id", uid)
        payload.setdefault("companion_id", cid)
        payload.setdefault("source_type", "manual")
        payload["feature_json"] = sanitize_learning_payload(payload.get("feature_json", {}))
        if "metadata" in payload:
            payload["metadata_"] = sanitize_learning_payload(payload.pop("metadata"))
        return create_row(session, RerankerTrainingExample, payload)


def build_reranker_example_from_feedback(feedback_event_id: uuid.UUID, data: dict | None = None) -> dict | None:
    with get_session() as session:
        feedback = session.get(FeedbackEvent, feedback_event_id)
        if feedback is None or not feedback.training_eligible or feedback.redaction_status == "blocked":
            return None
        existing = session.query(RerankerTrainingExample).filter(
            RerankerTrainingExample.feedback_event_id == feedback.id,
            RerankerTrainingExample.deleted_at.is_(None),
        ).first()
        if existing:
            return row_to_dict(existing)

        payload = dict(data or {})
        memory_id = payload.get("memory_id")
        if memory_id is None and feedback.target_type == "memory":
            memory_id = feedback.target_id
        memory = session.get(Memory, memory_id) if memory_id else None
        if memory is not None and memory.companion_id != feedback.companion_id:
            return None
        usage = None
        if memory is not None:
            usage = session.execute(
                select(MemoryUsageEvent)
                .where(
                    MemoryUsageEvent.memory_id == memory.id,
                    MemoryUsageEvent.companion_id == feedback.companion_id,
                )
                .order_by(MemoryUsageEvent.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        reranker_features = (
            memory_feature_vector(
                memory,
                semantic_similarity=usage.semantic_similarity if usage else 0.0,
                heuristic_score=usage.retrieval_score if usage else 0.0,
                score_json=usage.score_json if usage else {},
            )
            if memory is not None
            else {}
        )
        feature_json = sanitize_learning_payload(
            payload.get(
                "feature_json",
                {
                    "feedback_label": feedback.label,
                    "feedback_action": feedback.action,
                    "feedback_source": feedback.feedback_source,
                    "reward": feedback.reward,
                    "context_hash": feedback.context_hash,
                    "algorithm_version": feedback.algorithm_version,
                    "reranker_features": reranker_features,
                },
            )
        )
        row = RerankerTrainingExample(
            user_id=feedback.user_id,
            companion_id=feedback.companion_id,
            memory_id=memory_id,
            feedback_event_id=feedback.id,
            memory_usage_event_id=usage.id if usage else None,
            label=payload.get("label", _feedback_label_score(feedback)),
            feature_json=feature_json,
            source_type="feedback",
            metadata_=sanitize_learning_payload(
                {
                    "sample_provenance": feedback.sample_provenance,
                    "feedback_algorithm_key": feedback.algorithm_key,
                    "feedback_algorithm_version": feedback.algorithm_version,
                }
            ),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row_to_dict(row)


def train_memory_reranker(companion_id: uuid.UUID) -> dict:
    return train_shadow_model(companion_id)


def list_reranker_examples(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, RerankerTrainingExample, filters, page, page_size)


def create_memory_reranker_run(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        payload = _ensure_learning_mode(data)
        payload.setdefault("user_id", uid)
        payload.setdefault("companion_id", cid)
        payload.setdefault("learning_mode", "shadow")
        payload.setdefault("status", "completed")
        return create_row(session, MemoryRerankerRun, payload)


def list_memory_reranker_runs(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, MemoryRerankerRun, filters, page, page_size)


def create_presence_feedback_sample(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        payload = dict(data)
        if payload.get("companion_id"):
            from app.db.models import Companion

            companion = session.get(
                Companion,
                uuid.UUID(str(payload["companion_id"])),
            )
            if companion is None:
                raise ValueError("Companion not found")
            if (
                payload.get("user_id")
                and uuid.UUID(str(payload["user_id"])) != companion.user_id
            ):
                raise ValueError("Presence sample violates user ownership boundary")
            uid, cid = companion.user_id, companion.id
        if payload.get("feedback_event_id"):
            feedback = session.get(
                FeedbackEvent,
                uuid.UUID(str(payload["feedback_event_id"])),
            )
            if feedback is None:
                raise ValueError("Feedback event not found")
            if (
                payload.get("companion_id")
                and feedback.companion_id
                != uuid.UUID(str(payload["companion_id"]))
            ):
                raise ValueError("Presence sample feedback crosses Companion boundary")
            uid, cid = feedback.user_id, feedback.companion_id
        opportunity = None
        if payload.get("presence_opportunity_id"):
            from app.db.models import PresenceOpportunity

            opportunity = session.get(
                PresenceOpportunity,
                uuid.UUID(str(payload["presence_opportunity_id"])),
            )
            if opportunity is None:
                raise ValueError("Presence opportunity not found")
            requested_companion = payload.get("companion_id")
            if requested_companion and uuid.UUID(str(requested_companion)) != opportunity.companion_id:
                raise ValueError("Presence sample violates Companion ownership boundary")
            if feedback is not None and feedback.companion_id != opportunity.companion_id:
                raise ValueError("Presence sample links cross-Companion evidence")
            uid, cid = opportunity.user_id, opportunity.companion_id
            payload.setdefault(
                "action_taken",
                _presence_action_from_surface(opportunity.recommended_surface),
            )
            payload.setdefault(
                "feature_json",
                {
                    "opportunity_type": str(
                        (opportunity.calibration_json or {}).get("presence_type")
                        or (opportunity.calibration_json or {}).get(
                            _COMPAT_PRESENCE_TYPE_KEY
                        )
                        or opportunity.type
                    ),
                    "surface": str(
                        (opportunity.calibration_json or {}).get("presence_surface")
                        or (opportunity.calibration_json or {}).get(
                            _COMPAT_PRESENCE_SURFACE_KEY
                        )
                        or opportunity.recommended_surface
                    ),
                    "interruption_risk": float(opportunity.interruption_risk or 0.0),
                },
            )
        payload.setdefault("user_id", uid)
        payload.setdefault("companion_id", cid)
        if payload.get("action_taken") not in {"no_show", "silence", "defer", "hub", "queue"}:
            raise ValueError("Presence sample action is outside the safe action space")
        payload["reward"] = max(-1.0, min(1.0, float(payload.get("reward", 0.0))))
        payload["feature_json"] = sanitize_learning_payload(payload.get("feature_json", {}))
        if "metadata" in payload:
            payload["metadata_"] = sanitize_learning_payload(payload.pop("metadata"))
        return create_row(session, PresencePolicyFeedbackSample, payload)


def _presence_action_from_surface(surface: str) -> str:
    return {
        "silent": "silence",
        "none": "no_show",
        "hub": "hub",
        "inline": "hub",
        "scene_panel": "hub",
        "session_surface": "hub",
        "queue": "queue",
        "hub_queue": "queue",
    }.get(str(surface), "queue")


def list_presence_feedback_samples(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, PresencePolicyFeedbackSample, filters, page, page_size)


def create_presence_policy_run(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        payload = _ensure_learning_mode(data)
        payload.setdefault("user_id", uid)
        payload.setdefault("companion_id", cid)
        payload.setdefault("learning_mode", "shadow")
        payload.setdefault("selected_action", "no_show")
        return create_row(session, PresencePolicyRun, payload)


def list_presence_policy_runs(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, PresencePolicyRun, filters, page, page_size)
