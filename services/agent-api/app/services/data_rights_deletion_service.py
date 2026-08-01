"""Recoverable and resumable Companion deletion lifecycle.

The workflow deliberately separates the recovery window, scope discovery,
reference detachment and table-by-table purge. A failed purge keeps its durable
scope so the user can retry without reviving already deleted content.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import Base
from app.db.models import (
    ChannelBinding,
    Companion,
    CompanionDeletionRequest,
    CompanionDeletionScopeRow,
    CompanionRoomTurnStep,
    ConversationTaskRun,
    DiscordChannelDelivery,
    DiscordDmConversationBinding,
    DiscordDmDelivery,
    EvaluationRun,
    PresenceSchedule,
    PresenceScheduleOccurrence,
    ScopedHardStopEvent,
    ToolRun,
)
from app.services.settings_service import get_session


CONTRACT_VERSION = "companion-deletion.v1"
RECOVERY_DAYS = 30
BACKUP_DELETION_DAYS = 30
ACTIVE_REQUEST_STATUSES = {"trash", "purging", "failed"}
PURGE_EXCLUDED_TABLES = {
    "companion_deletion_requests",
    "companion_deletion_scope_rows",
    "users",
}


def create_deletion_request(
    companion_id: uuid.UUID,
    *,
    confirmation_name: str,
    skip_recovery_window: bool,
    export_choice: str,
    idempotency_key: str,
) -> dict[str, Any]:
    if export_choice not in {"skip", "completed"}:
        raise ValueError("Choose whether to skip export or confirm that export is complete")
    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required")
    now = _now()
    with get_session() as session:
        companion = session.get(Companion, companion_id, with_for_update=True)
        if companion is None or companion.deleted_at is not None:
            existing = session.execute(
                select(CompanionDeletionRequest)
                .where(
                    CompanionDeletionRequest.companion_id == companion_id,
                    CompanionDeletionRequest.status.in_(ACTIVE_REQUEST_STATUSES),
                )
                .order_by(CompanionDeletionRequest.requested_at.desc())
            ).scalars().first()
            if existing:
                return _request_to_dict(existing)
            raise ValueError("Companion not found")
        if _normalize_name(confirmation_name) != _normalize_name(companion.name):
            raise ValueError("The confirmation name does not match the current Companion")
        existing_by_key = session.execute(
            select(CompanionDeletionRequest).where(
                CompanionDeletionRequest.user_id == companion.user_id,
                CompanionDeletionRequest.idempotency_key == idempotency_key.strip(),
            )
        ).scalar_one_or_none()
        if existing_by_key:
            return _request_to_dict(existing_by_key)
        active = session.execute(
            select(CompanionDeletionRequest).where(
                CompanionDeletionRequest.companion_id == companion.id,
                CompanionDeletionRequest.status.in_(ACTIVE_REQUEST_STATUSES),
            )
        ).scalar_one_or_none()
        if active:
            raise ValueError("This Companion already has an active deletion request")

        request = CompanionDeletionRequest(
            user_id=companion.user_id,
            companion_id=companion.id,
            companion_scope_hash=_scope_hash(companion.user_id, companion.id),
            status="trash",
            deletion_mode="immediate" if skip_recovery_window else "recovery_window",
            previous_companion_status=companion.current_status,
            current_stage="recovery_window",
            restore_snapshot_json={},
            affected_counts_json={},
            deleted_counts_json={},
            requested_at=now,
            purge_after=now if skip_recovery_window else now + timedelta(days=RECOVERY_DAYS),
            backup_delete_due_at=(now if skip_recovery_window else now + timedelta(days=RECOVERY_DAYS))
            + timedelta(days=BACKUP_DELETION_DAYS),
            idempotency_key=idempotency_key.strip(),
            metadata_={
                "contract_version": CONTRACT_VERSION,
                "export_choice": export_choice,
                "content_retained": False,
            },
        )
        session.add(request)
        session.flush()
        request.affected_counts_json = _domain_counts(session, companion.id)
        request.restore_snapshot_json = _quiesce_companion(session, companion, request.id)
        session.commit()
        request_id = request.id
        companion_display_name = companion.name

    if skip_recovery_window:
        result = execute_deletion_request(request_id, allow_before_due=True)
        result["companion_display_name"] = companion_display_name
        return result
    return get_deletion_request(request_id)


def get_deletion_request(request_id: uuid.UUID) -> dict[str, Any]:
    with get_session() as session:
        request = session.get(CompanionDeletionRequest, request_id)
        if request is None:
            raise ValueError("Deletion request not found")
        companion = (
            session.get(Companion, request.companion_id)
            if request.companion_id
            else None
        )
        return _request_to_dict(
            request,
            companion_display_name=companion.name if companion else None,
        )


def get_companion_deletion_request(companion_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as session:
        request = session.execute(
            select(CompanionDeletionRequest)
            .where(
                CompanionDeletionRequest.companion_id == companion_id,
                CompanionDeletionRequest.status.in_(ACTIVE_REQUEST_STATUSES),
            )
            .order_by(CompanionDeletionRequest.requested_at.desc())
        ).scalars().first()
        if request is None:
            return None
        companion = session.get(Companion, companion_id)
        return _request_to_dict(
            request,
            companion_display_name=companion.name if companion else None,
        )


def restore_deletion_request(request_id: uuid.UUID) -> dict[str, Any]:
    now = _now()
    with get_session() as session:
        request = session.get(
            CompanionDeletionRequest,
            request_id,
            with_for_update=True,
        )
        if request is None or request.status != "trash":
            raise ValueError("Only a Companion in the recovery window can be restored")
        if request.purge_after <= now:
            raise ValueError("The recovery window has expired")
        if request.companion_id is None:
            raise ValueError("Companion data is no longer recoverable")
        companion = session.get(Companion, request.companion_id)
        if companion is None:
            raise ValueError("Companion data is no longer recoverable")
        snapshot = request.restore_snapshot_json or {}
        companion.deleted_at = None
        companion.current_status = request.previous_companion_status or "idle"
        companion.updated_at = now

        for item in snapshot.get("channel_bindings", []):
            row = session.get(ChannelBinding, _uuid_or_none(item.get("id")))
            if row and row.companion_id == companion.id and row.revoked_at is None:
                row.binding_status = item.get("binding_status") or "paused"
                row.can_receive_inbound = bool(item.get("can_receive_inbound"))
                row.can_send_outbound = bool(item.get("can_send_outbound"))
                row.checkin_enabled = bool(item.get("checkin_enabled"))
        for item in snapshot.get("dm_bindings", []):
            row = session.get(DiscordDmConversationBinding, _uuid_or_none(item.get("id")))
            if row and row.companion_id == companion.id and row.revoked_at is None:
                row.binding_status = item.get("binding_status") or "paused"
                row.revision += 1
        for item in snapshot.get("presence_schedules", []):
            row = session.get(PresenceSchedule, _uuid_or_none(item.get("id")))
            if row and row.companion_id == companion.id:
                row.status = item.get("status") or "paused"
                row.pause_reason = item.get("pause_reason")
                row.revision += 1
        hard_stop_id = _uuid_or_none(snapshot.get("hard_stop_event_id"))
        hard_stop = session.get(ScopedHardStopEvent, hard_stop_id) if hard_stop_id else None
        if hard_stop and hard_stop.companion_id == companion.id and hard_stop.released_at is None:
            hard_stop.hard_stop_status = "released"
            hard_stop.released_at = now

        request.status = "restored"
        request.current_stage = "restored"
        request.restored_at = now
        request.revision += 1
        request.restore_snapshot_json = {}
        session.execute(
            delete(CompanionDeletionScopeRow).where(
                CompanionDeletionScopeRow.deletion_request_id == request.id
            )
        )
        session.commit()
        session.refresh(request)
        return _request_to_dict(
            request,
            companion_display_name=companion.name,
        )


def execute_deletion_request(
    request_id: uuid.UUID,
    *,
    allow_before_due: bool = False,
) -> dict[str, Any]:
    stage = "start"
    try:
        with get_session() as session:
            request = session.get(
                CompanionDeletionRequest,
                request_id,
                with_for_update=True,
            )
            if request is None:
                raise ValueError("Deletion request not found")
            if request.status == "completed":
                return _request_to_dict(request)
            if request.status not in {"trash", "failed", "purging"}:
                raise ValueError("Deletion request cannot be executed from its current state")
            if request.companion_id is None:
                raise ValueError("Deletion request has no recoverable Companion scope")
            if request.purge_after > _now() and not allow_before_due:
                raise ValueError("The recovery window has not expired")
            request.status = "purging"
            request.current_stage = "scope_discovery"
            request.purge_started_at = request.purge_started_at or _now()
            request.attempt_count += 1
            request.failure_code = None
            request.failure_stage = None
            request.revision += 1
            session.commit()

        stage = "scope_discovery"
        _build_purge_scope(request_id)
        stage = "reference_detachment"
        _detach_nullable_scope_references(request_id)
        stage = "content_purge"
        _purge_scope_tables(request_id)
        stage = "completion"
        with get_session() as session:
            request = session.get(CompanionDeletionRequest, request_id)
            if request is None:
                raise ValueError("Deletion request not found")
            request.status = "completed"
            request.current_stage = "completed"
            request.completed_at = _now()
            request.companion_id = None
            request.restore_snapshot_json = {}
            request.failure_code = None
            request.failure_stage = None
            request.revision += 1
            session.execute(
                delete(CompanionDeletionScopeRow).where(
                    CompanionDeletionScopeRow.deletion_request_id == request.id
                )
            )
            session.commit()
            session.refresh(request)
            return _request_to_dict(request)
    except ValueError:
        raise
    except (SQLAlchemyError, RuntimeError) as exc:
        _mark_failed(request_id, stage, type(exc).__name__)
        raise ValueError(
            "Permanent deletion paused safely; retry from the deletion status panel"
        ) from exc


def process_due_deletions(*, limit: int = 2) -> list[dict[str, Any]]:
    now = _now()
    with get_session() as session:
        request_ids = list(
            session.execute(
                select(CompanionDeletionRequest.id)
                .where(
                    CompanionDeletionRequest.status == "trash",
                    CompanionDeletionRequest.purge_after <= now,
                )
                .order_by(CompanionDeletionRequest.purge_after.asc())
                .limit(max(1, min(limit, 10)))
            ).scalars()
        )
    results = []
    for request_id in request_ids:
        try:
            results.append(execute_deletion_request(request_id))
        except ValueError:
            # Failure state is durable and visible; one request must not prevent
            # other due requests from being processed.
            continue
    return results


def _quiesce_companion(
    session: Any,
    companion: Companion,
    deletion_request_id: uuid.UUID,
) -> dict[str, Any]:
    now = _now()
    channel_bindings = list(
        session.execute(
            select(ChannelBinding).where(ChannelBinding.companion_id == companion.id)
        ).scalars()
    )
    dm_bindings = list(
        session.execute(
            select(DiscordDmConversationBinding).where(
                DiscordDmConversationBinding.companion_id == companion.id
            )
        ).scalars()
    )
    presence_schedules = list(
        session.execute(
            select(PresenceSchedule).where(PresenceSchedule.companion_id == companion.id)
        ).scalars()
    )
    snapshot = {
        "channel_bindings": [
            {
                "id": str(row.id),
                "binding_status": row.binding_status,
                "can_receive_inbound": row.can_receive_inbound,
                "can_send_outbound": row.can_send_outbound,
                "checkin_enabled": row.checkin_enabled,
            }
            for row in channel_bindings
        ],
        "dm_bindings": [
            {"id": str(row.id), "binding_status": row.binding_status}
            for row in dm_bindings
        ],
        "presence_schedules": [
            {"id": str(row.id), "status": row.status, "pause_reason": row.pause_reason}
            for row in presence_schedules
        ],
    }
    for row in channel_bindings:
        if row.revoked_at is None:
            row.binding_status = "disabled"
            row.can_receive_inbound = False
            row.can_send_outbound = False
            row.checkin_enabled = False
    for row in dm_bindings:
        if row.revoked_at is None:
            row.binding_status = "paused"
            row.revision += 1
    for row in presence_schedules:
        row.status = "paused"
        row.pause_reason = "data_deletion_recovery_window"
        row.revision += 1

    session.execute(
        update(PresenceScheduleOccurrence)
        .where(
            PresenceScheduleOccurrence.companion_id == companion.id,
            PresenceScheduleOccurrence.status.in_({"scheduled", "claimed", "retry_wait"}),
        )
        .values(
            status="cancelled",
            suppression_reason="data_deletion_requested",
            lease_expires_at=None,
            next_attempt_at=None,
        )
    )
    session.execute(
        update(ToolRun)
        .where(
            ToolRun.companion_id == companion.id,
            ToolRun.status.in_(
                {
                    "planned",
                    "awaiting_input",
                    "awaiting_confirmation",
                    "queued",
                    "running",
                    "retry_scheduled",
                }
            ),
        )
        .values(
            status="cancelled",
            cancel_requested_at=now,
            terminal_reason="data_deletion_requested",
            lease_owner=None,
            lease_expires_at=None,
            next_attempt_at=None,
        )
    )
    session.execute(
        update(EvaluationRun)
        .where(
            EvaluationRun.companion_id == companion.id,
            EvaluationRun.status.in_({"pending", "running"}),
        )
        .values(status="cancelled", lease_owner=None, lease_expires_at=None, next_attempt_at=None)
    )
    session.execute(
        update(DiscordDmDelivery)
        .where(
            DiscordDmDelivery.companion_id == companion.id,
            DiscordDmDelivery.delivery_status.in_({"queued", "leased", "retry_scheduled"}),
        )
        .values(
            delivery_status="cancelled",
            cancelled_at=now,
            lease_owner=None,
            lease_expires_at=None,
            next_attempt_at=None,
        )
    )
    session.execute(
        update(DiscordChannelDelivery)
        .where(
            DiscordChannelDelivery.companion_id == companion.id,
            DiscordChannelDelivery.delivery_status.in_({"queued", "leased", "retry_scheduled"}),
        )
        .values(
            delivery_status="cancelled",
            cancelled_at=now,
            lease_owner=None,
            lease_expires_at=None,
            next_attempt_at=None,
        )
    )
    session.execute(
        update(CompanionRoomTurnStep)
        .where(
            CompanionRoomTurnStep.companion_id == companion.id,
            CompanionRoomTurnStep.status.in_({"planned", "queued", "running", "retry_wait"}),
        )
        .values(
            status="cancelled",
            completed_at=now,
            lease_owner=None,
            lease_expires_at=None,
            retry_available_at=None,
        )
    )
    session.execute(
        update(ConversationTaskRun)
        .where(
            ConversationTaskRun.companion_id == companion.id,
            ConversationTaskRun.status.in_(
                {
                    "draft",
                    "awaiting_input",
                    "awaiting_approval",
                    "ready",
                    "running",
                    "paused",
                    "blocked",
                }
            ),
        )
        .values(
            status="cancelled",
            cancellation_requested=True,
            stop_reason="data_deletion_requested",
            completed_at=now,
            lease_owner=None,
            lease_expires_at=None,
        )
    )

    hard_stop = ScopedHardStopEvent(
        user_id=companion.user_id,
        hard_stop_scope="companion",
        hard_stop_status="active",
        initiated_by="user",
        companion_id=companion.id,
        stop_reason="Companion deletion recovery window",
        stops_listening=True,
        stops_speaking=True,
        stops_observing=True,
        stops_memory_capture=True,
        stops_context_capture=True,
        requires_audit=True,
        policy_snapshot_json={
            "contract_version": CONTRACT_VERSION,
            "deletion_request_id": str(deletion_request_id),
        },
        metadata_={"implementation_origin": "data_rights"},
    )
    session.add(hard_stop)
    session.flush()
    snapshot["hard_stop_event_id"] = str(hard_stop.id)

    companion.deleted_at = now
    companion.current_status = "trash"
    companion.current_focus = None
    companion.updated_at = now
    return snapshot


def _build_purge_scope(request_id: uuid.UUID) -> None:
    import app.db.models  # noqa: F401

    scope = CompanionDeletionScopeRow.__table__
    tables = Base.metadata.tables
    with get_session() as session:
        request = session.get(CompanionDeletionRequest, request_id)
        if request is None or request.companion_id is None:
            raise RuntimeError("Deletion scope is unavailable")
        existing = session.scalar(
            select(func.count())
            .select_from(scope)
            .where(scope.c.deletion_request_id == request_id)
        )
        if not existing:
            _insert_scope_select(
                session,
                request_id,
                "companions",
                select(tables["companions"].c.id).where(
                    tables["companions"].c.id == request.companion_id
                ),
            )
            for table in tables.values():
                if table.name in PURGE_EXCLUDED_TABLES or table.name == "companions":
                    continue
                direct_columns = [
                    element.parent
                    for constraint in table.foreign_key_constraints
                    for element in constraint.elements
                    if element.column.table.name == "companions"
                    and element.column.name == "id"
                ]
                if direct_columns:
                    _insert_scope_select(
                        session,
                        request_id,
                        table.name,
                        select(table.c.id).where(
                            or_(*(column == request.companion_id for column in direct_columns))
                        ),
                    )

            for _ in range(len(tables) + 1):
                before = int(
                    session.scalar(
                        select(func.count())
                        .select_from(scope)
                        .where(scope.c.deletion_request_id == request_id)
                    )
                    or 0
                )
                for child in tables.values():
                    if child.name in PURGE_EXCLUDED_TABLES:
                        continue
                    for constraint in child.foreign_key_constraints:
                        for element in constraint.elements:
                            parent = element.column.table
                            if parent.name in PURGE_EXCLUDED_TABLES:
                                continue
                            parent_scope = scope.alias("parent_scope")
                            rows = (
                                select(child.c.id)
                                .select_from(
                                    child.join(
                                        parent_scope,
                                        element.parent == parent_scope.c.row_id,
                                    )
                                )
                                .where(
                                    parent_scope.c.deletion_request_id == request_id,
                                    parent_scope.c.table_name == parent.name,
                                )
                            )
                            _insert_scope_select(
                                session,
                                request_id,
                                child.name,
                                rows,
                            )
                after = int(
                    session.scalar(
                        select(func.count())
                        .select_from(scope)
                        .where(scope.c.deletion_request_id == request_id)
                    )
                    or 0
                )
                if after == before:
                    break
            else:
                raise RuntimeError("Deletion scope did not converge")

        table_counts = dict(
            session.execute(
                select(scope.c.table_name, func.count())
                .where(scope.c.deletion_request_id == request_id)
                .group_by(scope.c.table_name)
            ).all()
        )
        request.affected_counts_json = {
            **(request.affected_counts_json or {}),
            "purge_tables": len(table_counts),
            "purge_rows": sum(int(value) for value in table_counts.values()),
        }
        request.current_stage = "reference_detachment"
        request.revision += 1
        session.commit()


def _insert_scope_select(
    session: Any,
    request_id: uuid.UUID,
    table_name: str,
    rows: Any,
) -> None:
    scope = CompanionDeletionScopeRow.__table__
    statement = (
        pg_insert(scope)
        .from_select(
            ["deletion_request_id", "table_name", "row_id"],
            select(
                literal(request_id),
                literal(table_name),
                rows.subquery().c.id,
            ),
        )
        .on_conflict_do_nothing(
            index_elements=["deletion_request_id", "table_name", "row_id"]
        )
    )
    session.execute(statement)


def _detach_nullable_scope_references(request_id: uuid.UUID) -> None:
    scope = CompanionDeletionScopeRow.__table__
    tables = Base.metadata.tables
    with get_session() as session:
        scoped_names = set(
            session.execute(
                select(scope.c.table_name)
                .where(scope.c.deletion_request_id == request_id)
                .distinct()
            ).scalars()
        )
        cyclic_groups = _cyclic_table_groups(scoped_names)
        cyclic_group_by_table = {
            table_name: group
            for group in cyclic_groups
            for table_name in group
        }
        for child_name in sorted(scoped_names):
            child = tables[child_name]
            child_scope = (
                select(scope.c.row_id)
                .where(
                    scope.c.deletion_request_id == request_id,
                    scope.c.table_name == child_name,
                )
            )
            for column in child.c:
                if not column.nullable:
                    continue
                for foreign_key in column.foreign_keys:
                    parent_name = foreign_key.column.table.name
                    group = cyclic_group_by_table.get(child_name)
                    if group is None or parent_name not in group:
                        continue
                    parent_scope = select(scope.c.row_id).where(
                        scope.c.deletion_request_id == request_id,
                        scope.c.table_name == parent_name,
                    )
                    session.execute(
                        update(child)
                        .where(
                            child.c.id.in_(child_scope),
                            column.in_(parent_scope),
                        )
                        .values({column.name: None})
                    )
        request = session.get(CompanionDeletionRequest, request_id)
        if request:
            request.current_stage = "content_purge"
            request.revision += 1
        session.commit()


def _purge_scope_tables(request_id: uuid.UUID) -> None:
    scope = CompanionDeletionScopeRow.__table__
    tables = Base.metadata.tables
    with get_session() as session:
        scoped_names = set(
            session.execute(
                select(scope.c.table_name)
                .where(scope.c.deletion_request_id == request_id)
                .distinct()
            ).scalars()
        )
    order = _child_first_order(scoped_names)
    for table_name in order:
        table = tables[table_name]
        with get_session() as session:
            scoped_ids = select(scope.c.row_id).where(
                scope.c.deletion_request_id == request_id,
                scope.c.table_name == table_name,
            )
            result = session.execute(delete(table).where(table.c.id.in_(scoped_ids)))
            request = session.get(CompanionDeletionRequest, request_id)
            if request is None:
                raise RuntimeError("Deletion request disappeared during purge")
            deleted_counts = dict(request.deleted_counts_json or {})
            deleted_counts[table_name] = int(result.rowcount or 0)
            request.deleted_counts_json = deleted_counts
            request.current_stage = f"purge:{table_name}"
            request.revision += 1
            session.commit()


def _child_first_order(scoped_names: set[str]) -> list[str]:
    tables = Base.metadata.tables
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming_count = {name: 0 for name in scoped_names}
    cyclic_groups = _cyclic_table_groups(scoped_names)
    cyclic_group_by_table = {
        table_name: group
        for group in cyclic_groups
        for table_name in group
    }
    for child_name in scoped_names:
        child = tables[child_name]
        for column in child.c:
            for foreign_key in column.foreign_keys:
                parent_name = foreign_key.column.table.name
                if parent_name in scoped_names and parent_name != child_name:
                    child_group = cyclic_group_by_table.get(child_name)
                    if (
                        column.nullable
                        and child_group is not None
                        and parent_name in child_group
                    ):
                        # This reference was cleared in the preceding durable
                        # stage specifically to break a dependency cycle.
                        continue
                    if parent_name not in outgoing[child_name]:
                        outgoing[child_name].add(parent_name)
                        incoming_count[parent_name] += 1
    queue = deque(sorted(name for name, count in incoming_count.items() if count == 0))
    order: list[str] = []
    while queue:
        child = queue.popleft()
        order.append(child)
        for parent in sorted(outgoing.get(child, set())):
            incoming_count[parent] -= 1
            if incoming_count[parent] == 0:
                queue.append(parent)
    if len(order) != len(scoped_names):
        unresolved = sorted(scoped_names - set(order))
        raise RuntimeError(f"Non-null deletion dependency cycle: {','.join(unresolved)}")
    return order


def _cyclic_table_groups(scoped_names: set[str]) -> list[set[str]]:
    """Return strongly connected FK groups, including nullable self-links."""

    tables = Base.metadata.tables
    graph: dict[str, set[str]] = defaultdict(set)
    for child_name in scoped_names:
        child = tables[child_name]
        for column in child.c:
            for foreign_key in column.foreign_keys:
                parent_name = foreign_key.column.table.name
                if parent_name in scoped_names:
                    graph[child_name].add(parent_name)

    index = 0
    indices: dict[str, int] = {}
    low_links: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    groups: list[set[str]] = []

    def visit(table_name: str) -> None:
        nonlocal index
        indices[table_name] = index
        low_links[table_name] = index
        index += 1
        stack.append(table_name)
        on_stack.add(table_name)

        for parent_name in graph.get(table_name, set()):
            if parent_name not in indices:
                visit(parent_name)
                low_links[table_name] = min(
                    low_links[table_name],
                    low_links[parent_name],
                )
            elif parent_name in on_stack:
                low_links[table_name] = min(
                    low_links[table_name],
                    indices[parent_name],
                )

        if low_links[table_name] != indices[table_name]:
            return
        group: set[str] = set()
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            group.add(member)
            if member == table_name:
                break
        if len(group) > 1 or table_name in graph.get(table_name, set()):
            groups.append(group)

    for table_name in sorted(scoped_names):
        if table_name not in indices:
            visit(table_name)
    return groups


def _domain_counts(session: Any, companion_id: uuid.UUID) -> dict[str, int]:
    from app.db.models import Conversation, Memory, Message

    def count(model: type, *filters: Any) -> int:
        return int(
            session.scalar(select(func.count()).select_from(model).where(*filters))
            or 0
        )

    return {
        "conversations": count(Conversation, Conversation.companion_id == companion_id),
        "messages": count(Message, Message.companion_id == companion_id),
        "private_memories": count(Memory, Memory.companion_id == companion_id),
        "channel_bindings": count(ChannelBinding, ChannelBinding.companion_id == companion_id),
        "tool_runs": count(ToolRun, ToolRun.companion_id == companion_id),
    }


def _request_to_dict(
    request: CompanionDeletionRequest,
    *,
    companion_display_name: str | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "id": str(request.id),
        "companion_id": str(request.companion_id) if request.companion_id else None,
        # This name is resolved only while the Companion row still exists. It
        # is never stored in the content-free deletion proof.
        "companion_display_name": companion_display_name,
        "status": request.status,
        "deletion_mode": request.deletion_mode,
        "current_stage": request.current_stage,
        "requested_at": request.requested_at.isoformat(),
        "purge_after": request.purge_after.isoformat(),
        "completed_at": request.completed_at.isoformat() if request.completed_at else None,
        "restored_at": request.restored_at.isoformat() if request.restored_at else None,
        "backup_delete_due_at": (
            request.backup_delete_due_at.isoformat()
            if request.backup_delete_due_at
            else None
        ),
        "affected_counts": request.affected_counts_json or {},
        "deleted_counts": request.deleted_counts_json or {},
        "failure_code": request.failure_code,
        "failure_stage": request.failure_stage,
        "can_restore": request.status == "trash" and request.purge_after > _now(),
        "can_retry": request.status == "failed",
        "content_disclosure": "counts_and_safe_status_only",
    }


def _mark_failed(request_id: uuid.UUID, stage: str, failure_code: str) -> None:
    try:
        with get_session() as session:
            request = session.get(CompanionDeletionRequest, request_id)
            if request:
                request.status = "failed"
                request.current_stage = "failed"
                request.failure_stage = stage
                request.failure_code = failure_code[:120]
                request.revision += 1
                session.commit()
    except SQLAlchemyError:
        return


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _scope_hash(user_id: uuid.UUID, companion_id: uuid.UUID) -> str:
    return hashlib.sha256(f"{user_id}:{companion_id}".encode("utf-8")).hexdigest()


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if not value:
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)
