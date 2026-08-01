"""Permanent deletion for one archived, Single-Companion Conversation."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, update

from app.db.base import Base
from app.db.models import Conversation, ConversationDeletionProof
from app.services import data_rights_deletion_service
from app.services.conversation_service import (
    ConversationTurnError,
    is_companion_room_conversation,
)
from app.services.settings_service import get_session


CONTRACT_VERSION = "conversation-deletion.v1"
CONFIRMATION_PHRASE = "永久删除"

# These objects can span a Conversation boundary or remain independently useful.
# Their nullable Conversation reference is detached; their own domain lifecycle is
# not silently overridden by deleting one transcript.
PRESERVED_REFERENCE_TABLES = {
    "co_presence_sessions",
    "realtime_copresence_sessions",
    "shared_experience_records",
    "presence_schedules",
    "project_tasks",
}
SCOPE_EXCLUDED_TABLES = {
    "users",
    "companions",
    "companion_deletion_requests",
    "companion_deletion_scope_rows",
    "conversation_deletion_proofs",
    *PRESERVED_REFERENCE_TABLES,
}
MESSAGE_ARRAY_REFERENCES = {
    "companion_affect_events": "source_message_ids",
    "companion_context_documents": "source_message_ids",
    "growth_candidates": "evidence_message_ids",
    "growth_records": "evidence_message_ids",
    "memory_abstraction_candidates": "source_message_ids",
    "memories": "source_message_ids",
    "memory_candidates": "source_message_ids",
    "presence_opportunities": "evidence_message_ids",
    "relationship_candidates": "source_message_ids",
    "relationship_events": "source_message_ids",
    "relationship_explanation_events": "evidence_message_ids",
}


def preview_conversation_deletion(
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    import app.db.models  # noqa: F401

    with get_session() as session:
        conversation = _get_deletable_conversation(
            session,
            conversation_id,
            companion_id,
            lock=False,
        )
        scope = _discover_scope(session, conversation.id)
        return _preview_dict(conversation, scope)


def permanently_delete_conversation(
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    confirmation_phrase: str,
) -> dict[str, Any]:
    import app.db.models  # noqa: F401

    if confirmation_phrase != CONFIRMATION_PHRASE:
        raise ConversationTurnError(
            "CONVERSATION_DELETION_CONFIRMATION_MISMATCH",
            f"请输入“{CONFIRMATION_PHRASE}”以确认不可恢复的删除。",
        )

    now = datetime.now(timezone.utc)
    with get_session() as session:
        conversation = _get_deletable_conversation(
            session,
            conversation_id,
            companion_id,
            lock=True,
        )
        scope = _discover_scope(session, conversation.id)
        preview = _preview_dict(conversation, scope)
        _detach_preserved_references(session, scope)
        _detach_scoped_cycles(session, scope)

        deleted_counts: dict[str, int] = {}
        scoped_names = {name for name, ids in scope.items() if ids}
        order = data_rights_deletion_service._child_first_order(scoped_names)
        for table_name in order:
            table = Base.metadata.tables[table_name]
            result = session.execute(
                delete(table).where(table.c.id.in_(scope[table_name]))
            )
            deleted_counts[table_name] = int(result.rowcount or 0)

        proof = ConversationDeletionProof(
            user_id=conversation.user_id,
            user_scope_hash=_scope_hash("user", conversation.user_id),
            companion_scope_hash=_scope_hash(
                "companion",
                conversation.user_id,
                conversation.companion_id,
            ),
            conversation_scope_hash=_scope_hash(
                "conversation",
                conversation.user_id,
                conversation.id,
            ),
            deleted_counts_json=deleted_counts,
            completed_at=now,
            metadata_={
                "contract_version": CONTRACT_VERSION,
                "content_retained": False,
                "preserved_boundary_records": sorted(PRESERVED_REFERENCE_TABLES),
            },
        )
        session.add(proof)
        session.commit()
        session.refresh(proof)

    return {
        "contract_version": CONTRACT_VERSION,
        "status": "deleted",
        "conversation_id": str(conversation_id),
        "completed_at": proof.completed_at.isoformat(),
        "affected_counts": preview["affected_counts"],
        "deleted_counts": deleted_counts,
        "content_disclosure": "counts_and_safe_status_only",
    }


def _get_deletable_conversation(
    session: Any,
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    lock: bool,
) -> Conversation:
    statement = select(Conversation).where(Conversation.id == conversation_id)
    if lock:
        statement = statement.with_for_update()
    conversation = session.execute(statement).scalar_one_or_none()
    if (
        conversation is None
        or conversation.deleted_at is not None
        or conversation.companion_id != companion_id
        or is_companion_room_conversation(conversation)
    ):
        raise ConversationTurnError(
            "CONVERSATION_NOT_FOUND",
            "没有找到这段伙伴对话。",
        )
    if conversation.status != "archived":
        raise ConversationTurnError(
            "CONVERSATION_DELETE_REQUIRES_ARCHIVE",
            "请先归档这段对话，再执行永久删除。",
        )
    return conversation


def _discover_scope(
    session: Any,
    conversation_id: uuid.UUID,
) -> dict[str, set[uuid.UUID]]:
    tables = Base.metadata.tables
    scope: dict[str, set[uuid.UUID]] = {
        "conversations": {conversation_id},
    }

    for _ in range(len(tables) + 1):
        changed = False
        for child in tables.values():
            if child.name in SCOPE_EXCLUDED_TABLES or "id" not in child.c:
                continue
            candidate_ids: set[uuid.UUID] = set()
            for column in child.c:
                for foreign_key in column.foreign_keys:
                    parent_name = foreign_key.column.table.name
                    parent_ids = scope.get(parent_name)
                    if not parent_ids:
                        continue
                    candidate_ids.update(
                        session.execute(
                            select(child.c.id).where(column.in_(parent_ids))
                        ).scalars()
                    )
            if not candidate_ids:
                continue
            existing = scope.setdefault(child.name, set())
            new_ids = candidate_ids - existing
            if new_ids:
                existing.update(new_ids)
                changed = True
        message_ids = scope.get("messages", set())
        if message_ids:
            for table_name, column_name in MESSAGE_ARRAY_REFERENCES.items():
                if table_name in SCOPE_EXCLUDED_TABLES:
                    continue
                table = tables.get(table_name)
                if table is None or column_name not in table.c:
                    continue
                candidate_ids = set(
                    session.execute(
                        select(table.c.id).where(
                            table.c[column_name].op("&&")(list(message_ids))
                        )
                    ).scalars()
                )
                existing = scope.setdefault(table_name, set())
                new_ids = candidate_ids - existing
                if new_ids:
                    existing.update(new_ids)
                    changed = True
        if not changed:
            return scope
    raise RuntimeError("Conversation deletion scope did not converge")


def _detach_preserved_references(
    session: Any,
    scope: dict[str, set[uuid.UUID]],
) -> None:
    tables = Base.metadata.tables
    for table_name in PRESERVED_REFERENCE_TABLES:
        table = tables.get(table_name)
        if table is None:
            continue
        for column in table.c:
            for foreign_key in column.foreign_keys:
                parent_ids = scope.get(foreign_key.column.table.name)
                if not parent_ids:
                    continue
                if not column.nullable:
                    raise ConversationTurnError(
                        "CONVERSATION_DELETE_BOUNDARY_BLOCKED",
                        "这段对话仍被一个不可自动解除的共享边界引用，请先处理该关联。",
                    )
                values: dict[str, Any] = {column.name: None}
                if table_name == "presence_schedules":
                    values.update(status="paused", pause_reason="conversation_deleted")
                session.execute(
                    update(table)
                    .where(column.in_(parent_ids))
                    .values(values)
                )


def _detach_scoped_cycles(
    session: Any,
    scope: dict[str, set[uuid.UUID]],
) -> None:
    scoped_names = {name for name, ids in scope.items() if ids}
    cyclic_groups = data_rights_deletion_service._cyclic_table_groups(scoped_names)
    cyclic_group_by_table = {
        table_name: group
        for group in cyclic_groups
        for table_name in group
    }
    for child_name in sorted(scoped_names):
        child = Base.metadata.tables[child_name]
        group = cyclic_group_by_table.get(child_name)
        if group is None:
            continue
        for column in child.c:
            if not column.nullable:
                continue
            for foreign_key in column.foreign_keys:
                parent_name = foreign_key.column.table.name
                parent_ids = scope.get(parent_name)
                if parent_name not in group or not parent_ids:
                    continue
                session.execute(
                    update(child)
                    .where(
                        child.c.id.in_(scope[child_name]),
                        column.in_(parent_ids),
                    )
                    .values({column.name: None})
                )


def _preview_dict(
    conversation: Conversation,
    scope: dict[str, set[uuid.UUID]],
) -> dict[str, Any]:
    count = lambda table_name: len(scope.get(table_name, set()))
    affected_counts = {
        "messages": count("messages"),
        "memories": count("memories"),
        "growth": (
            count("growth_candidates")
            + count("growth_records")
            + count("companion_persona_growth_candidates")
            + count("companion_persona_growth_events")
        ),
        "tool_runs": count("tool_runs"),
        "task_runs": count("conversation_task_runs"),
        "channel_bindings": (
            count("discord_dm_conversation_bindings")
            + count("discord_channel_room_bindings")
        ),
        "related_records": max(
            0,
            sum(len(ids) for ids in scope.values())
            - count("conversations")
            - count("messages"),
        ),
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "conversation_id": str(conversation.id),
        "companion_id": str(conversation.companion_id),
        "title": conversation.title,
        "status": conversation.status,
        "affected_counts": affected_counts,
        "preserved_domains": [
            "共同空间与共享经历本体",
            "独立项目任务",
            "主动陪伴计划",
        ],
        "requires_phrase": CONFIRMATION_PHRASE,
    }


def _scope_hash(prefix: str, *values: uuid.UUID) -> str:
    raw = ":".join([prefix, *(str(value) for value in values)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
