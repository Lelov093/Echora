"""Durable runtime quality feedback over existing execution truth.

The worker evaluates identifiers, terminal states, permission/review evidence and
safe summaries only. It never copies prompts, messages, tool payloads or shared
memory content, and it never applies a Companion-domain mutation automatically.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.models import (
    BadCaseInboxItem,
    BadCaseTriageEvent,
    ChannelMemoryCandidate,
    ChannelMemoryReview,
    Companion,
    CrossCompanionMemoryEvent,
    CrossCompanionMemoryReview,
    DiscordChannelDelivery,
    DiscordDmDelivery,
    EvaluationResult,
    EvaluationRun,
    PresenceScheduleOccurrence,
    RegressionCase,
    ToolRun,
    TraceRun,
)
from app.memory.learned_reranker import POLICY_MODE as MEMORY_RERANKER_POLICY_MODE
from app.presence.contextual_bandit import POLICY_MODE as PRESENCE_BANDIT_POLICY_MODE
from app.services import governance_policy_service
from app.services.settings_service import get_session


CONTRACT_VERSION = "quality-feedback.v2"
JUDGE_TYPE = "deterministic_runtime_feedback"
ACTIVE_RUN_STATUSES = {"pending", "running"}
TERMINAL_TRACE_STATUSES = {"completed", "failed"}


@dataclass(frozen=True)
class SourceSpec:
    model: type
    domain: str
    status_attr: str
    terminal_statuses: frozenset[str]
    companion_attr: str = "companion_id"
    revision_attr: str | None = None


SOURCE_SPECS: dict[str, SourceSpec] = {
    "trace_run": SourceSpec(TraceRun, "quality", "status", frozenset(TERMINAL_TRACE_STATUSES)),
    "presence_occurrence": SourceSpec(
        PresenceScheduleOccurrence,
        "presence",
        "status",
        frozenset({"delivered", "suppressed", "failed", "expired", "cancelled"}),
        revision_attr="schedule_revision",
    ),
    "tool_run": SourceSpec(
        ToolRun,
        "tools",
        "status",
        frozenset({"succeeded", "failed", "cancelled", "blocked", "timed_out"}),
    ),
    "discord_dm_delivery": SourceSpec(
        DiscordDmDelivery,
        "channels",
        "delivery_status",
        frozenset({"delivered", "failed", "cancelled", "suppressed"}),
    ),
    "discord_channel_delivery": SourceSpec(
        DiscordChannelDelivery,
        "channels",
        "delivery_status",
        frozenset({"delivered", "failed", "cancelled", "suppressed"}),
    ),
    "channel_memory_candidate": SourceSpec(
        ChannelMemoryCandidate,
        "shared",
        "candidate_status",
        frozenset({"approved", "rejected", "redacted", "committed"}),
    ),
    "cross_companion_memory_event": SourceSpec(
        CrossCompanionMemoryEvent,
        "shared",
        "status",
        frozenset({"approved", "rejected", "recorded"}),
        companion_attr="source_companion_id",
    ),
}


def enqueue_trace_feedback(
    trace_run_id: uuid.UUID,
    *,
    expected_companion_id: uuid.UUID | None = None,
    trigger_type: str = "trace_terminal",
) -> dict[str, Any] | None:
    return enqueue_source_feedback(
        "trace_run",
        trace_run_id,
        expected_companion_id=expected_companion_id,
        trigger_type=trigger_type,
    )


def enqueue_source_feedback(
    source_entity_type: str,
    source_entity_id: uuid.UUID,
    *,
    expected_companion_id: uuid.UUID | None = None,
    trigger_type: str = "terminal_source",
) -> dict[str, Any] | None:
    """Idempotently enqueue one terminal durable source without copying content."""
    spec = SOURCE_SPECS.get(source_entity_type)
    if spec is None:
        raise ValueError("Unsupported quality feedback source")
    with get_session() as session:
        source = session.get(spec.model, source_entity_id)
        if source is None:
            return None
        terminal_status = str(getattr(source, spec.status_attr))
        if terminal_status not in spec.terminal_statuses:
            return None
        companion_id = getattr(source, spec.companion_attr)
        if expected_companion_id is not None and companion_id != expected_companion_id:
            raise ValueError("Quality feedback source does not belong to this Companion")
        revision = int(getattr(source, spec.revision_attr, 0) or 0) if spec.revision_attr else 0
        existing = _find_source_run(
            session,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            source_entity_revision=revision,
        )
        if existing is not None:
            return _run_dict(existing)

        policy = governance_policy_service.get_governance_policy(companion_id)
        if (
            trigger_type != "explicit_trace_review"
            and not governance_policy_service.quality_feedback_is_automatic(policy)
        ):
            return None
        run = EvaluationRun(
            user_id=source.user_id,
            companion_id=companion_id,
            source_trace_run_id=source.id if source_entity_type == "trace_run" else None,
            source_domain=spec.domain,
            source_entity_type=source_entity_type,
            source_entity_id=source.id,
            source_entity_revision=revision,
            feedback_revision=1,
            trigger_type=trigger_type,
            judge_type=JUDGE_TYPE,
            status="pending",
            next_attempt_at=datetime.now(timezone.utc),
            result_summary_json={
                "contract_version": CONTRACT_VERSION,
                "source": {
                    "entity_type": source_entity_type,
                    "entity_id": str(source.id),
                    "entity_revision": revision,
                    "domain": spec.domain,
                    "terminal_status": terminal_status,
                },
                "governance": _policy_snapshot(policy),
                "revision_history": [],
            },
            metadata_={"contract_version": CONTRACT_VERSION},
        )
        session.add(run)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = _find_source_run(
                session,
                source_entity_type=source_entity_type,
                source_entity_id=source_entity_id,
                source_entity_revision=revision,
            )
            if existing is None:
                raise
            return _run_dict(existing)
        session.refresh(run)
        return _run_dict(run)


def discover_recent_terminal_sources(*, limit: int = 50) -> dict[str, int]:
    """Recover missed hooks for each supported durable source in a bounded window."""
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=max(1, settings.QUALITY_FEEDBACK_LOOKBACK_MINUTES)
    )
    counts: dict[str, int] = {}
    per_source_limit = max(1, limit // len(SOURCE_SPECS))
    for source_type, spec in SOURCE_SPECS.items():
        status_column = getattr(spec.model, spec.status_attr)
        with get_session() as session:
            source_ids = session.execute(
                select(spec.model.id)
                .where(
                    status_column.in_(spec.terminal_statuses),
                    spec.model.updated_at >= cutoff,
                    ~select(EvaluationRun.id)
                    .where(
                        EvaluationRun.judge_type == JUDGE_TYPE,
                        EvaluationRun.source_entity_type == source_type,
                        EvaluationRun.source_entity_id == spec.model.id,
                        EvaluationRun.deleted_at.is_(None),
                    )
                    .exists(),
                )
                .order_by(spec.model.updated_at.asc())
                .limit(per_source_limit)
            ).scalars().all()
        created = 0
        for source_id in source_ids:
            if enqueue_source_feedback(
                source_type,
                source_id,
                trigger_type="recent_terminal_reconciliation",
            ):
                created += 1
        counts[source_type] = created
    return counts


def discover_recent_terminal_traces(*, limit: int = 50) -> int:
    """Compatibility wrapper retained for existing callers and contracts."""
    return _discover_one_source("trace_run", limit=limit)


def _discover_one_source(source_type: str, *, limit: int) -> int:
    spec = SOURCE_SPECS[source_type]
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=max(1, settings.QUALITY_FEEDBACK_LOOKBACK_MINUTES)
    )
    status_column = getattr(spec.model, spec.status_attr)
    with get_session() as session:
        source_ids = session.execute(
            select(spec.model.id)
            .where(
                status_column.in_(spec.terminal_statuses),
                spec.model.updated_at >= cutoff,
                ~select(EvaluationRun.id)
                .where(
                    EvaluationRun.judge_type == JUDGE_TYPE,
                    EvaluationRun.source_entity_type == source_type,
                    EvaluationRun.source_entity_id == spec.model.id,
                    EvaluationRun.deleted_at.is_(None),
                )
                .exists(),
            )
            .order_by(spec.model.updated_at.asc())
            .limit(limit)
        ).scalars().all()
    return sum(
        1
        for source_id in source_ids
        if enqueue_source_feedback(
            source_type, source_id, trigger_type="recent_terminal_reconciliation"
        )
    )


def run_scheduler_tick(*, worker_id: str, limit: int = 10) -> dict[str, Any]:
    discovered_by_source = discover_recent_terminal_sources(limit=max(limit * 4, 28))
    claimed = _claim_due_runs(worker_id=worker_id, limit=limit)
    counts: dict[str, Any] = {
        "discovered": sum(discovered_by_source.values()),
        "discovered_by_source": discovered_by_source,
        "claimed": len(claimed),
        "completed": 0,
        "failed": 0,
    }
    for run_id in claimed:
        try:
            _execute_run(run_id, worker_id=worker_id)
            counts["completed"] += 1
        except Exception as exc:  # each durable task fails independently
            _record_worker_failure(run_id, worker_id=worker_id, exc=exc)
            counts["failed"] += 1
    return counts


def retry_feedback_run(
    companion_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    expected_attempt_count: int,
) -> dict[str, Any]:
    """Retry infrastructure failure without changing the semantic revision."""
    with get_session() as session:
        run = session.get(EvaluationRun, run_id, with_for_update=True)
        if run is None or run.companion_id != companion_id or run.judge_type != JUDGE_TYPE:
            raise ValueError("Quality feedback run not found for this Companion")
        if run.attempt_count != expected_attempt_count:
            raise ValueError("Quality feedback attempt changed; reload before retrying")
        if run.status not in {"failed", "cancelled"}:
            raise ValueError("Only failed or cancelled worker runs can be retried")
        run.status = "pending"
        run.max_attempts = max(run.max_attempts, run.attempt_count + 1)
        run.next_attempt_at = datetime.now(timezone.utc)
        run.lease_owner = None
        run.lease_expires_at = None
        run.error_json = {}
        session.commit()
        session.refresh(run)
        return _run_dict(run)


def retest_feedback_run(
    companion_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    expected_feedback_revision: int,
    reason: str,
) -> dict[str, Any]:
    """Start a new semantic evaluation revision while retaining prior evidence."""
    with get_session() as session:
        run = session.get(EvaluationRun, run_id, with_for_update=True)
        if run is None or run.companion_id != companion_id or run.judge_type != JUDGE_TYPE:
            raise ValueError("Quality feedback run not found for this Companion")
        if run.feedback_revision != expected_feedback_revision:
            raise ValueError("Quality feedback revision changed; reload before retesting")
        outcome = (run.result_summary_json or {}).get("outcome") or {}
        if run.status != "completed" or outcome.get("status") != "failed":
            raise ValueError("Only completed failed feedback can be retested")
        summary = dict(run.result_summary_json or {})
        history = list(summary.get("revision_history") or [])
        history.append(
            {
                "feedback_revision": run.feedback_revision,
                "outcome": outcome,
                "evaluation_result_id": summary.get("evaluation_result_id"),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "retest_reason": reason,
            }
        )
        run.feedback_revision += 1
        run.status = "pending"
        run.aggregate_score = None
        run.attempt_count = 0
        run.next_attempt_at = datetime.now(timezone.utc)
        run.started_at = None
        run.completed_at = None
        run.lease_owner = None
        run.lease_expires_at = None
        run.error_json = {}
        run.result_summary_json = {
            **summary,
            "revision_history": history,
            "outcome": None,
            "evaluation_result_id": None,
            "retest_requested_at": datetime.now(timezone.utc).isoformat(),
        }
        session.commit()
        session.refresh(run)
        return _run_dict(run)


def get_quality_overview(companion_id: uuid.UUID) -> dict[str, Any]:
    with get_session() as session:
        companion = session.get(Companion, companion_id)
        if companion is None or companion.deleted_at is not None:
            raise ValueError("Companion not found")
        status_counts = dict(
            session.execute(
                select(EvaluationRun.status, func.count())
                .where(
                    EvaluationRun.companion_id == companion_id,
                    EvaluationRun.judge_type == JUDGE_TYPE,
                    EvaluationRun.deleted_at.is_(None),
                )
                .group_by(EvaluationRun.status)
            ).all()
        )
        domain_counts = dict(
            session.execute(
                select(EvaluationRun.source_domain, func.count())
                .where(
                    EvaluationRun.companion_id == companion_id,
                    EvaluationRun.judge_type == JUDGE_TYPE,
                    EvaluationRun.deleted_at.is_(None),
                )
                .group_by(EvaluationRun.source_domain)
            ).all()
        )
        inbox_counts = dict(
            session.execute(
                select(BadCaseInboxItem.status, func.count())
                .where(
                    BadCaseInboxItem.companion_id == companion_id,
                    BadCaseInboxItem.source_type == "evaluation_result",
                    BadCaseInboxItem.metadata_["contract_version"].astext.in_(
                        ["quality-feedback.v1", CONTRACT_VERSION]
                    ),
                    BadCaseInboxItem.deleted_at.is_(None),
                )
                .group_by(BadCaseInboxItem.status)
            ).all()
        )
        latest = session.execute(
            select(EvaluationRun)
            .where(
                EvaluationRun.companion_id == companion_id,
                EvaluationRun.judge_type == JUDGE_TYPE,
                EvaluationRun.deleted_at.is_(None),
            )
            .order_by(EvaluationRun.updated_at.desc())
            .limit(12)
        ).scalars().all()
    policy = governance_policy_service.get_governance_policy(companion_id)
    return {
        "contract_version": CONTRACT_VERSION,
        "companion_id": str(companion_id),
        "scheduler": {
            "enabled": settings.QUALITY_FEEDBACK_SCHEDULER_ENABLED,
            "poll_seconds": settings.QUALITY_FEEDBACK_SCHEDULER_POLL_SECONDS,
            "lease_seconds": settings.QUALITY_FEEDBACK_SCHEDULER_LEASE_SECONDS,
            "lookback_minutes": settings.QUALITY_FEEDBACK_LOOKBACK_MINUTES,
        },
        "run_counts": {
            status: int(status_counts.get(status, 0))
            for status in ("pending", "running", "completed", "failed", "cancelled")
        },
        "domain_counts": {
            str(domain or "quality"): int(count) for domain, count in domain_counts.items()
        },
        "bad_case_counts": {status: int(count) for status, count in inbox_counts.items()},
        "latest_runs": [_run_dict(run) for run in latest],
        "governance": _policy_snapshot(policy),
        "claim_boundaries": {
            "automatic_detection": True,
            "automatic_suggestion": True,
            "automatic_domain_application": False,
            "raw_prompt_or_message_copied": False,
        },
    }


def _find_source_run(
    session: Any,
    *,
    source_entity_type: str,
    source_entity_id: uuid.UUID,
    source_entity_revision: int,
) -> EvaluationRun | None:
    return session.execute(
        select(EvaluationRun).where(
            EvaluationRun.source_entity_type == source_entity_type,
            EvaluationRun.source_entity_id == source_entity_id,
            EvaluationRun.source_entity_revision == source_entity_revision,
            EvaluationRun.judge_type == JUDGE_TYPE,
            EvaluationRun.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def _claim_due_runs(*, worker_id: str, limit: int) -> list[uuid.UUID]:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        rows = session.execute(
            select(EvaluationRun)
            .where(
                EvaluationRun.judge_type == JUDGE_TYPE,
                EvaluationRun.deleted_at.is_(None),
                EvaluationRun.attempt_count < EvaluationRun.max_attempts,
                or_(EvaluationRun.next_attempt_at.is_(None), EvaluationRun.next_attempt_at <= now),
                or_(
                    EvaluationRun.status == "pending",
                    and_(
                        EvaluationRun.status == "running",
                        EvaluationRun.lease_expires_at.is_not(None),
                        EvaluationRun.lease_expires_at <= now,
                    ),
                ),
            )
            .order_by(EvaluationRun.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        ).scalars().all()
        for run in rows:
            run.status = "running"
            run.attempt_count += 1
            run.started_at = run.started_at or now
            run.lease_owner = worker_id
            run.lease_expires_at = now + timedelta(
                seconds=max(10, settings.QUALITY_FEEDBACK_SCHEDULER_LEASE_SECONDS)
            )
            run.next_attempt_at = None
        session.commit()
        return [run.id for run in rows]


def _execute_run(run_id: uuid.UUID, *, worker_id: str) -> None:
    with get_session() as session:
        run = session.get(EvaluationRun, run_id, with_for_update=True)
        if run is None or run.status != "running" or run.lease_owner != worker_id:
            return
        source_type = run.source_entity_type or "trace_run"
        spec = SOURCE_SPECS.get(source_type)
        if spec is None:
            raise ValueError("Unsupported quality feedback source")
        source_id = run.source_entity_id or run.source_trace_run_id
        source = session.get(spec.model, source_id) if source_id else None
        if source is None:
            raise ValueError("Source evidence no longer exists")

        checks = _evaluate_source(session, source_type, source)
        outcome = _summarize_checks(checks)
        result = EvaluationResult(
            evaluation_run_id=run.id,
            user_id=run.user_id,
            companion_id=run.companion_id,
            trace_run_id=run.source_trace_run_id,
            status=outcome["status"],
            score=outcome["score"],
            judge_reason=outcome["reason"],
            output_json={
                "contract_version": CONTRACT_VERSION,
                "feedback_revision": run.feedback_revision,
                "source_domain": run.source_domain,
                "source_entity_type": source_type,
                "checks": checks,
                "content_retention": "identifiers_status_and_policy_evidence_only",
            },
            expected_json={
                "source_terminal": True,
                "learned_policies_shadow": True,
                "domain_writes_require_existing_gates": True,
            },
            metadata_={
                "contract_version": CONTRACT_VERSION,
                "feedback_revision": run.feedback_revision,
            },
        )
        session.add(result)
        session.flush()

        bad_case, regression = _reconcile_quality_evidence(
            session,
            run=run,
            result=result,
            source=source,
            source_type=source_type,
            checks=checks,
            outcome=outcome,
        )
        run.status = "completed"
        run.aggregate_score = outcome["score"]
        run.completed_at = datetime.now(timezone.utc)
        run.lease_owner = None
        run.lease_expires_at = None
        run.error_json = {}
        run.result_summary_json = {
            **(run.result_summary_json or {}),
            "outcome": outcome,
            "feedback_revision": run.feedback_revision,
            "evaluation_result_id": str(result.id),
            "bad_case_inbox_item_id": str(bad_case.id) if bad_case else None,
            "regression_case_id": str(regression.id) if regression else None,
            "automatic_domain_application": False,
        }
        session.commit()


def _reconcile_quality_evidence(
    session: Any,
    *,
    run: EvaluationRun,
    result: EvaluationResult,
    source: Any,
    source_type: str,
    checks: list[dict[str, Any]],
    outcome: dict[str, Any],
) -> tuple[BadCaseInboxItem | None, RegressionCase | None]:
    bad_case = session.execute(
        select(BadCaseInboxItem).where(
            BadCaseInboxItem.companion_id == run.companion_id,
            BadCaseInboxItem.source_type == "evaluation_result",
            BadCaseInboxItem.metadata_["evaluation_run_id"].astext == str(run.id),
            BadCaseInboxItem.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    regression = None
    if bad_case and bad_case.created_regression_case_id:
        regression = session.get(RegressionCase, bad_case.created_regression_case_id)

    if outcome["status"] == "failed":
        failed_keys = [item["key"] for item in checks if item["status"] == "failed"]
        if bad_case is None:
            trace = source if source_type == "trace_run" else None
            bad_case = BadCaseInboxItem(
                user_id=run.user_id,
                companion_id=run.companion_id,
                conversation_id=getattr(trace, "conversation_id", None),
                message_id=getattr(trace, "message_id", None),
                trace_run_id=run.source_trace_run_id,
                source_type="evaluation_result",
                case_type="evaluation_failed",
                title="运行时质量反馈发现失败",
                description=outcome["reason"],
                severity="high" if "learned_policy_gate" in failed_keys else "medium",
                status="open",
                evidence_summary=(
                    f"{source_type} {run.source_entity_id or run.source_trace_run_id} "
                    "的确定性检查未全部通过。"
                ),
                suggested_fix="查看失败检查，修复后使用重新验证；系统不会自动改写伙伴状态。",
                metadata_={
                    "contract_version": CONTRACT_VERSION,
                    "evaluation_run_id": str(run.id),
                    "latest_evaluation_result_id": str(result.id),
                    "latest_feedback_revision": run.feedback_revision,
                    "failed_check_keys": failed_keys,
                    "retest_count": max(0, run.feedback_revision - 1),
                },
            )
            session.add(bad_case)
            session.flush()
        else:
            previous_status = bad_case.status
            bad_case.status = "open"
            bad_case.description = outcome["reason"]
            bad_case.metadata_ = {
                **(bad_case.metadata_ or {}),
                "contract_version": CONTRACT_VERSION,
                "latest_evaluation_result_id": str(result.id),
                "latest_feedback_revision": run.feedback_revision,
                "failed_check_keys": failed_keys,
                "retest_count": max(0, run.feedback_revision - 1),
            }
            if previous_status != "open":
                session.add(BadCaseTriageEvent(
                    bad_case_inbox_item_id=bad_case.id,
                    user_id=run.user_id,
                    previous_status=previous_status,
                    new_status="open",
                    action="quality_retest_failed",
                    reason="最新质量复测仍未通过。",
                    metadata_={"feedback_revision": run.feedback_revision},
                ))

        if regression is None:
            regression = RegressionCase(
                user_id=run.user_id,
                companion_id=run.companion_id,
                source_bad_case_id=bad_case.id,
                title=f"质量反馈回归：{source_type}",
                case_type="runtime_quality_feedback",
                input_json={
                    "source_entity_type": source_type,
                    "source_entity_id": str(run.source_entity_id or run.source_trace_run_id),
                    "failed_check_keys": failed_keys,
                },
                expected_behavior="相同运行证据在修复后不再触发这些确定性质量失败。",
                expected_json={"failed_check_count": 0, "learned_policies": "shadow"},
                status="failed",
                metadata_={
                    "contract_version": CONTRACT_VERSION,
                    "source_bad_case_inbox_item_id": str(bad_case.id),
                    "latest_evaluation_result_id": str(result.id),
                    "latest_feedback_revision": run.feedback_revision,
                    "automatic_application": False,
                },
            )
            session.add(regression)
            session.flush()
            bad_case.created_regression_case_id = regression.id
        else:
            regression.status = "failed"
            regression.metadata_ = {
                **(regression.metadata_ or {}),
                "latest_evaluation_result_id": str(result.id),
                "latest_feedback_revision": run.feedback_revision,
                "automatic_application": False,
            }
        return bad_case, regression

    if bad_case is not None and run.feedback_revision > 1:
        previous_status = bad_case.status
        bad_case.status = "resolved"
        bad_case.metadata_ = {
            **(bad_case.metadata_ or {}),
            "contract_version": CONTRACT_VERSION,
            "resolved_evaluation_result_id": str(result.id),
            "resolved_feedback_revision": run.feedback_revision,
        }
        session.add(BadCaseTriageEvent(
            bad_case_inbox_item_id=bad_case.id,
            user_id=run.user_id,
            previous_status=previous_status,
            new_status="resolved",
            action="quality_retest_passed",
            reason="最新质量复测已通过；历史失败证据继续保留。",
            metadata_={"feedback_revision": run.feedback_revision},
        ))
        if regression is not None:
            regression.status = "passed"
            regression.metadata_ = {
                **(regression.metadata_ or {}),
                "latest_evaluation_result_id": str(result.id),
                "latest_feedback_revision": run.feedback_revision,
                "automatic_application": False,
            }
    return bad_case, regression


def _evaluate_source(session: Any, source_type: str, source: Any) -> list[dict[str, Any]]:
    if source_type == "trace_run":
        checks = _evaluate_trace(source)
    elif source_type == "presence_occurrence":
        checks = _evaluate_presence(source)
    elif source_type == "tool_run":
        checks = _evaluate_tool_run(source)
    elif source_type in {"discord_dm_delivery", "discord_channel_delivery"}:
        checks = _evaluate_delivery(source, source_type=source_type)
    elif source_type == "channel_memory_candidate":
        review = session.execute(
            select(ChannelMemoryReview)
            .where(ChannelMemoryReview.channel_memory_candidate_id == source.id)
            .order_by(ChannelMemoryReview.updated_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        checks = _evaluate_channel_memory(source, review)
    elif source_type == "cross_companion_memory_event":
        review = session.execute(
            select(CrossCompanionMemoryReview)
            .where(CrossCompanionMemoryReview.cross_companion_memory_event_id == source.id)
            .order_by(CrossCompanionMemoryReview.updated_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        checks = _evaluate_cross_companion_memory(source, review)
    else:
        raise ValueError("Unsupported quality feedback source")
    if not any(item["key"] == "learned_policy_gate" for item in checks):
        checks.append(_learned_policy_check())
    checks.append(_check(
        "content_retention",
        "passed",
        "only identifiers, statuses and policy evidence were inspected",
    ))
    return checks


def _evaluate_trace(trace: TraceRun) -> list[dict[str, Any]]:
    metadata = trace.metadata_ or {}
    response = metadata.get("turn_response_json") if isinstance(metadata.get("turn_response_json"), dict) else {}
    post_turn = metadata.get("post_turn_effects") if isinstance(metadata.get("post_turn_effects"), dict) else {}
    conversation_graph = trace.agent_graph_name in {"conversation_graph", "room_conversation_graph"}
    checks = [
        _check("trace_terminal", "passed" if trace.status in TERMINAL_TRACE_STATUSES else "failed", f"trace_status={trace.status}"),
        _check("runtime_outcome", "passed" if trace.status == "completed" else "failed", f"runtime_status={trace.status}"),
    ]
    if conversation_graph and trace.status == "completed":
        provider_complete = bool(trace.model_provider and trace.model_name and trace.output_summary)
        checks.extend([
            _check("provider_evidence", "passed" if provider_complete else "failed", "provider/model/output evidence present" if provider_complete else "completed conversation trace lacks provider/model/output evidence"),
            _check("post_turn_effects", "passed" if post_turn.get("status") == "completed" else "failed", f"post_turn_status={post_turn.get('status') or 'missing'}"),
        ])
    else:
        checks.extend([
            _check("provider_evidence", "skipped", "not a completed conversation graph"),
            _check("post_turn_effects", "skipped", "not a completed conversation graph"),
        ])
    run_errors = response.get("_run_errors") if isinstance(response, dict) else []
    bad_signals = response.get("bad_case_signals") if isinstance(response, dict) else []
    signal_count = len(run_errors or []) + len(bad_signals or [])
    checks.extend([
        _check("runtime_signals", "warning" if signal_count else "passed", f"structured_signal_count={signal_count}"),
        _learned_policy_check(),
        _check("cross_boundary_content", "skipped", "domain review evidence remains authoritative"),
    ])
    return checks


def _evaluate_presence(occurrence: PresenceScheduleOccurrence) -> list[dict[str, Any]]:
    status = occurrence.status
    outcome_status = "failed" if status == "failed" else ("warning" if status == "expired" else "passed")
    checks = [
        _check("presence_terminal", "passed", f"status={status}"),
        _check("presence_outcome", outcome_status, f"status={status};attempts={occurrence.attempt_count}"),
    ]
    if status == "suppressed":
        checks.append(_check(
            "meaningful_silence",
            "passed" if occurrence.suppression_reason else "warning",
            f"suppression_reason={occurrence.suppression_reason or 'missing'}",
        ))
    return checks


def _evaluate_tool_run(run: ToolRun) -> list[dict[str, Any]]:
    status = run.status
    checks = [
        _check("tool_terminal", "passed", f"status={status}"),
        _check("tool_outcome", "failed" if status in {"failed", "timed_out"} else "passed", f"status={status};attempts={run.attempt_count}"),
    ]
    executed = status == "succeeded"
    checks.append(_check(
        "tool_permission_gate",
        "failed" if executed and run.permission_required and not run.permission_granted else "passed",
        f"required={run.permission_required};granted={run.permission_granted}",
    ))
    checks.append(_check(
        "tool_confirmation_gate",
        "failed" if executed and run.confirmation_required and not run.confirmed_at else "passed",
        f"required={run.confirmation_required};confirmed={bool(run.confirmed_at)}",
    ))
    return checks


def _evaluate_delivery(delivery: Any, *, source_type: str) -> list[dict[str, Any]]:
    status = delivery.delivery_status
    return [
        _check("delivery_terminal", "passed", f"source={source_type};status={status}"),
        _check("delivery_outcome", "failed" if status == "failed" else "passed", f"status={status};attempts={delivery.attempt_count}"),
    ]


def _evaluate_channel_memory(
    candidate: ChannelMemoryCandidate,
    review: ChannelMemoryReview | None,
) -> list[dict[str, Any]]:
    reviewed = review is not None and review.review_decision != "pending"
    requires_decision = candidate.candidate_status in {"approved", "rejected", "committed"}
    return [
        _check("channel_memory_review_required", "passed" if candidate.requires_user_review else "failed", f"requires_user_review={candidate.requires_user_review}"),
        _check("channel_memory_auto_commit_blocked", "passed" if not candidate.auto_commit_allowed else "failed", f"auto_commit_allowed={candidate.auto_commit_allowed}"),
        _check("channel_memory_raw_payload_blocked", "passed" if not candidate.raw_payload_storage_allowed else "failed", f"raw_payload_storage_allowed={candidate.raw_payload_storage_allowed}"),
        _check("channel_memory_review_evidence", "passed" if (reviewed or not requires_decision) else "failed", f"status={candidate.candidate_status};reviewed={reviewed}"),
    ]


def _evaluate_cross_companion_memory(
    event: CrossCompanionMemoryEvent,
    review: CrossCompanionMemoryReview | None,
) -> list[dict[str, Any]]:
    reviewed = review is not None and review.decision != "pending"
    return [
        _check("cross_companion_scope", "passed" if event.source_companion_id != event.target_companion_id else "failed", "source and target Companion scopes remain distinct"),
        _check("cross_companion_review_required", "passed" if event.review_required else "failed", f"review_required={event.review_required}"),
        _check("cross_companion_review_evidence", "passed" if reviewed else "failed", f"status={event.status};reviewed={reviewed}"),
    ]


def _learned_policy_check() -> dict[str, Any]:
    shadow = MEMORY_RERANKER_POLICY_MODE == "shadow" and PRESENCE_BANDIT_POLICY_MODE == "shadow"
    return _check(
        "learned_policy_gate",
        "passed" if shadow else "failed",
        f"memory={MEMORY_RERANKER_POLICY_MODE};presence={PRESENCE_BANDIT_POLICY_MODE}",
    )


def _summarize_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [item for item in checks if item["status"] == "failed"]
    warnings = [item for item in checks if item["status"] == "warning"]
    applicable = [item for item in checks if item["status"] != "skipped"]
    value = {"passed": 1.0, "warning": 0.5, "failed": 0.0}
    score = round(sum(value[item["status"]] for item in applicable) / max(1, len(applicable)), 4)
    status = "failed" if failed else ("warning" if warnings else "passed")
    reason = (
        f"{len(failed)} 项失败：{', '.join(item['key'] for item in failed)}"
        if failed
        else (f"{len(warnings)} 项需要关注" if warnings else "确定性运行质量检查通过")
    )
    return {"status": status, "score": score, "reason": reason, "failed_count": len(failed), "warning_count": len(warnings)}


def _record_worker_failure(run_id: uuid.UUID, *, worker_id: str, exc: Exception) -> None:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        run = session.get(EvaluationRun, run_id, with_for_update=True)
        if run is None or run.status != "running" or run.lease_owner != worker_id:
            return
        exhausted = run.attempt_count >= run.max_attempts
        run.status = "failed" if exhausted else "pending"
        run.next_attempt_at = None if exhausted else now + timedelta(seconds=min(300, 10 * (2 ** max(0, run.attempt_count - 1))))
        run.lease_owner = None
        run.lease_expires_at = None
        run.completed_at = now if exhausted else None
        run.error_json = {
            "code": "QUALITY_FEEDBACK_WORKER_FAILURE",
            "error_type": type(exc).__name__,
            "retryable": not exhausted,
        }
        session.commit()


def _check(key: str, status: str, reason: str) -> dict[str, Any]:
    return {"key": key, "status": status, "reason": reason}


def _policy_snapshot(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": policy.get("contract_version"),
        "revision": policy.get("revision"),
        "mode": policy.get("mode"),
        "domain_effective_modes": {
            item["key"]: item["effective_mode"] for item in policy.get("domains", [])
        },
        "learned_policy_status": policy.get("learned_policy_status"),
    }


def _run_dict(run: EvaluationRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "companion_id": str(run.companion_id),
        "source_trace_run_id": str(run.source_trace_run_id) if run.source_trace_run_id else None,
        "source_domain": run.source_domain or "quality",
        "source_entity_type": run.source_entity_type or "trace_run",
        "source_entity_id": str(run.source_entity_id) if run.source_entity_id else (str(run.source_trace_run_id) if run.source_trace_run_id else None),
        "source_entity_revision": run.source_entity_revision,
        "feedback_revision": run.feedback_revision,
        "trigger_type": run.trigger_type,
        "status": run.status,
        "judge_type": run.judge_type,
        "aggregate_score": run.aggregate_score,
        "attempt_count": run.attempt_count,
        "max_attempts": run.max_attempts,
        "next_attempt_at": run.next_attempt_at.isoformat() if run.next_attempt_at else None,
        "lease_expires_at": run.lease_expires_at.isoformat() if run.lease_expires_at else None,
        "result_summary": run.result_summary_json or {},
        "error": run.error_json or {},
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
