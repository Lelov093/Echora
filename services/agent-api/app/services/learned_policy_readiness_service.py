"""learned-policy readiness offline readiness evaluation for shadow-only learned policies."""

from __future__ import annotations

import math
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import (
    Companion,
    EvaluationMetric,
    EvaluationRun,
    Memory,
    MemoryRerankerRun,
    PresencePolicyFeedbackSample,
    PresencePolicyRun,
    RerankerTrainingExample,
)
from app.memory.learned_reranker import (
    FEATURE_SCHEMA,
    POLICY_MODE as MEMORY_POLICY_MODE,
    evaluate_temporal_holdout,
)
from app.presence.contextual_bandit import (
    POLICY_MODE as PRESENCE_POLICY_MODE,
    SAFE_ACTIONS,
)
from app.services.persistence_helpers import get_session, row_to_dict


SUITE = "learned_policy_readiness_wb3_a"
CONTRACT_VERSION = "conversation-learned-policy-readiness.v1"
DELIVERY_ACTIONS = frozenset({"hub", "queue"})
IMMEDIATE_SURFACE_ACTIONS = frozenset({"hub"})
SILENCE_ACTIONS = frozenset({"no_show", "silence", "defer"})
RAW_PAYLOAD_KEYS = frozenset(
    {
        "content",
        "raw_content",
        "message",
        "messages",
        "prompt",
        "reasoning_content",
        "summary",
        "text",
    }
)

# These thresholds are intentionally fixed in code before any policy decision.
# They may only be revised through a separately reviewed contract version.
THRESHOLDS: dict[str, Any] = {
    "memory": {
        "minimum_examples": 80,
        "minimum_positive_examples": 20,
        "minimum_negative_examples": 20,
        "minimum_holdout_examples": 16,
        "minimum_holdout_pairs": 20,
        "minimum_observation_span_days": 30,
        "minimum_positive_corrections": 10,
        "minimum_outdated_negative_examples": 10,
        "minimum_conflict_negative_examples": 5,
        "minimum_ndcg_at_8": 0.80,
        "minimum_mrr": 0.75,
        "minimum_pairwise_accuracy": 0.70,
        "minimum_correction_recall": 0.80,
        "minimum_outdated_suppression_rate": 0.80,
        "minimum_conflict_suppression_rate": 0.80,
        "maximum_scope_violations": 0,
        "maximum_raw_payload_violations": 0,
    },
    "presence": {
        "minimum_samples": 100,
        "minimum_action_types": 3,
        "minimum_silence_action_samples": 15,
        "minimum_delivery_action_samples": 15,
        "minimum_opportunity_types": 3,
        "minimum_counterfactual_samples": 30,
        "minimum_safety_veto_samples": 10,
        "minimum_observation_span_days": 30,
        "minimum_counterfactual_lift": -0.02,
        "maximum_safety_veto_violations": 0,
        "maximum_high_interruption_immediate_surface_rate": 0.02,
        "maximum_random_user_exploration": 0,
        "maximum_raw_payload_violations": 0,
    },
}


def run_readiness_evaluation(companion_id: uuid.UUID) -> dict[str, Any]:
    """Evaluate and persist learned-policy readiness evidence without changing either policy."""
    with get_session() as session:
        companion = session.get(Companion, companion_id)
        if companion is None or companion.deleted_at is not None:
            raise ValueError("Companion not found")

        examples = list(
            session.execute(
                select(RerankerTrainingExample)
                .where(
                    RerankerTrainingExample.companion_id == companion_id,
                    RerankerTrainingExample.deleted_at.is_(None),
                )
                .order_by(
                    RerankerTrainingExample.created_at,
                    RerankerTrainingExample.id,
                )
            ).scalars()
        )
        memory_ids = {
            example.memory_id for example in examples if example.memory_id is not None
        }
        memories = (
            list(
                session.execute(
                    select(Memory).where(Memory.id.in_(memory_ids))
                ).scalars()
            )
            if memory_ids
            else []
        )
        presence_samples = list(
            session.execute(
                select(PresencePolicyFeedbackSample)
                .where(
                    PresencePolicyFeedbackSample.companion_id == companion_id,
                    PresencePolicyFeedbackSample.deleted_at.is_(None),
                )
                .order_by(
                    PresencePolicyFeedbackSample.created_at,
                    PresencePolicyFeedbackSample.id,
                )
            ).scalars()
        )
        recent_memory_runs = list(
            session.execute(
                select(MemoryRerankerRun)
                .where(
                    MemoryRerankerRun.companion_id == companion_id,
                    MemoryRerankerRun.deleted_at.is_(None),
                )
                .order_by(MemoryRerankerRun.created_at.desc())
                .limit(100)
            ).scalars()
        )
        latest_memory_run = next(
            (
                run
                for run in recent_memory_runs
                if (run.score_json or {}).get("run_kind") == "model_training"
            ),
            None,
        )
        latest_presence_run = session.execute(
            select(PresencePolicyRun)
            .where(
                PresencePolicyRun.companion_id == companion_id,
                PresencePolicyRun.deleted_at.is_(None),
            )
            .order_by(PresencePolicyRun.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        memory_report = _evaluate_memory(
            examples,
            {memory.id: memory for memory in memories},
            latest_memory_run,
        )
        presence_report = _evaluate_presence(presence_samples, latest_presence_run)
        gate = _build_gate(memory_report, presence_report)
        now = datetime.now(timezone.utc)
        aggregate_score = _aggregate_score(memory_report, presence_report)
        run = EvaluationRun(
            user_id=companion.user_id,
            companion_id=companion_id,
            status="completed",
            judge_type="deterministic_behavior",
            source_domain="strategy",
            source_entity_type="companion",
            source_entity_id=companion_id,
            source_entity_revision=1,
            trigger_type="manual_readiness_evaluation",
            aggregate_score=aggregate_score,
            result_summary_json={
                "suite": SUITE,
                "contract_version": CONTRACT_VERSION,
                "thresholds": THRESHOLDS,
                "memory": memory_report,
                "presence": presence_report,
                "activation_gate": gate,
                "metric_semantics": (
                    "Companion-local offline readiness evidence. It is not an "
                    "authorization to change a user-visible policy."
                ),
            },
            started_at=now,
            completed_at=now,
            metadata_={
                "suite": SUITE,
                "contract_version": CONTRACT_VERSION,
                "policy_modes": {
                    "memory_reranker": MEMORY_POLICY_MODE,
                    "contextual_presence_bandit": PRESENCE_POLICY_MODE,
                },
            },
        )
        session.add(run)
        session.flush()
        for name, value, domain, details in _metric_rows(
            memory_report, presence_report
        ):
            session.add(
                EvaluationMetric(
                    evaluation_run_id=run.id,
                    metric_name=name,
                    metric_value=_clamp01(value),
                    metric_json={
                        "domain": domain,
                        "contract_version": CONTRACT_VERSION,
                        **details,
                    },
                )
            )
        session.commit()
        session.refresh(run)
        return {
            "run": row_to_dict(run),
            "memory": memory_report,
            "presence": presence_report,
            "activation_gate": gate,
        }


def latest_readiness(companion_id: uuid.UUID) -> dict[str, Any]:
    with get_session() as session:
        rows = list(
            session.execute(
                select(EvaluationRun)
                .where(
                    EvaluationRun.companion_id == companion_id,
                    EvaluationRun.deleted_at.is_(None),
                )
                .order_by(EvaluationRun.created_at.desc())
                .limit(100)
            ).scalars()
        )
        run = next(
            (
                row
                for row in rows
                if (row.metadata_ or {}).get("suite") == SUITE
            ),
            None,
        )
        if run is None:
            return {
                "contract_version": CONTRACT_VERSION,
                "status": "not_evaluated",
                "active_allowed": False,
                "assistive_review_allowed": False,
                "policy_modes": _policy_modes(),
                "reason": "No learned-policy readiness readiness evaluation exists for this Companion.",
            }
        summary = run.result_summary_json or {}
        return {
            "evaluation_run_id": str(run.id),
            "evaluated_at": run.completed_at.isoformat()
            if run.completed_at
            else None,
            "aggregate_score": run.aggregate_score,
            "contract_version": summary.get("contract_version"),
            "thresholds": summary.get("thresholds"),
            "memory": summary.get("memory"),
            "presence": summary.get("presence"),
            **(summary.get("activation_gate") or {}),
        }


def _evaluate_memory(
    examples: list[RerankerTrainingExample],
    memories_by_id: dict[uuid.UUID, Memory],
    latest_run: MemoryRerankerRun | None,
) -> dict[str, Any]:
    temporal = evaluate_temporal_holdout(examples, memories_by_id)
    positive_count = sum(float(example.label) > 0 for example in examples)
    negative_count = sum(float(example.label) < 0 for example in examples)
    correction_count = sum(
        1
        for example in examples
        if example.memory_id in memories_by_id
        and memories_by_id[example.memory_id].type == "correction"
        and float(example.label) > 0
    )
    outdated_negative_count = sum(
        1
        for example in examples
        if float(example.label) < 0
        and example.memory_id in memories_by_id
        and (
            getattr(memories_by_id[example.memory_id], "outdated_count", 0)
            or getattr(memories_by_id[example.memory_id], "wrong_count", 0)
            or _float(
                ((example.feature_json or {}).get("reranker_features") or {}).get(
                    "outdated_penalty"
                ),
                0.0,
            )
            > 0
        )
    )
    conflict_negative_count = sum(
        1
        for example in examples
        if float(example.label) < 0
        and example.memory_id in memories_by_id
        and (
            bool((example.feature_json or {}).get("conflict"))
            or bool((example.feature_json or {}).get("conflict_signal"))
            or bool((example.feature_json or {}).get("superseded"))
            or memories_by_id[example.memory_id].type == "conflict"
        )
    )
    raw_payload_violations = sum(
        _contains_raw_payload(example.feature_json or {}) for example in examples
    )
    span_days = _span_days(examples)
    metrics = temporal.get("metrics") or {}
    data_checks = [
        _minimum_check("examples", len(examples), THRESHOLDS["memory"]["minimum_examples"]),
        _minimum_check(
            "positive_examples",
            positive_count,
            THRESHOLDS["memory"]["minimum_positive_examples"],
        ),
        _minimum_check(
            "negative_examples",
            negative_count,
            THRESHOLDS["memory"]["minimum_negative_examples"],
        ),
        _minimum_check(
            "holdout_examples",
            temporal["holdout_example_count"],
            THRESHOLDS["memory"]["minimum_holdout_examples"],
        ),
        _minimum_check(
            "holdout_pairs",
            temporal["holdout_pair_count"],
            THRESHOLDS["memory"]["minimum_holdout_pairs"],
        ),
        _minimum_check(
            "observation_span_days",
            span_days,
            THRESHOLDS["memory"]["minimum_observation_span_days"],
        ),
        _minimum_check(
            "positive_corrections",
            correction_count,
            THRESHOLDS["memory"]["minimum_positive_corrections"],
        ),
        _minimum_check(
            "outdated_negative_examples",
            outdated_negative_count,
            THRESHOLDS["memory"]["minimum_outdated_negative_examples"],
        ),
        _minimum_check(
            "conflict_negative_examples",
            conflict_negative_count,
            THRESHOLDS["memory"]["minimum_conflict_negative_examples"],
        ),
    ]
    safety_checks = [
        _maximum_check(
            "scope_violations",
            temporal["invalid_scope_count"],
            THRESHOLDS["memory"]["maximum_scope_violations"],
            safety=True,
        ),
        _maximum_check(
            "raw_payload_violations",
            raw_payload_violations,
            THRESHOLDS["memory"]["maximum_raw_payload_violations"],
            safety=True,
        ),
        _exact_check("temporal_split_overlap", temporal["overlap_count"], 0, safety=True),
        _exact_check("runtime_policy_mode", MEMORY_POLICY_MODE, "shadow", safety=True),
    ]
    quality_checks = [
        _metric_check(
            "ndcg_at_8",
            metrics.get("ndcg_at_8"),
            THRESHOLDS["memory"]["minimum_ndcg_at_8"],
        ),
        _metric_check(
            "mrr",
            metrics.get("mrr"),
            THRESHOLDS["memory"]["minimum_mrr"],
        ),
        _metric_check(
            "pairwise_accuracy",
            metrics.get("pairwise_accuracy"),
            THRESHOLDS["memory"]["minimum_pairwise_accuracy"],
        ),
        _metric_check(
            "correction_recall",
            metrics.get("correction_recall"),
            THRESHOLDS["memory"]["minimum_correction_recall"],
        ),
        _metric_check(
            "outdated_suppression_rate",
            metrics.get("outdated_suppression_rate"),
            THRESHOLDS["memory"]["minimum_outdated_suppression_rate"],
        ),
        _metric_check(
            "conflict_suppression_rate",
            metrics.get("conflict_suppression_rate"),
            THRESHOLDS["memory"]["minimum_conflict_suppression_rate"],
        ),
    ]
    latest_mode = latest_run.learning_mode if latest_run else None
    latest_schema = (
        tuple((latest_run.score_json or {}).get("feature_schema") or ())
        if latest_run
        else ()
    )
    fallback_checks = [
        _exact_check(
            "latest_persisted_policy_mode",
            latest_mode,
            "shadow",
            safety=True,
            unavailable_is_insufficient=True,
        ),
        _exact_check(
            "feature_schema_compatible",
            latest_schema,
            FEATURE_SCHEMA,
            safety=True,
            unavailable_is_insufficient=True,
        ),
        _exact_check("rollback_target", MEMORY_POLICY_MODE, "shadow", safety=True),
    ]
    return {
        "status": _domain_status(
            data_checks, safety_checks + fallback_checks, quality_checks
        ),
        "sample_counts": {
            "examples": len(examples),
            "positive": positive_count,
            "negative": negative_count,
            "positive_corrections": correction_count,
            "outdated_negative": outdated_negative_count,
            "conflict_negative": conflict_negative_count,
            "distinct_memories": len(
                {example.memory_id for example in examples if example.memory_id}
            ),
        },
        "observation_span_days": span_days,
        "temporal_holdout": temporal,
        "data_checks": data_checks,
        "safety_checks": safety_checks,
        "quality_checks": quality_checks,
        "fallback_checks": fallback_checks,
        "raw_payload_violations": raw_payload_violations,
    }


def _evaluate_presence(
    samples: list[PresencePolicyFeedbackSample],
    latest_run: PresencePolicyRun | None,
) -> dict[str, Any]:
    action_counts = Counter(str(sample.action_taken) for sample in samples)
    opportunity_types = Counter(
        str((sample.feature_json or {}).get("opportunity_type") or "unknown")
        for sample in samples
    )
    silence_count = sum(action_counts[action] for action in SILENCE_ACTIONS)
    delivery_count = sum(action_counts[action] for action in DELIVERY_ACTIONS)
    veto_samples = 0
    veto_violations = 0
    high_interruption_immediate_surfaces = 0
    immediate_surface_count = 0
    random_exploration = 0
    raw_payload_violations = 0
    counterfactual_samples = 0
    counterfactual_weighted_reward = 0.0
    counterfactual_weight_sum = 0.0
    for sample in samples:
        features = sample.feature_json or {}
        raw_payload_violations += int(_contains_raw_payload(features))
        veto = _presence_veto(features)
        action = str(sample.action_taken)
        if veto:
            veto_samples += 1
            veto_violations += int(action in DELIVERY_ACTIONS)
        interruption = _float(features.get("interruption_risk"), 0.0)
        immediate_surface_count += int(action in IMMEDIATE_SURFACE_ACTIONS)
        high_interruption_immediate_surfaces += int(
            action in IMMEDIATE_SURFACE_ACTIONS and interruption >= 0.70
        )
        random_exploration += int(
            bool(features.get("random_user_exploration"))
        )
        shadow_action = features.get("shadow_action")
        propensity = _float(
            features.get("behavior_propensity", features.get("propensity")),
            0.0,
        )
        if shadow_action == action and 0.0 < propensity <= 1.0:
            counterfactual_samples += 1
            weight = min(10.0, 1.0 / propensity)
            counterfactual_weighted_reward += float(sample.reward) * weight
            counterfactual_weight_sum += weight
    high_interruption_rate = (
        high_interruption_immediate_surfaces / immediate_surface_count
        if immediate_surface_count
        else 0.0
    )
    counterfactual_value = (
        counterfactual_weighted_reward / counterfactual_weight_sum
        if counterfactual_weight_sum
        else None
    )
    heuristic_mean_reward = (
        sum(float(sample.reward) for sample in samples) / len(samples)
        if samples
        else None
    )
    counterfactual_lift = (
        counterfactual_value - heuristic_mean_reward
        if counterfactual_value is not None and heuristic_mean_reward is not None
        else None
    )
    span_days = _span_days(samples)
    data_checks = [
        _minimum_check("samples", len(samples), THRESHOLDS["presence"]["minimum_samples"]),
        _minimum_check(
            "action_types",
            len(action_counts),
            THRESHOLDS["presence"]["minimum_action_types"],
        ),
        _minimum_check(
            "silence_action_samples",
            silence_count,
            THRESHOLDS["presence"]["minimum_silence_action_samples"],
        ),
        _minimum_check(
            "delivery_action_samples",
            delivery_count,
            THRESHOLDS["presence"]["minimum_delivery_action_samples"],
        ),
        _minimum_check(
            "opportunity_types",
            len(opportunity_types),
            THRESHOLDS["presence"]["minimum_opportunity_types"],
        ),
        _minimum_check(
            "counterfactual_samples",
            counterfactual_samples,
            THRESHOLDS["presence"]["minimum_counterfactual_samples"],
        ),
        _minimum_check(
            "safety_veto_samples",
            veto_samples,
            THRESHOLDS["presence"]["minimum_safety_veto_samples"],
        ),
        _minimum_check(
            "observation_span_days",
            span_days,
            THRESHOLDS["presence"]["minimum_observation_span_days"],
        ),
    ]
    safety_checks = [
        _maximum_check(
            "safety_veto_violations",
            veto_violations,
            THRESHOLDS["presence"]["maximum_safety_veto_violations"],
            safety=True,
        ),
        _maximum_check(
            "high_interruption_immediate_surface_rate",
            high_interruption_rate,
            THRESHOLDS["presence"][
                "maximum_high_interruption_immediate_surface_rate"
            ],
            safety=True,
        ),
        _maximum_check(
            "random_user_exploration",
            random_exploration,
            THRESHOLDS["presence"]["maximum_random_user_exploration"],
            safety=True,
        ),
        _maximum_check(
            "raw_payload_violations",
            raw_payload_violations,
            THRESHOLDS["presence"]["maximum_raw_payload_violations"],
            safety=True,
        ),
        _exact_check("runtime_policy_mode", PRESENCE_POLICY_MODE, "shadow", safety=True),
        _exact_check("safe_action_space", set(SAFE_ACTIONS), set(SAFE_ACTIONS), safety=True),
        _exact_check("rollback_target", PRESENCE_POLICY_MODE, "shadow", safety=True),
        _exact_check(
            "latest_persisted_policy_mode",
            latest_run.learning_mode if latest_run else None,
            "shadow",
            safety=True,
            unavailable_is_insufficient=True,
        ),
    ]
    quality_checks = [
        _metric_check(
            "counterfactual_lift",
            counterfactual_lift,
            THRESHOLDS["presence"]["minimum_counterfactual_lift"],
        )
    ]
    return {
        "status": _domain_status(data_checks, safety_checks, quality_checks),
        "sample_counts": {
            "samples": len(samples),
            "actions": dict(sorted(action_counts.items())),
            "opportunity_types": dict(sorted(opportunity_types.items())),
            "silence_actions": silence_count,
            "delivery_actions": delivery_count,
            "immediate_surface_actions": immediate_surface_count,
            "counterfactual_eligible": counterfactual_samples,
            "safety_veto": veto_samples,
        },
        "observation_span_days": span_days,
        "counterfactual_value": round(counterfactual_value, 6)
        if counterfactual_value is not None
        else None,
        "heuristic_mean_reward": round(heuristic_mean_reward, 6)
        if heuristic_mean_reward is not None
        else None,
        "counterfactual_lift": round(counterfactual_lift, 6)
        if counterfactual_lift is not None
        else None,
        "high_interruption_immediate_surface_rate": round(
            high_interruption_rate, 6
        ),
        "data_checks": data_checks,
        "safety_checks": safety_checks,
        "quality_checks": quality_checks,
        "raw_payload_violations": raw_payload_violations,
    }


def _build_gate(memory: dict[str, Any], presence: dict[str, Any]) -> dict[str, Any]:
    statuses = {memory["status"], presence["status"]}
    if "failed" in statuses:
        status = "failed"
        reason = "One or more quality or safety checks failed."
    elif "insufficient_data" in statuses:
        status = "insufficient_data"
        reason = "Real Companion-scoped evidence does not meet fixed readiness thresholds."
    else:
        status = "ready_for_assistive_review"
        reason = (
            "Offline readiness passed. A separately authorized, scoped assistive "
            "policy review is still required."
        )
    return {
        "status": status,
        "reason": reason,
        "active_allowed": False,
        "assistive_review_allowed": status
        == "ready_for_assistive_review",
        "separate_user_authorization_required": True,
        "policy_modes": _policy_modes(),
        "rollback_target": {
            "memory_reranker": "shadow",
            "contextual_presence_bandit": "shadow",
        },
        "cross_companion_pooling_allowed": False,
        "synthetic_behavior_counts_as_real_evidence": False,
    }


def _domain_status(
    data_checks: list[dict[str, Any]],
    safety_checks: list[dict[str, Any]],
    quality_checks: list[dict[str, Any]],
) -> str:
    if any(check["status"] == "failed" for check in safety_checks):
        return "failed"
    if any(check["status"] == "insufficient" for check in data_checks + safety_checks):
        return "insufficient_data"
    if any(check["status"] == "unavailable" for check in quality_checks):
        return "insufficient_data"
    if any(check["status"] == "failed" for check in quality_checks):
        return "failed"
    return "passed"


def _minimum_check(name: str, value: float, threshold: float) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "operator": ">=",
        "threshold": threshold,
        "status": "passed" if value >= threshold else "insufficient",
    }


def _maximum_check(
    name: str,
    value: float,
    threshold: float,
    *,
    safety: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "operator": "<=",
        "threshold": threshold,
        "status": "passed"
        if value <= threshold
        else ("failed" if safety else "insufficient"),
    }


def _exact_check(
    name: str,
    value: Any,
    expected: Any,
    *,
    safety: bool,
    unavailable_is_insufficient: bool = False,
) -> dict[str, Any]:
    unavailable = value is None or value == () or value == set()
    if unavailable and unavailable_is_insufficient:
        status = "insufficient"
    else:
        status = "passed" if value == expected else ("failed" if safety else "insufficient")
    return {
        "name": name,
        "value": _json_safe(value),
        "operator": "==",
        "threshold": _json_safe(expected),
        "status": status,
    }


def _metric_check(name: str, value: float | None, threshold: float) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "operator": ">=",
        "threshold": threshold,
        "status": "unavailable"
        if value is None
        else ("passed" if value >= threshold else "failed"),
    }


def _presence_veto(features: dict[str, Any]) -> bool:
    suppression = features.get("suppression") or {}
    return any(
        (
            bool(suppression.get("hard_block")),
            bool(suppression.get("suppress")),
            bool(features.get("hard_stop_active")),
            bool(features.get("revoked")),
            bool(features.get("quiet_hours_active")),
            bool(features.get("focus_mode_active")),
            bool(features.get("meaningful_silence")),
        )
    )


def _contains_raw_payload(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in RAW_PAYLOAD_KEYS:
                return True
            if _contains_raw_payload(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_raw_payload(item) for item in value)
    return False


def _span_days(rows: list[Any]) -> int:
    timestamps = [row.created_at for row in rows if row.created_at is not None]
    if len(timestamps) < 2:
        return 0
    return max(0, math.floor((max(timestamps) - min(timestamps)).total_seconds() / 86400))


def _aggregate_score(memory: dict[str, Any], presence: dict[str, Any]) -> float:
    checks = (
        memory["data_checks"]
        + memory["safety_checks"]
        + memory["fallback_checks"]
        + memory["quality_checks"]
        + presence["data_checks"]
        + presence["safety_checks"]
        + presence["quality_checks"]
    )
    if not checks:
        return 0.0
    return round(sum(check["status"] == "passed" for check in checks) / len(checks), 6)


def _metric_rows(
    memory: dict[str, Any], presence: dict[str, Any]
) -> list[tuple[str, float, str, dict[str, Any]]]:
    memory_metrics = memory["temporal_holdout"].get("metrics") or {}
    return [
        (
            "learned-policy readiness Memory Data Sufficiency",
            min(
                1.0,
                memory["sample_counts"]["examples"]
                / THRESHOLDS["memory"]["minimum_examples"],
            ),
            "memory",
            {"measurement_kind": "real_sample_count_ratio"},
        ),
        (
            "learned-policy readiness Memory NDCG@8",
            memory_metrics.get("ndcg_at_8", 0.0),
            "memory",
            {"measurement_kind": "latest_time_holdout"},
        ),
        (
            "learned-policy readiness Memory MRR",
            memory_metrics.get("mrr", 0.0),
            "memory",
            {"measurement_kind": "latest_time_holdout"},
        ),
        (
            "learned-policy readiness Memory Correction Recall",
            memory_metrics.get("correction_recall") or 0.0,
            "memory",
            {"measurement_kind": "latest_time_holdout"},
        ),
        (
            "learned-policy readiness Memory Outdated Suppression",
            memory_metrics.get("outdated_suppression_rate") or 0.0,
            "memory",
            {"measurement_kind": "latest_time_holdout"},
        ),
        (
            "learned-policy readiness Memory Conflict Suppression",
            memory_metrics.get("conflict_suppression_rate") or 0.0,
            "memory",
            {"measurement_kind": "latest_time_holdout"},
        ),
        (
            "learned-policy readiness Presence Data Sufficiency",
            min(
                1.0,
                presence["sample_counts"]["samples"]
                / THRESHOLDS["presence"]["minimum_samples"],
            ),
            "presence",
            {"measurement_kind": "real_sample_count_ratio"},
        ),
        (
            "learned-policy readiness Presence Safety Compliance",
            1.0
            if all(
                check["status"] == "passed" for check in presence["safety_checks"]
            )
            else 0.0,
            "presence",
            {"measurement_kind": "deterministic_safety_contract"},
        ),
        (
            "learned-policy readiness Presence Counterfactual Lift",
            (
                (presence["counterfactual_lift"] + 1.0) / 2.0
                if presence["counterfactual_lift"] is not None
                else 0.0
            ),
            "presence",
            {
                "measurement_kind": "self_normalized_ips",
                "raw_lift": presence["counterfactual_lift"],
            },
        ),
    ]


def _policy_modes() -> dict[str, str]:
    return {
        "memory_reranker": MEMORY_POLICY_MODE,
        "contextual_presence_bandit": PRESENCE_POLICY_MODE,
    }


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp01(value: Any) -> float:
    return max(0.0, min(1.0, _float(value, 0.0)))


def _json_safe(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, tuple):
        return list(value)
    return value
