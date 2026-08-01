"""Companion-scoped pairwise memory reranker running in shadow mode only."""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.algorithm_contract import clamp01
from app.db.models import Companion, Memory, MemoryRerankerRun, RerankerTrainingExample
from app.services.persistence_helpers import get_session, row_to_dict


ALGORITHM_VERSION = "core-r9-pairwise-logistic-v1"
POLICY_MODE = "shadow"
MIN_PAIR_COUNT = 2
FEATURE_SCHEMA = (
    "semantic_similarity",
    "heuristic_score",
    "memory_strength",
    "confidence",
    "goal_relevance",
    "relationship_impact",
    "feedback_signal",
    "correction_priority",
    "outdated_penalty",
)


def memory_feature_vector(
    memory: Memory,
    *,
    semantic_similarity: float = 0.0,
    heuristic_score: float = 0.0,
    score_json: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Build a content-free, bounded feature vector."""
    score_json = score_json or {}
    factors = score_json.get("factors") or {}
    feedback = score_json.get("feedback") or {}
    outdated = score_json.get("outdated") or {}
    stored_feedback = max(-1.0, min(1.0, float(memory.feedback_score or 0.0)))
    return {
        "semantic_similarity": clamp01(
            factors.get("semantic_similarity", semantic_similarity)
        ),
        "heuristic_score": clamp01(heuristic_score),
        "memory_strength": clamp01(
            factors.get("memory_strength", memory.memory_strength or 0.5)
        ),
        "confidence": clamp01(memory.confidence or 0.5),
        "goal_relevance": clamp01(
            factors.get("goal_relevance", memory.goal_relevance or 0.0)
        ),
        "relationship_impact": clamp01(
            factors.get("relationship_impact", memory.relationship_impact or 0.0)
        ),
        "feedback_signal": clamp01(
            (float(feedback.get("feedback_signal", stored_feedback)) + 1.0) / 2.0
        ),
        "correction_priority": clamp01(
            factors.get("correction_priority", memory.correction_value or 0.0)
        ),
        "outdated_penalty": clamp01(
            factors.get(
                "outdated_penalty",
                outdated.get(
                    "outdated_score",
                    (memory.outdated_count or 0) / ((memory.outdated_count or 0) + 2.0),
                ),
            )
        ),
    }


def train_shadow_model(companion_id: uuid.UUID) -> dict[str, Any]:
    """Train and persist a deterministic Companion-local pairwise model."""
    with get_session() as session:
        examples = list(
            session.execute(
                select(RerankerTrainingExample)
                .where(
                    RerankerTrainingExample.companion_id == companion_id,
                    RerankerTrainingExample.deleted_at.is_(None),
                    RerankerTrainingExample.memory_id.is_not(None),
                    RerankerTrainingExample.label != 0,
                )
                .order_by(RerankerTrainingExample.id)
            ).scalars()
        )
        points = []
        for example in examples:
            memory = session.get(Memory, example.memory_id)
            if (
                memory is None
                or memory.companion_id != companion_id
                or memory.owner_companion_id != companion_id
            ):
                continue
            supplied = (example.feature_json or {}).get("reranker_features")
            features = (
                _normalize_features(supplied)
                if isinstance(supplied, dict)
                else memory_feature_vector(memory)
            )
            points.append(
                {
                    "example_id": str(example.id),
                    "memory_id": str(memory.id),
                    "label": float(example.label),
                    "memory_type": memory.type,
                    "features": features,
                }
            )

        positives = [point for point in points if point["label"] > 0]
        negatives = [point for point in points if point["label"] < 0]
        pairs = [
            {
                "key": f"{positive['example_id']}:{negative['example_id']}",
                "positive": positive,
                "negative": negative,
            }
            for positive in positives
            for negative in negatives
            if positive["memory_id"] != negative["memory_id"]
        ]
        pairs.sort(key=lambda pair: pair["key"])
        if len(pairs) < MIN_PAIR_COUNT:
            return _persist_model_run(
                session,
                companion_id,
                points,
                weights={name: 0.0 for name in FEATURE_SCHEMA},
                model_status="insufficient_data",
                training_summary={
                    "example_count": len(points),
                    "positive_count": len(positives),
                    "negative_count": len(negatives),
                    "pair_count": len(pairs),
                    "minimum_pair_count": MIN_PAIR_COUNT,
                    "trained": False,
                },
                metrics={},
            )

        train_pairs, eval_pairs = _split_pairs(pairs)
        weights = _fit_pairwise_logistic(train_pairs)
        metrics = _evaluate(weights, eval_pairs)
        return _persist_model_run(
            session,
            companion_id,
            points,
            weights=weights,
            model_status="ready",
            training_summary={
                "example_count": len(points),
                "positive_count": len(positives),
                "negative_count": len(negatives),
                "pair_count": len(pairs),
                "train_pair_count": len(train_pairs),
                "evaluation_pair_count": len(eval_pairs),
                "split": "sha256_pair_key_mod_5_with_deterministic_holdout",
                "trained": True,
            },
            metrics=metrics,
        )


def latest_shadow_model(companion_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as session:
        rows = list(
            session.execute(
                select(MemoryRerankerRun)
                .where(
                    MemoryRerankerRun.companion_id == companion_id,
                    MemoryRerankerRun.learning_mode == POLICY_MODE,
                    MemoryRerankerRun.status == "completed",
                    MemoryRerankerRun.deleted_at.is_(None),
                )
                .order_by(MemoryRerankerRun.created_at.desc())
                .limit(50)
            ).scalars()
        )
        for row in rows:
            if (row.score_json or {}).get("run_kind") == "model_training":
                return row_to_dict(row)
    return None


def shadow_rank(
    companion_id: uuid.UUID,
    candidates: list[dict[str, Any]],
    *,
    top_k: int,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate learned ranks without changing the heuristic result order."""
    model = latest_shadow_model(companion_id)
    fallback_reason = None
    if not model:
        fallback_reason = "no_shadow_model"
    elif (model.get("score_json") or {}).get("model_status") != "ready":
        fallback_reason = "shadow_model_not_ready"
    elif tuple((model.get("score_json") or {}).get("feature_schema") or ()) != FEATURE_SCHEMA:
        fallback_reason = "feature_schema_mismatch"

    weights = (model or {}).get("score_json", {}).get("weights", {})
    scored = []
    for item in candidates:
        features = memory_feature_vector(
            item["memory"],
            semantic_similarity=item.get("semantic_similarity", 0.0),
            heuristic_score=item.get("retrieval_score", 0.0),
            score_json=item.get("score_json") or {},
        )
        if fallback_reason:
            learned_score = clamp01(item.get("retrieval_score"))
        else:
            learned_score = _sigmoid(
                sum(float(weights.get(name, 0.0)) * features[name] for name in FEATURE_SCHEMA)
            )
        scored.append(
            {
                "memory_id": str(item["memory"].id),
                "heuristic_rank": int(item["rank_after"]),
                "heuristic_score": round(float(item["retrieval_score"]), 6),
                "learned_score": round(learned_score, 6),
                "features": features,
            }
        )

    learned_order = sorted(
        scored,
        key=lambda item: (-item["learned_score"], item["memory_id"]),
    )
    learned_rank = {
        item["memory_id"]: rank for rank, item in enumerate(learned_order, start=1)
    }
    for item in scored:
        item["learned_rank"] = learned_rank[item["memory_id"]]

    run_id = _persist_shadow_decision(
        companion_id,
        scored,
        model,
        fallback_reason,
        top_k=top_k,
        context=context or {},
    )
    return {
        "policy_mode": POLICY_MODE,
        "user_visible_policy": "heuristic",
        "model_run_id": model.get("id") if model else None,
        "decision_run_id": run_id,
        "model_version": (model or {}).get("score_json", {}).get("model_version"),
        "fallback_reason": fallback_reason,
        "heuristic_rank": [
            item["memory_id"]
            for item in sorted(scored, key=lambda item: item["heuristic_rank"])
        ],
        "learned_rank": [item["memory_id"] for item in learned_order],
        "rank_comparison": scored,
    }


def evaluate_temporal_holdout(
    examples: list[RerankerTrainingExample],
    memories_by_id: dict[uuid.UUID, Memory],
    *,
    holdout_ratio: float = 0.2,
) -> dict[str, Any]:
    """Evaluate the pairwise ranker on a strict, latest-in-time holdout.

    This function is deliberately side-effect free. It never persists a model,
    changes retrieval order, or mixes Companion scopes. Callers remain
    responsible for supplying examples and memories from exactly one Companion.
    """
    points: list[dict[str, Any]] = []
    invalid_scope_example_ids: list[str] = []
    for example in sorted(
        examples,
        key=lambda item: (
            _aware_timestamp(item.created_at),
            str(item.id),
        ),
    ):
        memory = memories_by_id.get(example.memory_id)
        if (
            memory is None
            or memory.companion_id != example.companion_id
            or memory.owner_companion_id != example.companion_id
        ):
            invalid_scope_example_ids.append(str(example.id))
            continue
        supplied = (example.feature_json or {}).get("reranker_features")
        features = (
            _normalize_features(supplied)
            if isinstance(supplied, dict)
            else memory_feature_vector(memory)
        )
        if float(example.label) == 0:
            continue
        points.append(
            {
                "example_id": str(example.id),
                "memory_id": str(memory.id),
                "label": float(example.label),
                "memory_type": memory.type,
                "features": features,
                "created_at": _aware_timestamp(example.created_at),
                "outdated_flag": bool(
                    features["outdated_penalty"] > 0
                    or getattr(memory, "outdated_count", 0)
                    or getattr(memory, "wrong_count", 0)
                ),
                "conflict_flag": bool(
                    (example.feature_json or {}).get("conflict")
                    or (example.feature_json or {}).get("conflict_signal")
                    or (example.feature_json or {}).get("superseded")
                    or memory.type == "conflict"
                ),
            }
        )

    if len(points) < 2:
        return {
            "split": "latest_time_holdout",
            "example_count": len(points),
            "train_example_count": 0,
            "holdout_example_count": 0,
            "train_pair_count": 0,
            "holdout_pair_count": 0,
            "overlap_count": 0,
            "invalid_scope_count": len(invalid_scope_example_ids),
            "metrics": {},
            "unavailable_reason": "not_enough_scoped_nonzero_examples",
        }

    holdout_count = max(1, math.ceil(len(points) * max(0.1, min(0.5, holdout_ratio))))
    split_index = max(1, len(points) - holdout_count)
    train_points = points[:split_index]
    holdout_points = points[split_index:]
    train_pairs = _pairs_from_points(train_points)
    holdout_pairs = _pairs_from_points(holdout_points)
    train_ids = {point["example_id"] for point in train_points}
    holdout_ids = {point["example_id"] for point in holdout_points}
    metrics = (
        _evaluate(_fit_pairwise_logistic(train_pairs), holdout_pairs)
        if train_pairs and holdout_pairs
        else {}
    )
    unavailable_reason = None
    if not train_pairs:
        unavailable_reason = "training_partition_lacks_positive_negative_pairs"
    elif not holdout_pairs:
        unavailable_reason = "holdout_partition_lacks_positive_negative_pairs"
    return {
        "split": "latest_time_holdout",
        "example_count": len(points),
        "train_example_count": len(train_points),
        "holdout_example_count": len(holdout_points),
        "train_pair_count": len(train_pairs),
        "holdout_pair_count": len(holdout_pairs),
        "overlap_count": len(train_ids & holdout_ids),
        "train_through": train_points[-1]["created_at"].isoformat()
        if train_points
        else None,
        "holdout_from": holdout_points[0]["created_at"].isoformat()
        if holdout_points
        else None,
        "invalid_scope_count": len(invalid_scope_example_ids),
        "metrics": metrics,
        "unavailable_reason": unavailable_reason,
    }


def _normalize_features(value: dict[str, Any]) -> dict[str, float]:
    return {name: clamp01(value.get(name)) for name in FEATURE_SCHEMA}


def _pairs_from_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positives = [point for point in points if point["label"] > 0]
    negatives = [point for point in points if point["label"] < 0]
    pairs = [
        {
            "key": f"{positive['example_id']}:{negative['example_id']}",
            "positive": positive,
            "negative": negative,
        }
        for positive in positives
        for negative in negatives
        if positive["memory_id"] != negative["memory_id"]
    ]
    return sorted(pairs, key=lambda pair: pair["key"])


def _aware_timestamp(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=None)
    return value.replace(tzinfo=None) if value.tzinfo else value


def _split_pairs(pairs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train = []
    evaluation = []
    for pair in pairs:
        digest = int(hashlib.sha256(pair["key"].encode("utf-8")).hexdigest()[:8], 16)
        (evaluation if digest % 5 == 0 else train).append(pair)
    if not evaluation:
        evaluation.append(train.pop())
    if not train:
        train.append(evaluation[0])
    return train, evaluation


def _fit_pairwise_logistic(pairs: list[dict[str, Any]]) -> dict[str, float]:
    weights = {name: 0.0 for name in FEATURE_SCHEMA}
    learning_rate = 0.12
    l2 = 0.01
    for _ in range(120):
        for pair in pairs:
            delta = {
                name: pair["positive"]["features"][name] - pair["negative"]["features"][name]
                for name in FEATURE_SCHEMA
            }
            probability = _sigmoid(sum(weights[name] * delta[name] for name in FEATURE_SCHEMA))
            for name in FEATURE_SCHEMA:
                gradient = (1.0 - probability) * delta[name] - (l2 * weights[name])
                weights[name] += learning_rate * gradient
    return {name: round(max(-4.0, min(4.0, value)), 6) for name, value in weights.items()}


def _evaluate(weights: dict[str, float], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    correct = 0
    point_map: dict[str, dict[str, Any]] = {}
    correction_positive_ids = set()
    outdated_pairs = 0
    outdated_suppressed = 0
    conflict_pairs = 0
    conflict_suppressed = 0
    for pair in pairs:
        positive_score = _score(weights, pair["positive"]["features"])
        negative_score = _score(weights, pair["negative"]["features"])
        correct += int(positive_score > negative_score)
        if pair["negative"].get("outdated_flag"):
            outdated_pairs += 1
            outdated_suppressed += int(positive_score > negative_score)
        if pair["negative"].get("conflict_flag"):
            conflict_pairs += 1
            conflict_suppressed += int(positive_score > negative_score)
        for point, score in (
            (pair["positive"], positive_score),
            (pair["negative"], negative_score),
        ):
            point_map[point["example_id"]] = {**point, "score": score}
        if pair["positive"]["memory_type"] == "correction":
            correction_positive_ids.add(pair["positive"]["example_id"])

    ranked = sorted(
        point_map.values(),
        key=lambda point: (-point["score"], point["example_id"]),
    )
    relevance = [1.0 if point["label"] > 0 else 0.0 for point in ranked[:8]]
    ideal = sorted(relevance, reverse=True)
    ndcg = _dcg(relevance) / _dcg(ideal) if _dcg(ideal) else 0.0
    first_positive = next(
        (index for index, point in enumerate(ranked, start=1) if point["label"] > 0),
        None,
    )
    top_eight_ids = {point["example_id"] for point in ranked[:8]}
    correction_recall = (
        len(correction_positive_ids & top_eight_ids) / len(correction_positive_ids)
        if correction_positive_ids
        else None
    )
    return {
        "ndcg_at_8": round(ndcg, 6),
        "mrr": round(1.0 / first_positive, 6) if first_positive else 0.0,
        "pairwise_accuracy": round(correct / len(pairs), 6) if pairs else 0.0,
        "correction_recall": (
            round(correction_recall, 6) if correction_recall is not None else None
        ),
        "outdated_suppression_rate": (
            round(outdated_suppressed / outdated_pairs, 6)
            if outdated_pairs
            else None
        ),
        "conflict_suppression_rate": (
            round(conflict_suppressed / conflict_pairs, 6)
            if conflict_pairs
            else None
        ),
        "evaluation_pair_count": len(pairs),
    }


def _persist_model_run(
    session,
    companion_id: uuid.UUID,
    points: list[dict[str, Any]],
    *,
    weights: dict[str, float],
    model_status: str,
    training_summary: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    user_id = next(
        (
            example.user_id
            for example in session.execute(
                select(RerankerTrainingExample)
                .where(RerankerTrainingExample.companion_id == companion_id)
                .order_by(RerankerTrainingExample.created_at.desc())
                .limit(1)
            ).scalars()
        ),
        None,
    )
    if user_id is None:
        companion = session.get(Companion, companion_id)
        if companion is None:
            raise ValueError("Companion not found")
        user_id = companion.user_id
    fingerprint = hashlib.sha256(
        "|".join(sorted(point["example_id"] for point in points)).encode("utf-8")
    ).hexdigest()[:12]
    row = MemoryRerankerRun(
        user_id=user_id,
        companion_id=companion_id,
        learning_mode=POLICY_MODE,
        candidate_memory_ids=list(
            dict.fromkeys(uuid.UUID(point["memory_id"]) for point in points)
        ),
        selected_memory_ids=[],
        status="completed",
        score_json={
            "run_kind": "model_training",
            "model_status": model_status,
            "model_version": f"{ALGORITHM_VERSION}-{fingerprint}",
            "feature_schema": list(FEATURE_SCHEMA),
            "weights": weights,
        },
        explanation_json={
            "training_summary": training_summary,
            "metrics": metrics,
            "privacy": {
                "companion_scoped": True,
                "raw_content_used": False,
                "redacted_or_blocked_samples_excluded": True,
            },
            "policy_mode": POLICY_MODE,
        },
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row_to_dict(row)


def _persist_shadow_decision(
    companion_id: uuid.UUID,
    scored: list[dict[str, Any]],
    model: dict[str, Any] | None,
    fallback_reason: str | None,
    *,
    top_k: int,
    context: dict[str, Any],
) -> str | None:
    if not scored:
        return None
    with get_session() as session:
        memories = list(
            session.execute(
                select(Memory).where(
                    Memory.id.in_([uuid.UUID(item["memory_id"]) for item in scored]),
                    Memory.companion_id == companion_id,
                )
            ).scalars()
        )
        if not memories:
            return None
        learned = sorted(scored, key=lambda item: item["learned_rank"])
        row = MemoryRerankerRun(
            user_id=memories[0].user_id,
            companion_id=companion_id,
            conversation_id=_optional_uuid(context.get("conversation_id")),
            trace_run_id=_optional_uuid(context.get("trace_run_id")),
            learning_mode=POLICY_MODE,
            candidate_memory_ids=[uuid.UUID(item["memory_id"]) for item in scored],
            selected_memory_ids=[
                uuid.UUID(item["memory_id"]) for item in learned[:top_k]
            ],
            status="completed",
            score_json={
                "run_kind": "shadow_decision",
                "model_version": (model or {}).get("score_json", {}).get("model_version"),
                "rank_comparison": scored,
            },
            explanation_json={
                "policy_mode": POLICY_MODE,
                "user_visible_policy": "heuristic",
                "fallback_reason": fallback_reason,
                "boundary_filter_applied_before_learning": True,
            },
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return str(row.id)


def _score(weights: dict[str, float], features: dict[str, float]) -> float:
    return _sigmoid(sum(weights[name] * features[name] for name in FEATURE_SCHEMA))


def _sigmoid(value: float) -> float:
    value = max(-30.0, min(30.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def _dcg(relevance: list[float]) -> float:
    return sum(
        value / math.log2(index + 2.0)
        for index, value in enumerate(relevance)
    )


def _optional_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
