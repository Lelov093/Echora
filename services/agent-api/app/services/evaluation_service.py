"""Agent execution evaluation service and Core Algorithm Completion gate."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import (
    BadCaseInboxItem,
    EvaluationCase,
    EvaluationDataset,
    EvaluationMetric,
    EvaluationResult,
    EvaluationRun,
)
from app.memory.learned_reranker import POLICY_MODE as MEMORY_RERANKER_POLICY_MODE
from app.presence.contextual_bandit import POLICY_MODE as PRESENCE_BANDIT_POLICY_MODE
from app.services import regression_service
from app.services.persistence_helpers import create_row, default_ids, get_session, list_rows, row_to_dict


CORE_ALGORITHM_DATASET_NAME = "Core Algorithm Completion R14"
_CORE_EVALUATION_CASE_TYPES = {
    "correction_memory_force_recall": "memory_retrieval",
    "wrong_memory_suppressed": "memory_write",
    "sensitive_memory_not_prompt": "memory_retrieval",
    "cross_companion_private_memory_isolated": "memory_retrieval",
    "shared_memory_review_required": "memory_write",
    "persona_growth_conflict_blocked": "growth_consistency",
    "consecutive_dismissal_prefers_silence": "presence",
    "presence_safety_gates": "presence",
    "learned_policy_heuristic_fallback": "presence",
    "memory_graph_boundary": "memory_retrieval",
    "realtime_memory_review_gate": "memory_write",
    "channel_safe_summary_handoff": "evidence_sufficiency",
}
CORE_ALGORITHM_METRICS: tuple[dict[str, Any], ...] = (
    {"name": "Memory Candidate Precision", "domain": "memory", "direction": "higher", "cases": ("correction_memory_force_recall", "shared_memory_review_required")},
    {"name": "Memory Recall Accuracy / Recall@8", "domain": "memory", "direction": "higher", "cases": ("correction_memory_force_recall",)},
    {"name": "False Memory Rate", "domain": "memory", "direction": "lower", "cases": ("wrong_memory_suppressed", "sensitive_memory_not_prompt")},
    {"name": "Correction Retention", "domain": "memory", "direction": "higher", "cases": ("correction_memory_force_recall",)},
    {"name": "Decay Appropriateness", "domain": "memory", "direction": "higher", "cases": ("wrong_memory_suppressed",)},
    {"name": "Important Memory Retention", "domain": "memory", "direction": "higher", "cases": ("correction_memory_force_recall",)},
    {"name": "Outdated Suppression", "domain": "memory", "direction": "higher", "cases": ("wrong_memory_suppressed",)},
    {"name": "Cross-Companion Leakage Rate", "domain": "memory", "direction": "lower", "cases": ("cross_companion_private_memory_isolated", "memory_graph_boundary")},
    {"name": "Growth Candidate Precision", "domain": "growth", "direction": "higher", "cases": ("persona_growth_conflict_blocked",)},
    {"name": "Growth Evidence Sufficiency", "domain": "growth", "direction": "higher", "cases": ("persona_growth_conflict_blocked",)},
    {"name": "Growth Consistency", "domain": "growth", "direction": "higher", "cases": ("persona_growth_conflict_blocked",)},
    {"name": "Growth Reversion Rate", "domain": "growth", "direction": "lower", "cases": ("persona_growth_conflict_blocked",)},
    {"name": "Profile Drift Rate", "domain": "growth", "direction": "lower", "cases": ("persona_growth_conflict_blocked",)},
    {"name": "Presence Acceptance Rate", "domain": "presence", "direction": "higher", "cases": ("consecutive_dismissal_prefers_silence",)},
    {"name": "Dismissal Rate", "domain": "presence", "direction": "lower", "cases": ("consecutive_dismissal_prefers_silence",)},
    {"name": "Interruption Complaint Rate", "domain": "presence", "direction": "lower", "cases": ("presence_safety_gates",)},
    {"name": "Queue Usefulness", "domain": "presence", "direction": "higher", "cases": ("consecutive_dismissal_prefers_silence",)},
    {"name": "Meaningful Silence Score", "domain": "presence", "direction": "higher", "cases": ("consecutive_dismissal_prefers_silence", "presence_safety_gates")},
    {"name": "Revoke / Hard Stop Compliance", "domain": "presence", "direction": "higher", "cases": ("presence_safety_gates",)},
    {"name": "Strategy Fit", "domain": "companionship", "direction": "higher", "cases": ("learned_policy_heuristic_fallback",)},
    {"name": "Tone Stability", "domain": "companionship", "direction": "higher", "cases": ("learned_policy_heuristic_fallback",)},
    {"name": "Boundary Safety", "domain": "companionship", "direction": "higher", "cases": ("sensitive_memory_not_prompt", "cross_companion_private_memory_isolated", "shared_memory_review_required", "persona_growth_conflict_blocked", "presence_safety_gates", "learned_policy_heuristic_fallback", "memory_graph_boundary", "realtime_memory_review_gate", "channel_safe_summary_handoff")},
    {"name": "Goal Support Value", "domain": "companionship", "direction": "higher", "cases": ("correction_memory_force_recall", "learned_policy_heuristic_fallback")},
    {"name": "Persona Stability", "domain": "companionship", "direction": "higher", "cases": ("persona_growth_conflict_blocked",)},
    {"name": "Companion Feeling", "domain": "companionship", "direction": "higher", "cases": ("consecutive_dismissal_prefers_silence", "channel_safe_summary_handoff")},
    {"name": "Co-Presence Noise Rate", "domain": "companionship", "direction": "lower", "cases": ("realtime_memory_review_gate", "presence_safety_gates")},
)


def list_datasets(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, EvaluationDataset, filters, page, page_size)


def create_dataset(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        data.setdefault("status", "active")
        return create_row(session, EvaluationDataset, data)


def create_case(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        return create_row(session, EvaluationCase, data)


def list_cases(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, EvaluationCase, filters, page, page_size)


def create_run(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        data.pop("total_count", None)
        data.pop("passed_count", None)
        data.pop("failed_count", None)
        data.setdefault("status", "completed")
        return create_row(session, EvaluationRun, data)


def list_runs(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, EvaluationRun, filters, page, page_size)


def create_result(data: dict) -> dict:
    with get_session() as session:
        run = session.get(EvaluationRun, uuid.UUID(str(data["evaluation_run_id"])))
        if run:
            data.setdefault("user_id", run.user_id)
            data.setdefault("companion_id", run.companion_id)
        return create_row(session, EvaluationResult, data)


def list_results(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, EvaluationResult, filters, page, page_size)


def result_to_bad_case(result_id: uuid.UUID, data: dict | None = None) -> dict | None:
    with get_session() as session:
        result = session.get(EvaluationResult, result_id)
        if result is None:
            return None
        run = session.get(EvaluationRun, result.evaluation_run_id)
        payload = data or {}
        item = BadCaseInboxItem(
            user_id=run.user_id,
            companion_id=run.companion_id,
            source_type="evaluation_result",
            case_type="evaluation_failed",
            severity=payload.get("severity", "medium"),
            status="open",
            title=payload.get("title") or f"Evaluation failed: {result.id}",
            description=result.judge_reason,
            trace_run_id=result.trace_run_id,
            replay_id=result.replay_id,
            evidence_summary=f"evaluation_result:{result.id}",
        )
        session.add(item)
        session.flush()
        result.created_bad_case_id = item.id
        session.commit()
        session.refresh(item)
        return row_to_dict(item)


def core_algorithm_catalog() -> dict[str, Any]:
    return {
        "suite": regression_service.CORE_ALGORITHM_SUITE,
        "suite_version": regression_service.CORE_ALGORITHM_SUITE_VERSION,
        "metric_count": len(CORE_ALGORITHM_METRICS),
        "metrics": [dict(metric) for metric in CORE_ALGORITHM_METRICS],
        "regression": regression_service.core_algorithm_suite_manifest(),
        "policy_modes": {
            "memory_reranker": MEMORY_RERANKER_POLICY_MODE,
            "contextual_presence_bandit": PRESENCE_BANDIT_POLICY_MODE,
            "active_allowed_in_this_phase": False,
        },
    }


def ensure_core_algorithm_dataset(
    *,
    user_id: uuid.UUID | None = None,
    companion_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Create a safe synthetic evaluation dataset aligned to the fixed suite."""
    with get_session() as session:
        default_user_id, default_companion_id = default_ids(session)
        user_id = user_id or default_user_id
        companion_id = companion_id or default_companion_id
        datasets = list(
            session.execute(
                select(EvaluationDataset).where(
                    EvaluationDataset.companion_id == companion_id,
                    EvaluationDataset.deleted_at.is_(None),
                )
            ).scalars()
        )
        dataset = next(
            (
                row for row in datasets
                if (row.metadata_ or {}).get("suite")
                == regression_service.CORE_ALGORITHM_SUITE
            ),
            None,
        )
        created_dataset = False
        if dataset is None:
            dataset = EvaluationDataset(
                user_id=user_id,
                companion_id=companion_id,
                name=CORE_ALGORITHM_DATASET_NAME,
                description="Synthetic, privacy-safe deterministic core behavior cases.",
                dataset_type="deterministic_regression",
                status="active",
                metadata_={
                    "suite": regression_service.CORE_ALGORITHM_SUITE,
                    "suite_version": regression_service.CORE_ALGORITHM_SUITE_VERSION,
                    "contains_raw_user_data": False,
                },
            )
            session.add(dataset)
            session.flush()
            created_dataset = True

        existing_cases = list(
            session.execute(
                select(EvaluationCase).where(
                    EvaluationCase.dataset_id == dataset.id,
                    EvaluationCase.deleted_at.is_(None),
                )
            ).scalars()
        )
        existing = {
            str((row.metadata_ or {}).get("case_key")): row
            for row in existing_cases
        }
        created_cases = 0
        cases = []
        for definition in regression_service.CORE_ALGORITHM_REGRESSION_CASES:
            case = existing.get(definition["key"])
            if case is None:
                case = EvaluationCase(
                    dataset_id=dataset.id,
                    user_id=user_id,
                    companion_id=companion_id,
                    case_type=_CORE_EVALUATION_CASE_TYPES[definition["key"]],
                    title=definition["title"],
                    input_json={
                        "synthetic": True,
                        "contains_raw_user_data": False,
                        "case_key": definition["key"],
                    },
                    expected_behavior=definition["expected_behavior"],
                    expected_json={
                        "passed": True,
                        "p0_safety_case": definition["p0"],
                    },
                    evidence_refs=[],
                    status="active",
                    metadata_={
                        "suite": regression_service.CORE_ALGORITHM_SUITE,
                        "suite_version": regression_service.CORE_ALGORITHM_SUITE_VERSION,
                        "case_key": definition["key"],
                        "domain": definition["domain"],
                    },
                )
                session.add(case)
                session.flush()
                created_cases += 1
            cases.append(case)
        session.commit()
        session.refresh(dataset)
        return {
            "dataset": row_to_dict(dataset),
            "created_dataset": created_dataset,
            "created_case_count": created_cases,
            "case_count": len(cases),
            "items": [row_to_dict(case) for case in cases],
        }


def record_core_algorithm_evaluation(
    observations: list[dict[str, Any]],
    *,
    user_id: uuid.UUID | None = None,
    companion_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Persist actual case outcomes, metric proxies, and a closed activation gate."""
    dataset_result = ensure_core_algorithm_dataset(
        user_id=user_id,
        companion_id=companion_id,
    )
    regression_run = regression_service.record_core_algorithm_regression_run(
        observations,
        user_id=user_id,
        companion_id=companion_id,
    )
    regression_summary = regression_run["result_summary_json"]
    results_by_key = {
        item["case_key"]: item
        for item in regression_summary["results"]
    }
    case_rows = {
        str((item.get("metadata") or {}).get("case_key")): item
        for item in dataset_result["items"]
    }
    timestamp = datetime.now(timezone.utc)
    policy_modes = {
        "memory_reranker": MEMORY_RERANKER_POLICY_MODE,
        "contextual_presence_bandit": PRESENCE_BANDIT_POLICY_MODE,
    }
    gate_checks = {
        "explicit_user_approval": False,
        "separate_activation_task_approved": False,
        "independent_evaluation_dataset_passed": regression_summary["status"] == "passed",
        "heuristic_baseline_comparison_passed": regression_summary[
            "heuristic_baseline_comparison_passed"
        ],
        "p0_privacy_boundary_regression_zero": regression_summary[
            "p0_failure_count"
        ] == 0,
        "shadow_modes_enforced": all(
            mode == "shadow" for mode in policy_modes.values()
        ),
        "one_click_shadow_or_disabled_rollback": results_by_key[
            "learned_policy_heuristic_fallback"
        ]["passed"],
        "rollback_drill_passed": results_by_key[
            "learned_policy_heuristic_fallback"
        ]["passed"],
    }
    activation_gate = {
        "active_allowed": False,
        "status": "blocked_pending_separate_approval",
        "checks": gate_checks,
        "policy_modes": policy_modes,
        "reason": (
            "Memory selection and presence timing policies remain shadow. Assistive or active mode requires a "
            "separate approved task even when deterministic evaluation passes."
        ),
    }
    aggregate_score = (
        regression_summary["passed_count"] / regression_summary["total_count"]
        if regression_summary["total_count"]
        else 0.0
    )
    with get_session() as session:
        default_user_id, default_companion_id = default_ids(session)
        user_id = user_id or default_user_id
        companion_id = companion_id or default_companion_id
        run = EvaluationRun(
            dataset_id=uuid.UUID(dataset_result["dataset"]["id"]),
            user_id=user_id,
            companion_id=companion_id,
            status="completed" if regression_summary["status"] == "passed" else "failed",
            judge_type="deterministic_behavior",
            aggregate_score=aggregate_score,
            result_summary_json={
                "suite": regression_service.CORE_ALGORITHM_SUITE,
                "suite_version": regression_service.CORE_ALGORITHM_SUITE_VERSION,
                "regression_run_id": regression_run["id"],
                "regression_summary": regression_summary,
                "activation_gate": activation_gate,
                "metric_semantics": (
                    "Deterministic core regression proxies; not production quality estimates."
                ),
            },
            started_at=timestamp,
            completed_at=timestamp,
            metadata_={
                "suite": regression_service.CORE_ALGORITHM_SUITE,
                "suite_version": regression_service.CORE_ALGORITHM_SUITE_VERSION,
            },
        )
        session.add(run)
        session.flush()
        for key, result in results_by_key.items():
            session.add(
                EvaluationResult(
                    evaluation_run_id=run.id,
                    evaluation_case_id=uuid.UUID(case_rows[key]["id"]),
                    user_id=user_id,
                    companion_id=companion_id,
                    status=result["status"],
                    score=1.0 if result["passed"] else 0.0,
                    judge_reason=result["reason"],
                    output_json={
                        "case_key": key,
                        "evidence": result["evidence"],
                        "baseline_checked": result["baseline_checked"],
                        "skipped": result["skipped"],
                    },
                    expected_json={"passed": True},
                    metadata_={
                        "suite": regression_service.CORE_ALGORITHM_SUITE,
                        "p0": result["p0"],
                    },
                )
            )
        metric_results = []
        for definition in CORE_ALGORITHM_METRICS:
            case_results = [
                results_by_key[key]
                for key in definition["cases"]
            ]
            pass_rate = (
                sum(item["passed"] for item in case_results) / len(case_results)
            )
            value = 1.0 - pass_rate if definition["direction"] == "lower" else pass_rate
            metric = EvaluationMetric(
                evaluation_run_id=run.id,
                metric_name=definition["name"],
                metric_value=value,
                metric_json={
                    "domain": definition["domain"],
                    "direction": definition["direction"],
                    "case_keys": list(definition["cases"]),
                    "passed_cases": sum(item["passed"] for item in case_results),
                    "total_cases": len(case_results),
                    "measurement_kind": "deterministic_regression_proxy",
                },
            )
            session.add(metric)
            metric_results.append(metric)
        session.commit()
        session.refresh(run)
        return {
            "run": row_to_dict(run),
            "regression_run": regression_run,
            "metric_count": len(metric_results),
            "activation_gate": activation_gate,
        }


def latest_core_algorithm_activation_gate() -> dict[str, Any]:
    with get_session() as session:
        rows = list(
            session.execute(
                select(EvaluationRun)
                .where(EvaluationRun.deleted_at.is_(None))
                .order_by(EvaluationRun.created_at.desc())
                .limit(100)
            ).scalars()
        )
        run = next(
            (
                row for row in rows
                if (row.metadata_ or {}).get("suite")
                == regression_service.CORE_ALGORITHM_SUITE
            ),
            None,
        )
        if run is None:
            return {
                "active_allowed": False,
                "status": "not_evaluated",
                "reason": "No Core Algorithm Completion evaluation run exists.",
                "policy_modes": {
                    "memory_reranker": MEMORY_RERANKER_POLICY_MODE,
                    "contextual_presence_bandit": PRESENCE_BANDIT_POLICY_MODE,
                },
            }
        summary = run.result_summary_json or {}
        return {
            "evaluation_run_id": str(run.id),
            "aggregate_score": run.aggregate_score,
            **(summary.get("activation_gate") or {}),
        }
