"""Evidence-grounded dynamic summaries and long-term Companion profiles."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.agents.providers.base import LLMProviderError
from app.agents.providers.openai_compatible import OpenAICompatibleProvider
from app.core.config import settings
from app.db.models import Companion, CompanionContextDocument, Conversation, Memory, Message


ALGORITHM_VERSION = "context-documents.v1"
DOCUMENT_KINDS = ("recent_summary", "long_term_profile")
MIN_MESSAGES_FIRST_REFRESH = 2
MIN_NEW_MESSAGES_REFRESH = 6
MAX_SOURCE_MESSAGES = 24
MAX_SOURCE_MEMORIES = 12

_engine = None
_provider = None


class ContextDocumentError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def _get_provider():
    global _provider
    if _provider is None:
        _provider = OpenAICompatibleProvider()
    return _provider


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def refresh_context_documents(
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    conversation_id: uuid.UUID,
    force: bool = False,
    reason: str = "post_turn_refresh",
) -> dict[str, Any]:
    """Generate both context layers from bounded, Companion-scoped evidence."""
    with get_session() as session:
        conversation = session.get(Conversation, conversation_id)
        companion = session.get(Companion, companion_id)
        if (
            conversation is None or companion is None
            or conversation.user_id != user_id or conversation.companion_id != companion_id
            or companion.user_id != user_id
        ):
            raise ContextDocumentError("CONTEXT_SCOPE_MISMATCH", "Conversation and Companion scope do not match.")
        if conversation.retention_mode == "temporary" or not conversation.cross_session_memory_enabled:
            return {"outcome": "suppressed", "reason": "conversation_retention_policy", "documents": []}

        messages = list(session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.companion_id == companion_id,
                Message.deleted_at.is_(None),
            ).order_by(Message.created_at.desc()).limit(MAX_SOURCE_MESSAGES)
        ).scalars())
        messages.reverse()
        current = _active_documents(session, companion_id)
        latest_source_at = max(
            (doc.source_max_message_at for doc in current.values() if doc.source_max_message_at),
            default=None,
        )
        new_message_count = sum(1 for item in messages if latest_source_at is None or item.created_at > latest_source_at)
        required = MIN_MESSAGES_FIRST_REFRESH if not current else MIN_NEW_MESSAGES_REFRESH
        if not force and new_message_count < required:
            return {
                "outcome": "not_due",
                "reason": "insufficient_new_evidence",
                "new_message_count": new_message_count,
                "required": required,
                "documents": [_document_dict(item) for item in current.values()],
            }
        if not messages:
            return {"outcome": "not_due", "reason": "no_message_evidence", "documents": []}

        memories = list(session.execute(
            select(Memory).where(
                Memory.companion_id == companion_id,
                Memory.owner_companion_id == companion_id,
                Memory.deleted_at.is_(None),
                Memory.state.in_(("active", "dormant")),
                Memory.consent_status.notin_(("blocked", "revoked", "pending_review")),
            ).order_by(Memory.importance.desc(), Memory.updated_at.desc()).limit(MAX_SOURCE_MEMORIES)
        ).scalars())
        previous = {kind: doc.content for kind, doc in current.items()}

    payload = _generate_documents(messages, memories, previous)
    source_message_ids = [uuid.UUID(value) for value in payload["evidence_message_ids"]]
    source_memory_ids = [uuid.UUID(value) for value in payload["evidence_memory_ids"]]
    source_max_at = max(item.created_at for item in messages)

    with get_session() as session:
        conversation = session.execute(
            select(Conversation).where(Conversation.id == conversation_id).with_for_update()
        ).scalar_one_or_none()
        if conversation is None or conversation.retention_mode == "temporary" or not conversation.cross_session_memory_enabled:
            return {"outcome": "suppressed", "reason": "retention_policy_changed", "documents": []}
        session.execute(
            select(Companion).where(Companion.id == companion_id).with_for_update()
        ).scalar_one()
        created = []
        for kind in DOCUMENT_KINDS:
            content = payload[kind]["content"].strip()
            active = session.execute(
                select(CompanionContextDocument).where(
                    CompanionContextDocument.companion_id == companion_id,
                    CompanionContextDocument.document_kind == kind,
                    CompanionContextDocument.status == "active",
                ).order_by(CompanionContextDocument.version.desc()).with_for_update()
            ).scalars().first()
            if active and active.content_hash == _hash(content):
                created.append(active)
                continue
            next_version = session.execute(select(func.max(CompanionContextDocument.version)).where(
                CompanionContextDocument.companion_id == companion_id,
                CompanionContextDocument.document_kind == kind,
            )).scalar() or 0
            if active:
                active.status = "superseded"
                active.updated_at = datetime.now(timezone.utc)
            row = CompanionContextDocument(
                user_id=user_id,
                companion_id=companion_id,
                conversation_id=conversation_id,
                supersedes_document_id=active.id if active else None,
                document_kind=kind,
                version=int(next_version) + 1,
                status="active",
                content=content,
                content_hash=_hash(content),
                structured_json=payload[kind]["structured"],
                source_message_ids=source_message_ids,
                source_memory_ids=source_memory_ids,
                source_max_message_at=source_max_at,
                confidence=payload["confidence"],
                generation_reason=reason,
                generated_by_provider=payload["provider"],
                generated_by_model=payload["model"],
                user_corrected=False,
                metadata_={"algorithm_version": ALGORITHM_VERSION},
            )
            session.add(row)
            session.flush()
            created.append(row)
        session.commit()
        return {"outcome": "refreshed", "reason": reason, "documents": [_document_dict(item) for item in created]}


def list_context_documents(
    companion_id: uuid.UUID,
    *,
    kind: str | None = None,
    include_history: bool = False,
) -> dict[str, Any]:
    with get_session() as session:
        stmt = select(CompanionContextDocument).where(CompanionContextDocument.companion_id == companion_id)
        if kind:
            if kind not in DOCUMENT_KINDS:
                raise ContextDocumentError("INVALID_DOCUMENT_KIND", "Unsupported context document kind.")
            stmt = stmt.where(CompanionContextDocument.document_kind == kind)
        if not include_history:
            stmt = stmt.where(CompanionContextDocument.status == "active")
        rows = list(session.execute(stmt.order_by(
            CompanionContextDocument.document_kind,
            CompanionContextDocument.version.desc(),
        )).scalars())
        return {"items": [_document_dict(row) for row in rows], "total": len(rows)}


def correct_context_document(
    document_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    expected_version: int,
    content: str,
    reason: str,
) -> dict[str, Any]:
    return _append_user_version(
        document_id, companion_id, expected_version=expected_version,
        content=content.strip(), reason=reason, operation="corrected",
    )


def restore_context_document(
    document_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    expected_version: int,
    reason: str,
) -> dict[str, Any]:
    return _append_user_version(
        document_id, companion_id, expected_version=expected_version,
        content=None, reason=reason, operation="restored",
    )


def invalidate_context_document(
    document_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    expected_version: int,
    reason: str,
) -> dict[str, Any]:
    with get_session() as session:
        row = session.execute(select(CompanionContextDocument).where(
            CompanionContextDocument.id == document_id,
            CompanionContextDocument.companion_id == companion_id,
        ).with_for_update()).scalar_one_or_none()
        if row is None:
            raise ContextDocumentError("CONTEXT_DOCUMENT_NOT_FOUND", "Context document not found.")
        active = _active_document(session, companion_id, row.document_kind, lock=True)
        if active is None or active.id != row.id or active.version != expected_version:
            raise ContextDocumentError(
                "CONTEXT_DOCUMENT_VERSION_CONFLICT", "Context document changed after it was loaded.",
                {"expected_version": expected_version, "current_version": active.version if active else None},
            )
        row.status = "invalidated"
        row.invalidated_at = datetime.now(timezone.utc)
        row.invalidation_reason = reason
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        return _document_dict(row)


def _append_user_version(
    source_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    expected_version: int,
    content: str | None,
    reason: str,
    operation: str,
) -> dict[str, Any]:
    with get_session() as session:
        source = session.get(CompanionContextDocument, source_id)
        if source is None or source.companion_id != companion_id:
            raise ContextDocumentError("CONTEXT_DOCUMENT_NOT_FOUND", "Context document not found.")
        active = _active_document(session, companion_id, source.document_kind, lock=True)
        if active is None or active.version != expected_version:
            raise ContextDocumentError(
                "CONTEXT_DOCUMENT_VERSION_CONFLICT", "Context document changed after it was loaded.",
                {"expected_version": expected_version, "current_version": active.version if active else None},
            )
        next_content = content if content is not None else source.content
        if not next_content:
            raise ContextDocumentError("CONTEXT_DOCUMENT_CONTENT_REQUIRED", "Context document content is required.")
        active.status = "superseded"
        active.updated_at = datetime.now(timezone.utc)
        row = CompanionContextDocument(
            user_id=source.user_id,
            companion_id=companion_id,
            conversation_id=source.conversation_id,
            supersedes_document_id=active.id,
            restored_from_document_id=source.id if operation == "restored" else None,
            document_kind=source.document_kind,
            version=active.version + 1,
            status="active",
            content=next_content,
            content_hash=_hash(next_content),
            structured_json={**(source.structured_json or {}), "user_revision_reason": reason},
            source_message_ids=source.source_message_ids or [],
            source_memory_ids=source.source_memory_ids or [],
            source_max_message_at=source.source_max_message_at,
            confidence=1.0,
            generation_reason=f"user_{operation}",
            generated_by_provider=None,
            generated_by_model=None,
            user_corrected=True,
            metadata_={"algorithm_version": ALGORITHM_VERSION, "operation": operation},
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _document_dict(row)


def _generate_documents(messages: list[Message], memories: list[Memory], previous: dict[str, str]) -> dict[str, Any]:
    provider = _get_provider()
    message_lines = "\n".join(
        f"[{item.id}] {item.role}: {item.content[:1200]}" for item in messages
    )
    memory_lines = "\n".join(
        f"[{item.id}] {item.type}: {(item.summary or item.content)[:500]}" for item in memories
    ) or "(none)"
    system = """You maintain evidence-grounded private context for one AI Companion.
Return one JSON object only. Never invent facts, feelings, relationship changes, or preferences.
The recent summary may summarize the supplied messages. The long-term profile may retain only
stable facts supported by supplied messages or approved memories. Treat previous documents as
fallible context and remove claims contradicted by newer evidence.

Required JSON shape:
{
  "recent_summary": {"content": "...", "topic": "...", "goal": "...", "open_threads": ["..."]},
  "long_term_profile": {"content": "...", "stable_preferences": ["..."], "ongoing_goals": ["..."]},
  "evidence_message_ids": ["uuid"],
  "evidence_memory_ids": ["uuid"],
  "confidence": 0.0
}
Constraints: content must be concise Chinese; confidence is 0..1; evidence IDs must be selected
only from the supplied IDs; omit unsupported claims instead of guessing."""
    user = f"""Previous recent summary:
{previous.get('recent_summary') or '(none)'}

Previous long-term profile:
{previous.get('long_term_profile') or '(none)'}

Approved Companion-private memories:
{memory_lines}

Recent conversation messages:
{message_lines}
"""
    try:
        result = provider.generate(system, user, {"temperature": 0.1, "max_tokens": 1600})
    except LLMProviderError as exc:
        raise ContextDocumentError(exc.code, str(exc), exc.details) from exc
    try:
        raw = str(result["content"]).strip()
        if raw.startswith("```"):
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ContextDocumentError("CONTEXT_DOCUMENT_INVALID_PROVIDER_OUTPUT", "Provider returned invalid context JSON.") from exc

    allowed_messages = {str(item.id) for item in messages}
    allowed_memories = {str(item.id) for item in memories}
    evidence_messages = parsed.get("evidence_message_ids") or []
    evidence_memories = parsed.get("evidence_memory_ids") or []
    if not set(map(str, evidence_messages)).issubset(allowed_messages) or not set(map(str, evidence_memories)).issubset(allowed_memories):
        raise ContextDocumentError("CONTEXT_DOCUMENT_UNGROUNDED_EVIDENCE", "Provider cited evidence outside the Companion scope.")
    recent = parsed.get("recent_summary") or {}
    profile = parsed.get("long_term_profile") or {}
    recent_content = str(recent.get("content") or "").strip()
    profile_content = str(profile.get("content") or "").strip()
    if not recent_content or not profile_content or len(recent_content) > 4000 or len(profile_content) > 6000:
        raise ContextDocumentError("CONTEXT_DOCUMENT_INVALID_CONTENT", "Generated context content is missing or exceeds its bound.")
    confidence = max(0.0, min(1.0, float(parsed.get("confidence") or 0.0)))
    return {
        "recent_summary": {"content": recent_content, "structured": recent},
        "long_term_profile": {"content": profile_content, "structured": profile},
        "confidence": confidence,
        "provider": result.get("provider"),
        "model": result.get("model"),
        "evidence_message_ids": [str(value) for value in evidence_messages],
        "evidence_memory_ids": [str(value) for value in evidence_memories],
    }


def _active_documents(session: Session, companion_id: uuid.UUID) -> dict[str, CompanionContextDocument]:
    rows = session.execute(select(CompanionContextDocument).where(
        CompanionContextDocument.companion_id == companion_id,
        CompanionContextDocument.status == "active",
    ).order_by(CompanionContextDocument.version.desc())).scalars()
    result: dict[str, CompanionContextDocument] = {}
    for row in rows:
        result.setdefault(row.document_kind, row)
    return result


def _active_document(session: Session, companion_id: uuid.UUID, kind: str, *, lock: bool = False):
    stmt = select(CompanionContextDocument).where(
        CompanionContextDocument.companion_id == companion_id,
        CompanionContextDocument.document_kind == kind,
        CompanionContextDocument.status == "active",
    ).order_by(CompanionContextDocument.version.desc())
    if lock:
        stmt = stmt.with_for_update()
    return session.execute(stmt).scalars().first()


def _document_dict(row: CompanionContextDocument) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "companion_id": str(row.companion_id),
        "conversation_id": str(row.conversation_id) if row.conversation_id else None,
        "document_kind": row.document_kind,
        "version": row.version,
        "status": row.status,
        "content": row.content,
        "structured": row.structured_json or {},
        "source_message_ids": [str(value) for value in row.source_message_ids or []],
        "source_memory_ids": [str(value) for value in row.source_memory_ids or []],
        "confidence": row.confidence,
        "generation_reason": row.generation_reason,
        "generated_by_provider": row.generated_by_provider,
        "generated_by_model": row.generated_by_model,
        "user_corrected": row.user_corrected,
        "supersedes_document_id": str(row.supersedes_document_id) if row.supersedes_document_id else None,
        "restored_from_document_id": str(row.restored_from_document_id) if row.restored_from_document_id else None,
        "invalidation_reason": row.invalidation_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
