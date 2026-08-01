"""Memory & Memory Candidate service layer."""

import uuid
from datetime import datetime, timezone
import hashlib
import re

from app.memory.embedding import get_embedding_provider
from app.memory.decay import (
    MEMORY_LIFECYCLE_VERSION,
    calculate_personalized_half_life,
    determine_state_from_strength,
)
from app.memory.reinforcement import apply_reinforcement, compute_beta_confidence

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Companion, Memory, MemoryCandidate, MemoryContentRevision
from app.services.memory_lifecycle_service import record_memory_change
from app.services.memory_lifecycle_service import create_memory_lifecycle_event_in_session

_engine = None


class MemoryMutationError(Exception):
    """Typed failure for atomic content/revision mutations."""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _strict_embedding(content: str) -> tuple[list[float], str, str | None]:
    provider = get_embedding_provider()
    try:
        vector = provider.embed_strict(content)[0]
    except Exception as exc:
        raise MemoryMutationError(
            "MEMORY_EMBEDDING_UNAVAILABLE",
            "A real embedding is required before Saved Memory content can change.",
            {"provider": provider.provider_name, "failure_type": type(exc).__name__},
        ) from exc
    if len(vector) != settings.EMBEDDING_DIMENSIONS:
        raise MemoryMutationError(
            "MEMORY_EMBEDDING_DIMENSION_MISMATCH",
            "The embedding result does not match the configured Memory dimension.",
            {"expected": settings.EMBEDDING_DIMENSIONS, "actual": len(vector)},
        )
    return vector, provider.provider_name, settings.EMBEDDING_MODEL or None


def prepare_saved_memory_content(content: str) -> dict:
    """Prepare canonical content and a real vector before opening a write transaction."""
    normalized = content.strip()
    if not normalized:
        raise MemoryMutationError("MEMORY_CONTENT_REQUIRED", "Saved Memory content is required.")
    embedding, provider, model = _strict_embedding(normalized)
    return {
        "content": normalized,
        "content_hash": _content_hash(normalized),
        "embedding": embedding,
        "embedding_provider": provider,
        "embedding_model": model,
    }


def initialize_saved_memory_in_session(
    session: Session,
    memory: Memory,
    prepared: dict,
    *,
    reason: str,
    source_candidate_id: uuid.UUID | None = None,
) -> MemoryContentRevision:
    """Apply the invariant shared by every persisted Saved Memory creation path."""
    memory.content = prepared["content"]
    memory.owner_companion_id = memory.owner_companion_id or memory.companion_id
    memory.memory_scope_type = memory.memory_scope_type or "private_companion"
    memory.memory_layer = memory.memory_layer or "companion_private"
    memory.content_revision = 1
    memory.content_hash = prepared["content_hash"]
    memory.embedding = prepared["embedding"]
    _initialize_lifecycle(memory)
    session.add(memory)
    session.flush()
    return _append_content_revision(
        session,
        memory,
        operation="created",
        reason=reason,
        embedding=prepared["embedding"],
        embedding_provider=prepared["embedding_provider"],
        embedding_model=prepared["embedding_model"],
        source_candidate_id=source_candidate_id,
    )


def _append_content_revision(
    session: Session,
    memory: Memory,
    *,
    operation: str,
    reason: str,
    embedding: list[float] | None,
    embedding_provider: str | None,
    embedding_model: str | None,
    source_candidate_id: uuid.UUID | None = None,
    restored_from_revision_id: uuid.UUID | None = None,
) -> MemoryContentRevision:
    revision = MemoryContentRevision(
        user_id=memory.user_id,
        companion_id=memory.companion_id,
        memory_id=memory.id,
        source_candidate_id=source_candidate_id,
        restored_from_revision_id=restored_from_revision_id,
        revision=memory.content_revision,
        content=memory.content,
        summary=memory.summary,
        content_hash=memory.content_hash or _content_hash(memory.content),
        operation=operation,
        reason=reason,
        embedding=embedding,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )
    session.add(revision)
    session.flush()
    return revision


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def _memory_snapshot(memory: Memory) -> dict:
    return {
        "state": memory.state,
        "memory_strength": round(float(memory.memory_strength or 0.0), 6),
        "confidence": round(float(memory.confidence or 0.0), 6),
        "confidence_prior_alpha": round(float(memory.confidence_prior_alpha or 2.0), 6),
        "confidence_prior_beta": round(float(memory.confidence_prior_beta or 2.0), 6),
        "confidence_alpha": round(float(memory.confidence_alpha or 2.0), 6),
        "confidence_beta": round(float(memory.confidence_beta or 2.0), 6),
        "half_life_days": round(float(memory.half_life_days or 0.0), 4),
        "reactivation_count": int(memory.reactivation_count or 0),
        "last_reactivated_at": memory.last_reactivated_at.isoformat() if memory.last_reactivated_at else None,
    }


def _refresh_half_life(memory: Memory) -> dict:
    half_life = calculate_personalized_half_life(
        memory.type,
        importance=memory.importance or 0.0,
        user_confirmed=(
            memory.consent_status == "user_confirmed"
            or (memory.positive_confirmations or 0) > 0
        ),
        reactivation_count=memory.reactivation_count or 0,
        goal_relevance=memory.goal_relevance or 0.0,
        relationship_impact=memory.relationship_impact or 0.0,
        base_half_life_days=memory.base_half_life_days,
    )
    memory.base_half_life_days = half_life["base_half_life_days"]
    memory.half_life_days = half_life["half_life_days"]
    memory.lifecycle_algorithm_version = MEMORY_LIFECYCLE_VERSION
    return half_life


def _initialize_lifecycle(memory: Memory, now: datetime | None = None) -> None:
    timestamp = now or datetime.now(timezone.utc)
    beta = compute_beta_confidence(
        positive_confirmations=memory.positive_confirmations or 0,
        helpful_count=memory.helpful_count or 0,
        accepted_count=memory.accepted_count or 0,
        irrelevant_count=memory.irrelevant_count or 0,
        outdated_count=memory.outdated_count or 0,
        wrong_count=memory.wrong_count or 0,
        rejected_count=memory.rejected_count or 0,
        prior_alpha=memory.confidence_prior_alpha or 2.0,
        prior_beta=memory.confidence_prior_beta or 2.0,
    )
    memory.confidence_alpha = beta["alpha"]
    memory.confidence_beta = beta["beta"]
    memory.confidence = beta["confidence"]
    memory.strength_anchor_at = memory.strength_anchor_at or timestamp
    _refresh_half_life(memory)


def _record_change(
    session: Session,
    memory: Memory,
    *,
    event_type: str,
    reason: str,
    before: dict,
    score_json: dict | None = None,
) -> None:
    record_memory_change(
        session,
        memory,
        event_type=event_type,
        reason=reason,
        before=before,
        after=_memory_snapshot(memory),
        score_json=score_json,
    )


# ── Memory CRUD ──────────────────────────────────────────────────────

def list_memories(companion_id: uuid.UUID | None = None, type_: str | None = None,
                  state: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    with get_session() as s:
        stmt = select(Memory).where(Memory.deleted_at.is_(None))
        if companion_id:
            stmt = stmt.where(Memory.companion_id == companion_id)
        if type_:
            stmt = stmt.where(Memory.type == type_)
        if state:
            stmt = stmt.where(Memory.state == state)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(Memory.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def get_memory(memory_id: uuid.UUID, companion_id: uuid.UUID | None = None) -> Memory | None:
    with get_session() as s:
        memory = s.get(Memory, memory_id)
        if memory is None or (companion_id is not None and memory.companion_id != companion_id):
            return None
        return memory


def create_memory(data: dict) -> Memory:
    content = str(data["content"]).strip()
    embedding, provider_name, model_name = _strict_embedding(content)
    with get_session() as s:
        companion = s.get(Companion, data["companion_id"])
        if companion is None or companion.deleted_at is not None or companion.user_id != data["user_id"]:
            raise ValueError("Memory owner/Companion scope is invalid")
        data = {
            **data,
            "content": content,
            "owner_companion_id": data["companion_id"],
            "memory_scope_type": "private_companion",
            "memory_layer": "companion_private",
            "content_revision": 1,
            "content_hash": _content_hash(content),
            "embedding": embedding,
        }
        m = Memory(**data)
        _initialize_lifecycle(m)
        s.add(m)
        s.flush()
        _append_content_revision(
            s, m,
            operation="created",
            reason="user_created_saved_memory",
            embedding=embedding,
            embedding_provider=provider_name,
            embedding_model=model_name,
        )
        s.commit()
        s.refresh(m)
        return m


def update_memory(memory_id: uuid.UUID, data: dict, companion_id: uuid.UUID | None = None) -> Memory | None:
    protected = {"content", "summary", "embedding", "content_revision", "content_hash"} & set(data)
    if protected:
        raise MemoryMutationError(
            "MEMORY_VERSIONED_UPDATE_REQUIRED",
            "Saved Memory content must change through a versioned correction, merge, or restore operation.",
            {"protected_fields": sorted(protected)},
        )
    with get_session() as s:
        m = s.get(Memory, memory_id)
        if not m or (companion_id is not None and m.companion_id != companion_id):
            return None
        for k, v in data.items():
            if v is not None and hasattr(m, k):
                setattr(m, k, v)
        m.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(m)
        return m


def delete_memory(memory_id: uuid.UUID, companion_id: uuid.UUID | None = None) -> Memory | None:
    """Soft delete."""
    with get_session() as s:
        m = s.get(Memory, memory_id)
        if not m or (companion_id is not None and m.companion_id != companion_id):
            return None
        before = _memory_snapshot(m)
        m.state = "deleted"
        m.deleted_at = datetime.now(timezone.utc)
        m.updated_at = datetime.now(timezone.utc)
        _record_change(
            s,
            m,
            event_type="deleted",
            reason="Explicit forget/delete request",
            before=before,
        )
        s.commit()
        s.refresh(m)
        return m


def lock_memory(memory_id: uuid.UUID, companion_id: uuid.UUID | None = None) -> Memory | None:
    with get_session() as s:
        m = s.get(Memory, memory_id)
        if not m or m.deleted_at is not None or (companion_id is not None and m.companion_id != companion_id):
            return None
        before = _memory_snapshot(m)
        now = datetime.now(timezone.utc)
        m.state = "active"
        m.consent_status = "user_confirmed"
        m.positive_confirmations = (m.positive_confirmations or 0) + 1
        reinforced = apply_reinforcement(m.memory_strength or 0.5, user_confirmed=True)
        m.memory_strength = reinforced["new_strength"]
        beta = compute_beta_confidence(
            positive_confirmations=m.positive_confirmations or 0,
            helpful_count=m.helpful_count or 0,
            accepted_count=m.accepted_count or 0,
            irrelevant_count=m.irrelevant_count or 0,
            outdated_count=m.outdated_count or 0,
            wrong_count=m.wrong_count or 0,
            rejected_count=m.rejected_count or 0,
            prior_alpha=m.confidence_prior_alpha or 2.0,
            prior_beta=m.confidence_prior_beta or 2.0,
        )
        m.confidence_alpha = beta["alpha"]
        m.confidence_beta = beta["beta"]
        m.confidence = beta["confidence"]
        half_life = _refresh_half_life(m)
        m.strength_anchor_at = now
        m.updated_at = now
        _record_change(
            s,
            m,
            event_type="locked",
            reason="User confirmed and locked memory",
            before=before,
            score_json={"reinforcement": reinforced, "beta_confidence": beta, "half_life": half_life},
        )
        s.commit()
        s.refresh(m)
        return m


def fade_memory(memory_id: uuid.UUID, strength_delta: float = 0.2, companion_id: uuid.UUID | None = None) -> Memory | None:
    with get_session() as s:
        m = s.get(Memory, memory_id)
        if not m or m.deleted_at is not None or (companion_id is not None and m.companion_id != companion_id):
            return None
        before = _memory_snapshot(m)
        now = datetime.now(timezone.utc)
        m.memory_strength = max(0.0, (m.memory_strength or 0.5) - strength_delta)
        m.state = determine_state_from_strength(m.memory_strength, m.state, m.type)
        m.strength_anchor_at = now
        m.updated_at = now
        _record_change(
            s,
            m,
            event_type="faded",
            reason="Explicit user fade request",
            before=before,
            score_json={"requested_strength_delta": strength_delta},
        )
        s.commit()
        s.refresh(m)
        return m


def archive_memory(memory_id: uuid.UUID, companion_id: uuid.UUID | None = None) -> Memory | None:
    with get_session() as s:
        m = s.get(Memory, memory_id)
        if not m or m.deleted_at is not None or (companion_id is not None and m.companion_id != companion_id):
            return None
        before = _memory_snapshot(m)
        m.state = "archived"
        m.updated_at = datetime.now(timezone.utc)
        _record_change(
            s,
            m,
            event_type="archived",
            reason="Explicit user archive request",
            before=before,
        )
        s.commit()
        s.refresh(m)
        return m


def reactivate_memory(memory_id: uuid.UUID, companion_id: uuid.UUID | None = None) -> Memory | None:
    with get_session() as s:
        m = s.get(Memory, memory_id)
        if not m or (companion_id is not None and m.companion_id != companion_id):
            return None
        before = _memory_snapshot(m)
        now = datetime.now(timezone.utc)
        m.state = "active"
        m.deleted_at = None
        m.reactivation_count = (m.reactivation_count or 0) + 1
        m.last_reactivated_at = now
        reinforced = apply_reinforcement(m.memory_strength or 0.5, successful_recall=True)
        m.memory_strength = reinforced["new_strength"]
        half_life = _refresh_half_life(m)
        m.strength_anchor_at = now
        m.updated_at = now
        _record_change(
            s,
            m,
            event_type="reactivated",
            reason="Memory was explicitly reactivated",
            before=before,
            score_json={"reinforcement": reinforced, "half_life": half_life},
        )
        s.commit()
        s.refresh(m)
        return m


def correct_memory(
    memory_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    content: str,
    summary: str | None,
    reason: str,
    expected_revision: int,
) -> Memory | None:
    """Append a correction revision and atomically replace text plus real embedding."""
    normalized_content = content.strip()
    embedding, provider_name, model_name = _strict_embedding(normalized_content)
    with get_session() as s:
        m = s.execute(
            select(Memory).where(Memory.id == memory_id).with_for_update()
        ).scalar_one_or_none()
        if m is None or m.deleted_at is not None or m.companion_id != companion_id:
            return None
        if int(m.content_revision or 1) != expected_revision:
            raise MemoryMutationError(
                "MEMORY_REVISION_CONFLICT",
                "Saved Memory changed after it was loaded.",
                {"expected_revision": expected_revision, "current_revision": m.content_revision},
            )
        if _content_hash(normalized_content) == (m.content_hash or _content_hash(m.content)) and summary == m.summary:
            raise MemoryMutationError("MEMORY_CONTENT_UNCHANGED", "The correction does not change this Saved Memory.")
        before = _memory_snapshot(m)
        metadata = dict(m.metadata_ or {})
        corrections = list(metadata.get("content_corrections") or [])
        corrections.append({
            "previous_content": m.content,
            "previous_summary": m.summary,
            "reason": reason,
            "corrected_at": datetime.now(timezone.utc).isoformat(),
        })
        metadata["content_corrections"] = corrections
        m.metadata_ = metadata
        m.content = normalized_content
        m.summary = summary
        m.content_revision = int(m.content_revision or 1) + 1
        m.content_hash = _content_hash(normalized_content)
        m.embedding = embedding
        m.updated_at = datetime.now(timezone.utc)
        revision = _append_content_revision(
            s, m,
            operation="corrected",
            reason=reason,
            embedding=embedding,
            embedding_provider=provider_name,
            embedding_model=model_name,
        )
        _record_change(
            s,
            m,
            event_type="content_corrected",
            reason=reason,
            before=before,
            score_json={"content_changed": True, "content_revision_id": str(revision.id), "content_revision": m.content_revision},
        )
        s.commit()
        s.refresh(m)
        return m


def list_memory_content_revisions(
    memory_id: uuid.UUID,
    companion_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    with get_session() as s:
        memory = s.get(Memory, memory_id)
        if memory is None or memory.companion_id != companion_id:
            return {"items": [], "total": 0, "memory": None}
        stmt = select(MemoryContentRevision).where(
            MemoryContentRevision.memory_id == memory_id,
            MemoryContentRevision.companion_id == companion_id,
        )
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        rows = list(s.execute(
            stmt.order_by(MemoryContentRevision.revision.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).scalars())
        return {"items": [_revision_dict(row) for row in rows], "total": total, "memory": _mem_dict(memory)}


def restore_memory_content_revision(
    memory_id: uuid.UUID,
    revision_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    expected_revision: int,
    reason: str,
) -> Memory:
    with get_session() as s:
        source = s.get(MemoryContentRevision, revision_id)
        if source is None or source.memory_id != memory_id or source.companion_id != companion_id:
            raise MemoryMutationError("MEMORY_REVISION_NOT_FOUND", "Saved Memory revision not found.")
        source_content = source.content
        source_summary = source.summary
    restored_embedding, restored_provider, restored_model = _strict_embedding(source_content)

    with get_session() as s:
        memory = s.execute(select(Memory).where(Memory.id == memory_id).with_for_update()).scalar_one_or_none()
        if memory is None or memory.deleted_at is not None or memory.companion_id != companion_id:
            raise MemoryMutationError("MEMORY_NOT_FOUND", "Saved Memory not found.")
        if int(memory.content_revision or 1) != expected_revision:
            raise MemoryMutationError(
                "MEMORY_REVISION_CONFLICT", "Saved Memory changed after it was loaded.",
                {"expected_revision": expected_revision, "current_revision": memory.content_revision},
            )
        before = _memory_snapshot(memory)
        memory.content = source_content
        memory.summary = source_summary
        memory.content_revision = int(memory.content_revision or 1) + 1
        memory.content_hash = _content_hash(source_content)
        memory.embedding = restored_embedding
        memory.updated_at = datetime.now(timezone.utc)
        revision = _append_content_revision(
            s, memory,
            operation="restored",
            reason=reason,
            embedding=restored_embedding,
            embedding_provider=restored_provider,
            embedding_model=restored_model,
            restored_from_revision_id=revision_id,
        )
        _record_change(
            s, memory, event_type="content_restored", reason=reason, before=before,
            score_json={"content_revision_id": str(revision.id), "restored_from_revision_id": str(revision_id)},
        )
        s.commit()
        s.refresh(memory)
        return memory


# ── Memory Candidate ─────────────────────────────────────────────────

def list_memory_candidates(companion_id: uuid.UUID | None = None, status: str | None = None,
                           page: int = 1, page_size: int = 20) -> dict:
    with get_session() as s:
        stmt = select(MemoryCandidate)
        if companion_id:
            stmt = stmt.where(MemoryCandidate.companion_id == companion_id)
        if status:
            stmt = stmt.where(MemoryCandidate.status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(MemoryCandidate.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def get_memory_candidate(candidate_id: uuid.UUID) -> MemoryCandidate | None:
    with get_session() as s:
        return s.get(MemoryCandidate, candidate_id)


def accept_memory_candidate(candidate_id: uuid.UUID) -> dict | None:
    """Accept candidate content — does NOT create Memory.

    Only changes status to 'accepted'. User must call commit_memory_candidate
    to actually create a Memory record.
    """
    with get_session() as s:
        cand = s.get(MemoryCandidate, candidate_id)
        if not cand or cand.status not in ("pending",):
            return None
        cand.status = "accepted"
        cand.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(cand)
        return {"candidate": _cand_dict(cand)}


def commit_memory_candidate(candidate_id: uuid.UUID, user_id: uuid.UUID,
                            companion_id: uuid.UUID) -> dict | None:
    """Commit accepted candidate → create Memory record.

    Only works on candidates with status 'accepted'. Idempotent:
    if already committed, returns existing Memory.
    """
    with get_session() as s:
        candidate = s.get(MemoryCandidate, candidate_id)
        if not candidate or candidate.status not in ("accepted",):
            return None
        candidate_content = candidate.content
    embedding, provider_name, model_name = _strict_embedding(candidate_content)

    with get_session() as s:
        cand = s.execute(select(MemoryCandidate).where(MemoryCandidate.id == candidate_id).with_for_update()).scalar_one_or_none()
        if not cand or cand.status not in ("accepted",):
            if cand and cand.accepted_memory_id:
                existing = s.get(Memory, cand.accepted_memory_id)
                if existing:
                    return {"candidate": _cand_dict(cand), "memory": _mem_dict(existing)}
            return None
        if cand.user_id != user_id or cand.companion_id != companion_id or cand.proposed_owner_companion_id != companion_id:
            raise MemoryMutationError("MEMORY_SCOPE_MISMATCH", "Memory candidate scope does not match the requested Companion.")
        mem = Memory(
            user_id=user_id,
            companion_id=companion_id,
            owner_companion_id=companion_id,
            conversation_id=cand.conversation_id,
            memory_scope_type="private_companion",
            memory_layer="companion_private",
            type=cand.suggested_type,
            content=cand.content,
            summary=cand.suggested_summary or cand.content[:200],
            source_message_ids=cand.source_message_ids or [],
            importance=cand.importance,
            confidence=cand.confidence,
            emotional_intensity=cand.emotional_intensity,
            goal_relevance=cand.goal_relevance,
            relationship_impact=cand.relationship_impact,
            correction_value=cand.correction_value,
            memory_strength=max(0.5, cand.score or 0.5),
            state="active",
            consent_status="user_confirmed",
            positive_confirmations=1,
            content_revision=1,
            content_hash=_content_hash(cand.content),
            embedding=embedding,
        )
        _initialize_lifecycle(mem)
        s.add(mem)
        s.flush()
        _append_content_revision(
            s, mem,
            operation="created",
            reason="user_committed_memory_candidate",
            embedding=embedding,
            embedding_provider=provider_name,
            embedding_model=model_name,
            source_candidate_id=cand.id,
        )
        cand.status = "committed"
        cand.accepted_memory_id = mem.id
        cand.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(cand)
        s.refresh(mem)
        return {"candidate": _cand_dict(cand), "memory": _mem_dict(mem)}


def auto_commit_low_risk_memory_candidate(
    candidate_id: uuid.UUID,
    *,
    companion_id: uuid.UUID,
    governance_evidence: dict,
) -> dict:
    """Commit a validated private candidate with strict embedding and row locking."""
    with get_session() as s:
        candidate = s.get(MemoryCandidate, candidate_id)
        if not _is_low_risk_private_candidate(candidate, companion_id):
            return {"outcome": "manual_review", "reason": _eligibility_reason(candidate)}
        candidate_content = candidate.content

    try:
        embedding_provider = get_embedding_provider()
        embedding = embedding_provider.embed_strict(candidate_content)[0]
    except Exception as exc:
        return {
            "outcome": "manual_review",
            "reason": "strict_embedding_unavailable",
            "error_type": type(exc).__name__,
        }

    with get_session() as s:
        cand = s.execute(
            select(MemoryCandidate)
            .where(MemoryCandidate.id == candidate_id)
            .with_for_update()
        ).scalar_one_or_none()
        if cand is not None and cand.status == "committed" and cand.accepted_memory_id:
            existing = s.get(Memory, cand.accepted_memory_id)
            if existing is not None:
                return {
                    "outcome": "already_committed",
                    "reason": "candidate_was_committed_concurrently",
                    "candidate": _cand_dict(cand),
                    "memory": _mem_dict(existing),
                }
        if not _is_low_risk_private_candidate(cand, companion_id):
            return {"outcome": "manual_review", "reason": _eligibility_reason(cand)}

        companion = s.get(Companion, companion_id)
        if companion is None or companion.deleted_at is not None or companion.user_id != cand.user_id:
            return {"outcome": "manual_review", "reason": "owner_companion_scope_invalid"}

        conflict = _find_private_memory_conflict(s, cand, companion_id)
        if conflict["status"] == "potential_conflict":
            cand.score_json = {
                **(cand.score_json or {}),
                "persistence_validation": conflict,
            }
            cand.updated_at = datetime.now(timezone.utc)
            s.commit()
            return {"outcome": "manual_review", "reason": "potential_memory_conflict"}
        if conflict["status"] == "exact_duplicate":
            existing = conflict["memory"]
            cand.status = "committed"
            cand.needs_user_confirmation = False
            cand.accepted_memory_id = existing.id
            cand.score_json = {
                **(cand.score_json or {}),
                "governance": {
                    **governance_evidence,
                    "decision": "deduplicate_existing_private_memory",
                },
                "persistence_validation": {
                    "status": "exact_duplicate",
                    "existing_memory_id": str(existing.id),
                },
            }
            cand.updated_at = datetime.now(timezone.utc)
            s.commit()
            s.refresh(cand)
            return {
                "outcome": "deduplicated",
                "reason": "exact_private_memory_already_exists",
                "candidate": _cand_dict(cand),
                "memory": _mem_dict(existing),
            }

        mem = Memory(
            user_id=cand.user_id,
            companion_id=companion_id,
            owner_companion_id=companion_id,
            conversation_id=cand.conversation_id,
            memory_scope_type="private_companion",
            memory_layer="companion_private",
            type=cand.suggested_type,
            content=cand.content,
            summary=cand.suggested_summary or cand.content[:200],
            source_message_ids=cand.source_message_ids or [],
            importance=cand.importance,
            confidence=cand.confidence,
            emotional_intensity=cand.emotional_intensity,
            goal_relevance=cand.goal_relevance,
            relationship_impact=cand.relationship_impact,
            correction_value=cand.correction_value,
            memory_strength=max(0.5, cand.score or 0.5),
            state="active",
            consent_status="auto",
            positive_confirmations=0,
            content_revision=1,
            content_hash=_content_hash(cand.content),
            metadata_={
                "governance": {
                    **governance_evidence,
                    "decision": "auto_commit_low_risk_private",
                }
            },
        )
        _initialize_lifecycle(mem)
        mem.embedding = embedding
        s.add(mem)
        s.flush()
        _append_content_revision(
            s, mem,
            operation="created",
            reason="governance_auto_commit_low_risk_private",
            embedding=embedding,
            embedding_provider=getattr(embedding_provider, "provider_name", "configured_embedding_provider"),
            embedding_model=settings.EMBEDDING_MODEL or None,
            source_candidate_id=cand.id,
        )
        cand.status = "committed"
        cand.needs_user_confirmation = False
        cand.accepted_memory_id = mem.id
        cand.score_json = {
            **(cand.score_json or {}),
            "governance": {
                **governance_evidence,
                "decision": "auto_commit_low_risk_private",
            },
        }
        cand.updated_at = datetime.now(timezone.utc)
        lifecycle = create_memory_lifecycle_event_in_session(s, {
            "user_id": mem.user_id,
            "companion_id": mem.companion_id,
            "conversation_id": mem.conversation_id,
            "memory_id": mem.id,
            "source_candidate_id": cand.id,
            "event_type": "created",
            "reason": "governance_auto_commit_low_risk_private",
            "new_state": mem.state,
            "new_strength": mem.memory_strength,
            "new_confidence": mem.confidence,
            "new_half_life_days": mem.half_life_days,
            "score_json": cand.score_json,
            "after_json": _memory_snapshot(mem),
            "metadata": {"governance": governance_evidence},
        })
        cand.lifecycle_event_id = lifecycle.id
        s.commit()
        s.refresh(cand)
        s.refresh(mem)
        return {
            "outcome": "committed",
            "reason": "validated_low_risk_private_memory",
            "candidate": _cand_dict(cand),
            "memory": _mem_dict(mem),
            "lifecycle_event_id": str(lifecycle.id),
        }


def _is_low_risk_private_candidate(cand: MemoryCandidate | None, companion_id: uuid.UUID) -> bool:
    validation = (
        (cand.score_json or {}).get("independent_validation", {})
        if cand is not None
        else {}
    )
    return bool(
        cand is not None
        and cand.companion_id == companion_id
        and cand.proposed_owner_companion_id == companion_id
        and cand.status == "pending"
        and cand.proposed_shared_memory_id is None
        and not bool(cand.requires_companion_memory_review)
        and cand.suggested_type not in {"correction", "relationship", "shared", "channel"}
        and validation.get("eligible_before_persistence_checks") is True
        and validation.get("source_grounded") is True
        and float(cand.sensitivity_risk or 0.0) <= 0.15
        and float(cand.relationship_impact or 0.0) <= 0.35
        and float(validation.get("sensitivity_risk") or 1.0) <= 0.15
        and float(validation.get("relationship_impact") or 1.0) <= 0.35
        and float(cand.correction_value or 0.0) <= 0.20
        and float(cand.emotional_intensity or 0.0) <= 0.65
        and float(cand.score or 0.0) >= 0.55
        and float(cand.confidence or 0.0) >= 0.82
    )


def _eligibility_reason(cand: MemoryCandidate | None) -> str:
    if cand is None:
        return "candidate_not_found"
    validation = (cand.score_json or {}).get("independent_validation")
    if not isinstance(validation, dict):
        return "independent_validation_missing"
    reasons = validation.get("reasons")
    if isinstance(reasons, list) and reasons:
        return str(reasons[0])
    if cand.status != "pending":
        return "candidate_not_pending"
    if float(cand.score or 0.0) < 0.55:
        return "algorithm_score_below_threshold"
    return "candidate_not_eligible"


def _find_private_memory_conflict(
    session: Session,
    cand: MemoryCandidate,
    companion_id: uuid.UUID,
) -> dict:
    memories = list(session.execute(
        select(Memory)
        .where(
            Memory.owner_companion_id == companion_id,
            Memory.memory_scope_type.in_(("legacy_private", "private_companion")),
            Memory.state == "active",
            Memory.deleted_at.is_(None),
        )
        .order_by(Memory.updated_at.desc())
        .limit(200)
    ).scalars())
    normalized = _normalize_memory_text(cand.content)
    for memory in memories:
        existing = _normalize_memory_text(memory.content)
        if normalized and normalized == existing:
            return {"status": "exact_duplicate", "memory": memory}
        if memory.type == cand.suggested_type and _character_ngram_similarity(normalized, existing) >= 0.50:
            return {
                "status": "potential_conflict",
                "existing_memory_id": str(memory.id),
                "similarity_threshold": 0.50,
            }
    return {"status": "clear"}


def _normalize_memory_text(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (value or "").lower())


def _character_ngram_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if len(left) < 2 or len(right) < 2:
        return 1.0 if left == right else 0.0
    left_pairs = {left[index:index + 2] for index in range(len(left) - 1)}
    right_pairs = {right[index:index + 2] for index in range(len(right) - 1)}
    union = left_pairs | right_pairs
    return len(left_pairs & right_pairs) / len(union) if union else 0.0


def edit_memory_candidate(candidate_id: uuid.UUID, content: str | None = None,
                          summary: str | None = None, type_: str | None = None,
                          accept_after_edit: bool = False, user_id: uuid.UUID | None = None,
                          companion_id: uuid.UUID | None = None) -> dict | None:
    embedding_bundle = None
    if accept_after_edit:
        with get_session() as read_session:
            source_candidate = read_session.get(MemoryCandidate, candidate_id)
            if source_candidate is None:
                return None
            embedding_bundle = _strict_embedding(content if content is not None else source_candidate.content)
    with get_session() as s:
        cand = s.get(MemoryCandidate, candidate_id)
        if not cand or cand.status not in ("pending",):
            return None
        if content is not None:
            cand.content = content
            cand.edited_content = content
        if summary is not None:
            cand.suggested_summary = summary
        if type_ is not None:
            cand.suggested_type = type_
        if accept_after_edit and user_id and companion_id:
            final_content = cand.content
            embedding, provider_name, model_name = embedding_bundle
            mem = Memory(
                user_id=user_id, companion_id=companion_id, conversation_id=cand.conversation_id,
                owner_companion_id=companion_id, memory_scope_type="private_companion", memory_layer="companion_private",
                type=cand.suggested_type, content=cand.content,
                summary=cand.suggested_summary or cand.content[:200],
                importance=cand.importance, confidence=cand.confidence,
                memory_strength=max(0.5, cand.score or 0.5),
                state="active", consent_status="user_confirmed", positive_confirmations=1,
                content_revision=1, content_hash=_content_hash(final_content), embedding=embedding,
            )
            _initialize_lifecycle(mem)
            s.add(mem)
            s.flush()
            _append_content_revision(
                s, mem, operation="created", reason="user_edited_and_committed_memory_candidate",
                embedding=embedding, embedding_provider=provider_name, embedding_model=model_name,
                source_candidate_id=cand.id,
            )
            cand.status = "edited"
            cand.accepted_memory_id = mem.id
            s.commit()
            s.refresh(cand)
            s.refresh(mem)
            return {"candidate": _cand_dict(cand), "memory": _mem_dict(mem)}
        cand.status = "edited"
        cand.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(cand)
        return {"candidate": _cand_dict(cand), "memory": None}


def reject_memory_candidate(candidate_id: uuid.UUID, reason: str | None = None) -> MemoryCandidate | None:
    with get_session() as s:
        cand = s.get(MemoryCandidate, candidate_id)
        if not cand:
            return None
        cand.status = "rejected"
        cand.feedback_label = "negative"
        cand.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(cand)
        return cand


def merge_memory_candidate(
    candidate_id: uuid.UUID,
    target_memory_id: uuid.UUID,
    *,
    companion_id: uuid.UUID,
    expected_revision: int,
    merged_content: str,
    reason: str,
) -> dict | None:
    normalized_content = merged_content.strip()
    embedding, provider_name, model_name = _strict_embedding(normalized_content)
    with get_session() as s:
        cand = s.execute(select(MemoryCandidate).where(MemoryCandidate.id == candidate_id).with_for_update()).scalar_one_or_none()
        target = s.execute(select(Memory).where(Memory.id == target_memory_id).with_for_update()).scalar_one_or_none()
        if not cand or not target or target.deleted_at is not None:
            return None
        if cand.status not in {"pending", "accepted"}:
            raise MemoryMutationError("INVALID_STATE_TRANSITION", "Only a pending or accepted candidate can be merged.")
        if cand.companion_id != companion_id or target.companion_id != companion_id or target.owner_companion_id != companion_id:
            raise MemoryMutationError("MEMORY_SCOPE_MISMATCH", "Candidate and Saved Memory must belong to the same Companion.")
        if int(target.content_revision or 1) != expected_revision:
            raise MemoryMutationError(
                "MEMORY_REVISION_CONFLICT", "Saved Memory changed after it was loaded.",
                {"expected_revision": expected_revision, "current_revision": target.content_revision},
            )
        before = _memory_snapshot(target)
        target.content = normalized_content
        target.summary = target.summary or normalized_content[:200]
        target.content_revision = int(target.content_revision or 1) + 1
        target.content_hash = _content_hash(normalized_content)
        target.embedding = embedding
        target.updated_at = datetime.now(timezone.utc)
        revision = _append_content_revision(
            s, target, operation="merged", reason=reason,
            embedding=embedding, embedding_provider=provider_name, embedding_model=model_name,
            source_candidate_id=cand.id,
        )
        cand.status = "merged"
        cand.accepted_memory_id = target.id
        cand.updated_at = datetime.now(timezone.utc)
        _record_change(
            s, target, event_type="content_merged", reason=reason, before=before,
            score_json={"content_revision_id": str(revision.id), "source_candidate_id": str(cand.id)},
        )
        s.commit()
        s.refresh(cand)
        s.refresh(target)
        return {"candidate": _cand_dict(cand), "memory": _mem_dict(target), "revision": _revision_dict(revision)}


# ── Serialization ────────────────────────────────────────────────────

def _mem_dict(m: Memory) -> dict:
    return {
        "id": str(m.id), "companion_id": str(m.companion_id), "type": m.type, "state": m.state,
        "content": m.content, "summary": m.summary,
        "content_revision": m.content_revision or 1,
        "content_hash": m.content_hash,
        "importance": m.importance, "confidence": m.confidence,
        "memory_strength": m.memory_strength,
        "half_life_days": m.half_life_days,
        "base_half_life_days": m.base_half_life_days,
        "confidence_prior_alpha": m.confidence_prior_alpha,
        "confidence_prior_beta": m.confidence_prior_beta,
        "confidence_alpha": m.confidence_alpha,
        "confidence_beta": m.confidence_beta,
        "reactivation_count": m.reactivation_count or 0,
        "last_reactivated_at": m.last_reactivated_at.isoformat() if m.last_reactivated_at else None,
        "last_maintenance_at": m.last_maintenance_at.isoformat() if m.last_maintenance_at else None,
        "lifecycle_algorithm_version": m.lifecycle_algorithm_version,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _revision_dict(row: MemoryContentRevision) -> dict:
    return {
        "id": str(row.id),
        "memory_id": str(row.memory_id),
        "companion_id": str(row.companion_id),
        "revision": row.revision,
        "content": row.content,
        "summary": row.summary,
        "content_hash": row.content_hash,
        "operation": row.operation,
        "reason": row.reason,
        "source_candidate_id": str(row.source_candidate_id) if row.source_candidate_id else None,
        "restored_from_revision_id": str(row.restored_from_revision_id) if row.restored_from_revision_id else None,
        "embedding_provider": row.embedding_provider,
        "embedding_model": row.embedding_model,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _cand_dict(c: MemoryCandidate) -> dict:
    return {
        "id": str(c.id), "content": c.content,
        "suggested_type": c.suggested_type, "score": c.score,
        "status": c.status,
        "accepted_memory_id": str(c.accepted_memory_id) if c.accepted_memory_id else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
