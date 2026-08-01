"""Companion-scoped, content-free reliability reliability diagnostics.

Only identifiers, counts, statuses and safe operational reasons leave this
service. It never returns message, memory, prompt, provider or tool payloads.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import (
    BadCaseInboxItem,
    ChannelBinding,
    ChannelMemoryCandidate,
    Companion,
    CompanionAffectEvent,
    CompanionRoomTurnStep,
    Conversation,
    CrossCompanionMemoryEvent,
    CrossCompanionMemoryReview,
    DiscordChannelDelivery,
    DiscordDmDelivery,
    EvaluationRun,
    GrowthCandidate,
    Memory,
    MemoryContentRevision,
    MemoryLifecycleEvent,
    Message,
    PresenceScheduleOccurrence,
    RegressionRun,
    RelationshipCandidate,
    ScopedHardStopEvent,
    ToolRun,
    TraceRun,
)
from app.memory.learned_reranker import POLICY_MODE as MEMORY_RERANKER_POLICY_MODE
from app.presence.contextual_bandit import POLICY_MODE as PRESENCE_BANDIT_POLICY_MODE
from app.services.settings_service import get_session


CONTRACT_VERSION = "reliability-diagnostics.v1"
ACTIVE_BAD_CASE_STATUSES = {"open", "triaged", "investigating"}


@dataclass(frozen=True)
class RuntimeSpec:
    key: str
    label: str
    model: type
    status_field: str
    active: frozenset[str]
    terminal: frozenset[str]
    failed: frozenset[str]
    next_attempt_field: str | None = None
    lease_field: str | None = None


RUNTIME_SPECS = (
    RuntimeSpec("presence", "Presence", PresenceScheduleOccurrence, "status", frozenset({"scheduled", "claimed", "retry_wait"}), frozenset({"delivered", "suppressed", "failed", "expired", "cancelled"}), frozenset({"failed", "expired"}), "next_attempt_at", "lease_expires_at"),
    RuntimeSpec("tools", "Tools", ToolRun, "status", frozenset({"awaiting_input", "awaiting_confirmation", "queued", "running", "retry_scheduled"}), frozenset({"succeeded", "failed", "cancelled", "blocked", "timed_out"}), frozenset({"failed", "timed_out"}), "next_attempt_at", "lease_expires_at"),
    RuntimeSpec("quality", "Quality feedback", EvaluationRun, "status", frozenset({"pending", "running"}), frozenset({"completed", "failed", "cancelled"}), frozenset({"failed"}), "next_attempt_at", "lease_expires_at"),
    RuntimeSpec("discord_dm", "Discord DM", DiscordDmDelivery, "delivery_status", frozenset({"queued", "leased", "retry_scheduled"}), frozenset({"delivered", "failed", "cancelled", "suppressed"}), frozenset({"failed"}), "next_attempt_at", "lease_expires_at"),
    RuntimeSpec("discord_room", "Discord Room", DiscordChannelDelivery, "delivery_status", frozenset({"queued", "leased", "retry_scheduled"}), frozenset({"delivered", "failed", "cancelled", "suppressed"}), frozenset({"failed"}), "next_attempt_at", "lease_expires_at"),
    RuntimeSpec("room_turn", "Room turn", CompanionRoomTurnStep, "status", frozenset({"planned", "queued", "running", "retry_wait"}), frozenset({"completed", "failed", "cancelled", "suppressed"}), frozenset({"failed"}), "retry_available_at", "lease_expires_at"),
)


def get_reliability_diagnostics(companion_id: uuid.UUID) -> dict[str, Any]:
    companion = _require_companion(companion_id)
    domains = [_runtime_domain(companion_id, spec) for spec in RUNTIME_SPECS]
    state_domains = _state_domains(companion_id)
    quality = _quality_summary(companion_id)
    safety = _safety_summary(companion_id)
    unavailable = sum(1 for item in domains if item["status"] == "unavailable")
    attention = sum(1 for item in domains if item["status"] in {"attention", "blocked"})
    overall = "blocked" if safety["active_hard_stops"] > 0 else ("attention" if attention or unavailable or quality["open_bad_cases"] else "healthy")
    return {
        "contract_version": CONTRACT_VERSION,
        "companion_id": str(companion_id),
        "companion_status": companion.current_status or "unknown",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "runtime_domains": domains,
        "state_domains": state_domains,
        "validation_matrix": _validation_matrix(companion_id, domains, state_domains),
        "quality": quality,
        "safety": safety,
        "capabilities": {
            "durable_presence": True,
            "durable_tools": True,
            "durable_quality_feedback": True,
            "durable_discord_dm": True,
            "durable_discord_room": True,
            "data_rights_dry_run": True,
            "recoverable_companion_deletion": True,
            "voice_runtime": "model_only_not_production_validated",
            "webrtc_livekit": "not_implemented",
            "avatar_live2d": "not_implemented",
        },
        "content_disclosure": "counts_statuses_and_safe_reasons_only",
        "retention_boundaries": {
            "single": "Companion-private Conversation and Memory retention; no Room messages are projected into Single Conversation.",
            "room": "Room Conversation remains separate and preserves participant/turn evidence when archived.",
            "discord": "Bound Web Conversation is canonical; durable delivery evidence and hashed provider references are retained, raw provider payload storage is disallowed.",
            "shared": "Shared, cross-Companion, Room and channel memory remain review-gated; rejected evidence is not promoted to private Memory.",
            "web": "Web contains the durable product history and may be a superset of Discord; channel revoke does not erase Web history or audit evidence.",
        },
    }


def get_data_rights_dry_run(companion_id: uuid.UUID, operation: str, target_id: str | None = None) -> dict[str, Any]:
    _require_companion(companion_id)
    if operation not in {"export", "forget_memory", "archive_companion", "disconnect_channels", "revoke_channels", "permanent_delete"}:
        raise ValueError("Unsupported data-rights operation")
    target_uuid = None
    if target_id:
        try:
            target_uuid = uuid.UUID(target_id)
        except ValueError as exc:
            raise ValueError("target_id must be a UUID") from exc
    if operation == "forget_memory" and target_uuid is None:
        raise ValueError("forget_memory requires target_id")

    counts = _data_scope_counts(companion_id, target_uuid if operation == "forget_memory" else None)
    if operation == "forget_memory" and counts["target_memories"] != 1:
        raise ValueError("Memory target was not found in this Companion scope")

    irreversible = operation == "permanent_delete"
    separately_authorized = False
    supported_write_path = operation in {
        "forget_memory",
        "archive_companion",
        "revoke_channels",
        "permanent_delete",
    }
    blockers: list[str] = []
    if separately_authorized:
        blockers.append("separate_user_authorization_required")
    if operation == "export":
        supported_write_path = True
    if operation == "disconnect_channels":
        blockers.append("disconnect_is_not_a_canonical_write_contract; use reviewed revoke or disable per binding")

    effects = {
        "export": "下载当前伙伴的数据副本；Secret、向量索引、原始跨边界载荷和模型思维链不会进入导出文件。",
        "forget_memory": "Would invoke the existing versioned forget path for exactly one private Memory.",
        "archive_companion": "Would archive the Companion while retaining conversations, memories and audit evidence.",
        "disconnect_channels": "Would require a per-binding disable/revoke decision; no write is executed here.",
        "revoke_channels": "Would revoke active Companion channel bindings and preserve revoke/audit evidence.",
        "permanent_delete": "进入 30 天恢复窗口，或在名称二次确认后立即永久删除；执行前会停止伙伴活动并撤销外发能力。",
    }
    return {
        "contract_version": "data-rights-dry-run.v1",
        "companion_id": str(companion_id),
        "operation": operation,
        "dry_run": True,
        "executed": False,
        "supported_write_path": supported_write_path,
        "irreversible": irreversible,
        "separate_authorization_required": separately_authorized,
        "ready_for_explicit_execution": supported_write_path and not blockers,
        "blockers": blockers,
        "effect_summary": effects[operation],
        "affected_counts": counts,
        "retained_evidence": ["content_free_deletion_proof", "backup_deletion_due_at"],
        "review_gates": ["shared_memory", "cross_companion_memory", "channel_memory", "room_memory"],
        "content_disclosure": "counts_only",
    }


def _require_companion(companion_id: uuid.UUID) -> Companion:
    with get_session() as session:
        row = session.get(Companion, companion_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Companion not found")
        session.expunge(row)
        return row


def _runtime_domain(companion_id: uuid.UUID, spec: RuntimeSpec) -> dict[str, Any]:
    try:
        with get_session() as session:
            status_col = getattr(spec.model, spec.status_field)
            rows = session.execute(select(status_col, func.count()).where(spec.model.companion_id == companion_id).group_by(status_col)).all()
            counts = Counter({str(status): int(count) for status, count in rows})
            now = datetime.now(timezone.utc)
            stuck_filters = [status_col.in_(spec.active)]
            stale_conditions = []
            if spec.lease_field:
                lease = getattr(spec.model, spec.lease_field)
                stale_conditions.append(lease.is_not(None) & (lease < now))
            if spec.next_attempt_field:
                due = getattr(spec.model, spec.next_attempt_field)
                stale_conditions.append(due.is_not(None) & (due < now))
            stuck = 0
            if stale_conditions:
                stuck = int(session.scalar(select(func.count()).select_from(spec.model).where(spec.model.companion_id == companion_id, *stuck_filters, or_(*stale_conditions))) or 0)
            failed = sum(counts[key] for key in spec.failed)
            active = sum(counts[key] for key in spec.active)
            last_30d = int(session.scalar(select(func.count()).select_from(spec.model).where(spec.model.companion_id == companion_id, spec.model.created_at >= now - timedelta(days=30))) or 0)
            status = "attention" if stuck or failed else "healthy"
            return {"key": spec.key, "label": spec.label, "status": status, "total": sum(counts.values()), "last_30d": last_30d, "active": active, "terminal": sum(counts[key] for key in spec.terminal), "failed": failed, "stuck": stuck, "status_counts": dict(sorted(counts.items()))}
    except SQLAlchemyError:
        return {"key": spec.key, "label": spec.label, "status": "unavailable", "total": 0, "active": 0, "terminal": 0, "failed": 0, "stuck": 0, "status_counts": {}, "safe_reason": "schema_or_query_unavailable"}


def _state_domains(companion_id: uuid.UUID) -> list[dict[str, Any]]:
    specs = (
        ("conversation", "Conversation", Conversation, Conversation.status, Conversation.deleted_at.is_(None)),
        ("memory", "Memory", Memory, Memory.state, Memory.deleted_at.is_(None)),
        ("growth", "Growth", GrowthCandidate, GrowthCandidate.status, True),
        ("relationship", "Relationship", RelationshipCandidate, RelationshipCandidate.status, True),
        ("affect", "Affect", CompanionAffectEvent, CompanionAffectEvent.status, True),
    )
    result = []
    for key, label, model, status_col, extra in specs:
        try:
            with get_session() as session:
                rows = session.execute(select(status_col, func.count()).where(model.companion_id == companion_id, extra).group_by(status_col)).all()
                counts = {str(status): int(count) for status, count in rows}
                result.append({"key": key, "label": label, "status": "available", "total": sum(counts.values()), "status_counts": counts})
        except SQLAlchemyError:
            result.append({"key": key, "label": label, "status": "unavailable", "total": 0, "status_counts": {}, "safe_reason": "schema_or_query_unavailable"})
    return result


def _quality_summary(companion_id: uuid.UUID) -> dict[str, int]:
    with get_session() as session:
        open_bad = session.scalar(select(func.count()).select_from(BadCaseInboxItem).where(BadCaseInboxItem.companion_id == companion_id, BadCaseInboxItem.deleted_at.is_(None), BadCaseInboxItem.status.in_(ACTIVE_BAD_CASE_STATUSES))) or 0
        failed_regressions = session.scalar(select(func.coalesce(func.sum(RegressionRun.failed_count), 0)).where(RegressionRun.companion_id == companion_id, RegressionRun.deleted_at.is_(None))) or 0
        return {"open_bad_cases": int(open_bad), "failed_regression_results": int(failed_regressions)}


def _validation_matrix(
    companion_id: uuid.UUID,
    runtime_domains: list[dict[str, Any]],
    state_domains: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expose evidence coverage without turning one snapshot into a quality claim."""
    since = datetime.now(timezone.utc) - timedelta(days=30)
    with get_session() as session:
        def counts(model: type, *filters: Any) -> tuple[int, int]:
            all_time = int(session.scalar(select(func.count()).select_from(model).where(*filters)) or 0)
            recent = int(session.scalar(select(func.count()).select_from(model).where(*filters, model.created_at >= since)) or 0)
            return all_time, recent

        trace_all, trace_recent = counts(TraceRun, TraceRun.companion_id == companion_id)
        revision_all, revision_recent = counts(MemoryContentRevision, MemoryContentRevision.companion_id == companion_id)
        lifecycle_all, lifecycle_recent = counts(MemoryLifecycleEvent, MemoryLifecycleEvent.companion_id == companion_id)

    runtime_by_key = {item["key"]: item for item in runtime_domains}
    state_by_key = {item["key"]: item for item in state_domains}
    rows = [
        ("conversation", "Conversation", trace_all, trace_recent, ["TraceRun", "EvaluationRun", "BadCase"]),
        ("memory", "Memory update / correction / forget", revision_all + lifecycle_all, revision_recent + lifecycle_recent, ["MemoryContentRevision", "MemoryLifecycleEvent"]),
        ("growth_relationship_affect", "Growth / Relationship / Affect", sum(state_by_key.get(key, {}).get("total", 0) for key in ("growth", "relationship", "affect")), 0, ["candidate", "revision", "event"]),
    ]
    for key, label in (("presence", "Presence"), ("tools", "Tools"), ("discord_dm", "Discord DM"), ("discord_room", "Discord Room"), ("room_turn", "Rooms")):
        item = runtime_by_key.get(key, {})
        rows.append((key, label, int(item.get("total", 0)), int(item.get("last_30d", 0)), ["durable_status", "lease", "retry", "terminal_evidence"]))
    return [
        {
            "key": key,
            "label": label,
            "scope": "companion",
            "all_time_evidence_count": all_time,
            "last_30d_evidence_count": recent,
            "evidence_sources": sources,
            "coverage_status": "evidence_available" if all_time else "no_evidence",
            "quality_conclusion": "snapshot_only_no_long_term_claim",
        }
        for key, label, all_time, recent, sources in rows
    ]


def _safety_summary(companion_id: uuid.UUID) -> dict[str, Any]:
    with get_session() as session:
        hard_stops = session.scalar(select(func.count()).select_from(ScopedHardStopEvent).where(ScopedHardStopEvent.companion_id == companion_id, ScopedHardStopEvent.hard_stop_status == "active", ScopedHardStopEvent.released_at.is_(None))) or 0
        revoked = session.scalar(select(func.count()).select_from(ChannelBinding).where(ChannelBinding.companion_id == companion_id, or_(ChannelBinding.binding_status == "revoked", ChannelBinding.revoked_at.is_not(None)))) or 0
        pending_channel = session.scalar(select(func.count()).select_from(ChannelMemoryCandidate).where(ChannelMemoryCandidate.companion_id == companion_id, ChannelMemoryCandidate.candidate_status.in_({"pending_review", "candidate"}))) or 0
        pending_cross = session.scalar(
            select(func.count())
            .select_from(CrossCompanionMemoryReview)
            .join(
                CrossCompanionMemoryEvent,
                CrossCompanionMemoryEvent.id == CrossCompanionMemoryReview.cross_companion_memory_event_id,
            )
            .where(
                or_(
                    CrossCompanionMemoryEvent.source_companion_id == companion_id,
                    CrossCompanionMemoryEvent.target_companion_id == companion_id,
                ),
                CrossCompanionMemoryReview.decision == "pending",
            )
        ) or 0
        return {"active_hard_stops": int(hard_stops), "revoked_channel_bindings": int(revoked), "pending_shared_reviews": int(pending_channel + pending_cross), "memory_reranker_policy_mode": MEMORY_RERANKER_POLICY_MODE, "presence_bandit_policy_mode": PRESENCE_BANDIT_POLICY_MODE, "observer_auto_speaker": False}


def _data_scope_counts(companion_id: uuid.UUID, memory_target_id: uuid.UUID | None) -> dict[str, int]:
    with get_session() as session:
        def count(model: type, *filters: Any) -> int:
            return int(session.scalar(select(func.count()).select_from(model).where(*filters)) or 0)
        return {
            "conversations": count(Conversation, Conversation.companion_id == companion_id, Conversation.deleted_at.is_(None)),
            "messages": count(Message, Message.companion_id == companion_id, Message.deleted_at.is_(None)),
            "private_memories": count(Memory, Memory.companion_id == companion_id, Memory.deleted_at.is_(None)),
            "target_memories": count(Memory, Memory.id == memory_target_id, Memory.companion_id == companion_id, Memory.deleted_at.is_(None)) if memory_target_id else 0,
            "tool_runs": count(ToolRun, ToolRun.companion_id == companion_id, ToolRun.deleted_at.is_(None)),
            "presence_occurrences": count(PresenceScheduleOccurrence, PresenceScheduleOccurrence.companion_id == companion_id),
            "channel_bindings": count(ChannelBinding, ChannelBinding.companion_id == companion_id),
            "active_channel_bindings": count(ChannelBinding, ChannelBinding.companion_id == companion_id, ChannelBinding.binding_status.notin_({"revoked", "disabled"}), ChannelBinding.revoked_at.is_(None)),
            "room_turn_steps": count(CompanionRoomTurnStep, CompanionRoomTurnStep.companion_id == companion_id),
            "open_bad_cases": count(BadCaseInboxItem, BadCaseInboxItem.companion_id == companion_id, BadCaseInboxItem.deleted_at.is_(None), BadCaseInboxItem.status.in_(ACTIVE_BAD_CASE_STATUSES)),
        }
