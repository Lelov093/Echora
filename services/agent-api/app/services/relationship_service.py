"""Evidence-gated, versioned Relationship truth service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Companion,
    Memory,
    Message,
    RelationshipCandidate,
    RelationshipEvent,
    RelationshipExplanationEvent,
    RelationshipState,
    RelationshipStateRevision,
)
from app.relationship.belief import (
    ALGORITHM_VERSION,
    DIMENSIONS,
    initial_beliefs,
    summarize_beliefs,
    update_belief,
    validate_signals,
)


_engine = None


class RelationshipMutationError(Exception):
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


def get_relationship_state(companion_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        state = session.execute(
            select(RelationshipState).where(RelationshipState.companion_id == companion_id)
        ).scalar_one_or_none()
        return _state_dict(state) if state else None


def list_relationship_events(
    companion_id: uuid.UUID | None = None,
    dimension: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    with get_session() as session:
        stmt = select(RelationshipEvent)
        if companion_id:
            stmt = stmt.where(RelationshipEvent.companion_id == companion_id)
        if dimension:
            stmt = stmt.where(RelationshipEvent.dimension == dimension)
        total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        rows = list(session.execute(
            stmt.order_by(RelationshipEvent.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).scalars())
        return {"items": rows, "total": total}


def list_relationship_candidates(
    companion_id: uuid.UUID,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    with get_session() as session:
        stmt = select(RelationshipCandidate).where(RelationshipCandidate.companion_id == companion_id)
        if status:
            stmt = stmt.where(RelationshipCandidate.status == status)
        total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        rows = list(session.execute(
            stmt.order_by(RelationshipCandidate.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).scalars())
        return {"items": [_candidate_dict(row) for row in rows], "total": total}


def list_relationship_revisions(
    companion_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    with get_session() as session:
        stmt = select(RelationshipStateRevision).where(
            RelationshipStateRevision.companion_id == companion_id
        )
        total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        rows = list(session.execute(
            stmt.order_by(RelationshipStateRevision.revision.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).scalars())
        return {"items": [_revision_dict(row) for row in rows], "total": total}


def create_relationship_candidate(data: dict[str, Any]) -> dict:
    signals = validate_signals(list(data.get("dimension_signals") or []))
    validation = dict(data.get("validation") or {})
    if validation.get("status") != "passed":
        raise RelationshipMutationError(
            "RELATIONSHIP_EVIDENCE_NOT_VALIDATED",
            "Relationship candidate evidence must pass independent validation.",
            {"status": validation.get("status")},
        )
    source_message_ids = _uuid_list(data.get("source_message_ids"))
    source_memory_ids = _uuid_list(data.get("source_memory_ids"))
    with get_session() as session:
        companion = session.get(Companion, data["companion_id"])
        if companion is None or companion.deleted_at is not None or companion.user_id != data["user_id"]:
            raise RelationshipMutationError("RELATIONSHIP_SCOPE_MISMATCH", "Companion scope does not match candidate owner.")
        _validate_sources(
            session,
            companion.id,
            source_message_ids,
            source_memory_ids,
            conversation_id=_optional_uuid(data.get("conversation_id")),
            evidence_quotes=list(data.get("evidence_quotes") or []),
        )
        existing = session.execute(select(RelationshipCandidate).where(
            RelationshipCandidate.idempotency_key == data["idempotency_key"]
        )).scalar_one_or_none()
        if existing:
            return _candidate_dict(existing)
        state = session.execute(select(RelationshipState).where(
            RelationshipState.user_id == companion.user_id,
            RelationshipState.companion_id == companion.id,
        )).scalar_one_or_none()
        candidate = RelationshipCandidate(
            user_id=companion.user_id,
            companion_id=companion.id,
            conversation_id=data.get("conversation_id"),
            trace_run_id=data.get("trace_run_id"),
            status="pending",
            summary=str(data["summary"]).strip(),
            dimension_signals_json=signals,
            source_message_ids=source_message_ids,
            source_memory_ids=source_memory_ids,
            evidence_quotes_json=list(data.get("evidence_quotes") or []),
            extraction_json=dict(data.get("extraction") or {}),
            validation_json=validation,
            evidence_score=_unit(validation.get("evidence_score")),
            confidence=_unit(validation.get("confidence")),
            risk_level=str(validation.get("risk_level") or "medium"),
            requires_user_review=True,
            expected_state_revision=int(state.revision if state else 0),
            provider_name=data.get("provider_name"),
            model_name=data.get("model_name"),
            algorithm_version=ALGORITHM_VERSION,
            idempotency_key=str(data["idempotency_key"]),
            expires_at=data.get("expires_at"),
        )
        session.add(candidate)
        session.commit()
        session.refresh(candidate)
        return _candidate_dict(candidate)


def commit_relationship_candidate(
    candidate_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    expected_revision: int,
    reason: str,
) -> dict:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        candidate = session.execute(select(RelationshipCandidate).where(
            RelationshipCandidate.id == candidate_id,
            RelationshipCandidate.companion_id == companion_id,
        ).with_for_update()).scalar_one_or_none()
        if candidate is None:
            raise RelationshipMutationError("RELATIONSHIP_CANDIDATE_NOT_FOUND", "Relationship candidate not found.")
        if candidate.status == "committed" and candidate.committed_revision_id:
            revision = session.get(RelationshipStateRevision, candidate.committed_revision_id)
            state = session.get(RelationshipState, revision.relationship_state_id) if revision else None
            return {"candidate": _candidate_dict(candidate), "state": _state_dict(state), "revision": _revision_dict(revision)}
        if candidate.status != "pending":
            raise RelationshipMutationError("RELATIONSHIP_CANDIDATE_NOT_PENDING", "Only a pending candidate can be committed.")
        if candidate.expires_at and candidate.expires_at <= now:
            candidate.status = "expired"
            session.commit()
            raise RelationshipMutationError("RELATIONSHIP_CANDIDATE_EXPIRED", "Relationship candidate has expired.")
        state = session.execute(select(RelationshipState).where(
            RelationshipState.user_id == candidate.user_id,
            RelationshipState.companion_id == candidate.companion_id,
        ).with_for_update()).scalar_one_or_none()
        if state is None:
            state = _new_state(candidate.user_id, candidate.companion_id, now)
            session.add(state)
            session.flush()
        if state.revision != expected_revision or candidate.expected_state_revision != expected_revision:
            raise RelationshipMutationError(
                "RELATIONSHIP_REVISION_CONFLICT",
                "Relationship state changed after this candidate was loaded.",
                {"expected_revision": expected_revision, "current_revision": state.revision},
            )
        before = _state_snapshot(state)
        belief_before = dict(state.belief_state_json or initial_beliefs(now))
        belief_after = {key: dict(value) for key, value in belief_before.items()}
        event_details = []
        for signal in validate_signals(list(candidate.dimension_signals_json or [])):
            dimension = signal["dimension"]
            previous = float(getattr(state, dimension))
            updated_belief, stats = update_belief(belief_after[dimension], signal, now=now)
            belief_after[dimension] = updated_belief
            value = stats["mean"]
            setattr(state, dimension, value)
            setattr(state, f"{dimension}_trend", value - previous)
            event_details.append((signal, previous, value, stats))
        state.revision += 1
        state.belief_state_json = belief_after
        state.summary = candidate.summary
        state.last_evidence_at = now
        state.last_changed_at = now
        state.updated_at = now
        after = _state_snapshot(state)
        revision = RelationshipStateRevision(
            user_id=state.user_id,
            companion_id=state.companion_id,
            relationship_state_id=state.id,
            source_candidate_id=candidate.id,
            previous_revision_id=state.current_revision_id,
            revision=state.revision,
            operation="committed",
            reason=reason,
            snapshot_before_json=before,
            snapshot_after_json=after,
            belief_before_json=belief_before,
            belief_after_json=belief_after,
            algorithm_version=ALGORITHM_VERSION,
        )
        session.add(revision)
        session.flush()
        event_group_id = uuid.uuid4()
        explanation_ids = []
        for signal, previous, value, stats in event_details:
            event = RelationshipEvent(
                user_id=state.user_id,
                companion_id=state.companion_id,
                conversation_id=candidate.conversation_id,
                trace_run_id=candidate.trace_run_id,
                dimension=signal["dimension"],
                delta=value - previous,
                previous_value=previous,
                new_value=value,
                reason=candidate.summary,
                source_memory_ids=candidate.source_memory_ids or [],
                source_message_ids=candidate.source_message_ids or [],
                candidate_id=candidate.id,
                state_revision_id=revision.id,
                event_group_id=event_group_id,
                operation="committed",
                evidence_weight=stats["weight"],
                posterior_variance=stats["variance"],
                metadata_={"algorithm_version": ALGORITHM_VERSION, "signal": signal},
            )
            session.add(event)
            session.flush()
            explanation = _explanation_for_event(event, candidate, stats)
            session.add(explanation)
            session.flush()
            explanation_ids.append(explanation.id)
        state.current_revision_id = revision.id
        state.last_explanation_event_id = explanation_ids[-1] if explanation_ids else None
        state.explanation_summary = {
            "revision": revision.revision,
            "explanation_ids": [str(value) for value in explanation_ids],
            "candidate_id": str(candidate.id),
        }
        candidate.status = "committed"
        candidate.committed_revision_id = revision.id
        candidate.reviewed_at = now
        candidate.review_reason = reason
        candidate.updated_at = now
        session.commit()
        session.refresh(state)
        session.refresh(revision)
        return {"candidate": _candidate_dict(candidate), "state": _state_dict(state), "revision": _revision_dict(revision)}


def reject_relationship_candidate(
    candidate_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    reason: str,
) -> dict:
    with get_session() as session:
        candidate = session.execute(select(RelationshipCandidate).where(
            RelationshipCandidate.id == candidate_id,
            RelationshipCandidate.companion_id == companion_id,
        ).with_for_update()).scalar_one_or_none()
        if candidate is None:
            raise RelationshipMutationError("RELATIONSHIP_CANDIDATE_NOT_FOUND", "Relationship candidate not found.")
        if candidate.status not in {"pending", "rejected"}:
            raise RelationshipMutationError("RELATIONSHIP_CANDIDATE_NOT_PENDING", "Committed candidates must be corrected through a compensating revision.")
        candidate.status = "rejected"
        candidate.review_reason = reason
        candidate.reviewed_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(candidate)
        return _candidate_dict(candidate)


def correct_relationship_revision(
    revision_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    expected_revision: int,
    reason: str,
) -> dict:
    """Append a compensating revision that restores the source revision's before-state."""
    now = datetime.now(timezone.utc)
    with get_session() as session:
        source = session.execute(select(RelationshipStateRevision).where(
            RelationshipStateRevision.id == revision_id,
            RelationshipStateRevision.companion_id == companion_id,
        )).scalar_one_or_none()
        if source is None:
            raise RelationshipMutationError("RELATIONSHIP_REVISION_NOT_FOUND", "Relationship revision not found.")
        state = session.execute(select(RelationshipState).where(
            RelationshipState.id == source.relationship_state_id,
            RelationshipState.companion_id == companion_id,
        ).with_for_update()).scalar_one_or_none()
        if state is None:
            raise RelationshipMutationError("RELATIONSHIP_STATE_NOT_FOUND", "Relationship state not found.")
        if state.current_revision_id != source.id:
            raise RelationshipMutationError(
                "RELATIONSHIP_REVISION_NOT_CURRENT",
                "Only the current relationship revision can be corrected; refresh before retrying.",
            )
        if state.revision != expected_revision:
            raise RelationshipMutationError(
                "RELATIONSHIP_REVISION_CONFLICT", "Relationship state changed after it was loaded.",
                {"expected_revision": expected_revision, "current_revision": state.revision},
            )
        before = _state_snapshot(state)
        belief_before = dict(state.belief_state_json or {})
        target = dict(source.snapshot_before_json or {})
        target_belief = dict(source.belief_before_json or {})
        if not target or not target_belief:
            raise RelationshipMutationError("RELATIONSHIP_REVISION_NOT_CORRECTABLE", "Source revision has no restorable before-state.")
        previous_events = list(session.execute(select(RelationshipEvent).where(
            RelationshipEvent.state_revision_id == source.id
        )).scalars())
        previous_by_dimension = {row.dimension: row for row in previous_events}
        changed = []
        for dimension in DIMENSIONS:
            old = float(getattr(state, dimension))
            new = float(target[dimension])
            setattr(state, dimension, new)
            setattr(state, f"{dimension}_trend", new - old)
            if abs(new - old) > 1e-12:
                changed.append((dimension, old, new))
        state.revision += 1
        state.belief_state_json = target_belief
        state.summary = str(target.get("summary") or "Relationship judgment corrected")
        state.last_changed_at = now
        state.updated_at = now
        after = _state_snapshot(state)
        revision = RelationshipStateRevision(
            user_id=state.user_id,
            companion_id=state.companion_id,
            relationship_state_id=state.id,
            previous_revision_id=state.current_revision_id,
            restored_from_revision_id=source.id,
            revision=state.revision,
            operation="corrected",
            reason=reason,
            snapshot_before_json=before,
            snapshot_after_json=after,
            belief_before_json=belief_before,
            belief_after_json=target_belief,
            algorithm_version=ALGORITHM_VERSION,
        )
        session.add(revision)
        session.flush()
        group_id = uuid.uuid4()
        explanation_ids = []
        for dimension, old, new in changed:
            superseded = previous_by_dimension.get(dimension)
            stats = summarize_beliefs(target_belief)[dimension]
            event = RelationshipEvent(
                user_id=state.user_id, companion_id=state.companion_id,
                conversation_id=superseded.conversation_id if superseded else None,
                trace_run_id=superseded.trace_run_id if superseded else None,
                dimension=dimension, delta=new - old, previous_value=old, new_value=new,
                reason=reason, source_memory_ids=[], source_message_ids=[],
                state_revision_id=revision.id, event_group_id=group_id,
                supersedes_event_id=superseded.id if superseded else None,
                operation="corrected", evidence_weight=0.0,
                posterior_variance=stats["variance"],
                metadata_={"algorithm_version": ALGORITHM_VERSION, "corrects_revision_id": str(source.id)},
            )
            session.add(event)
            session.flush()
            explanation = RelationshipExplanationEvent(
                user_id=state.user_id, companion_id=state.companion_id,
                conversation_id=event.conversation_id, trace_run_id=event.trace_run_id,
                relationship_event_id=event.id, dimension=dimension,
                title="Relationship judgment corrected", explanation=reason,
                confidence=1.0, user_visible=True, user_confirmed=True,
                evidence_message_ids=[], evidence_memory_ids=[], evidence_growth_record_ids=[],
                metadata_={"operation": "corrected", "revision": revision.revision},
            )
            session.add(explanation)
            session.flush()
            explanation_ids.append(explanation.id)
        state.current_revision_id = revision.id
        state.last_explanation_event_id = explanation_ids[-1] if explanation_ids else state.last_explanation_event_id
        state.explanation_summary = {
            "revision": revision.revision,
            "operation": "corrected",
            "source_revision_id": str(source.id),
            "explanation_ids": [str(value) for value in explanation_ids],
        }
        session.commit()
        session.refresh(state)
        session.refresh(revision)
        return {"state": _state_dict(state), "revision": _revision_dict(revision)}


def _validate_sources(
    session: Session,
    companion_id: uuid.UUID,
    message_ids: list[uuid.UUID],
    memory_ids: list[uuid.UUID],
    *,
    conversation_id: uuid.UUID | None = None,
    evidence_quotes: list[dict[str, Any]] | None = None,
) -> None:
    if message_ids:
        message_scope = select(Message).where(
            Message.id.in_(message_ids),
            Message.companion_id == companion_id,
            Message.deleted_at.is_(None),
        )
        if conversation_id is not None:
            message_scope = message_scope.where(Message.conversation_id == conversation_id)
        messages = list(session.execute(message_scope).scalars())
        if {message.id for message in messages} != set(message_ids):
            raise RelationshipMutationError("RELATIONSHIP_EVIDENCE_SCOPE_MISMATCH", "Message evidence is missing or outside Companion scope.")
        user_text = "\n".join(message.content for message in messages if message.role == "user")
        assistant_text = "\n".join(message.content for message in messages if message.role == "assistant")
        for quote in evidence_quotes or []:
            user_quote = str(quote.get("user") or "").strip()
            assistant_quote = str(quote.get("assistant") or "").strip()
            if not user_quote or user_quote not in user_text:
                raise RelationshipMutationError("RELATIONSHIP_EVIDENCE_QUOTE_MISMATCH", "User evidence quote is not present in persisted user messages.")
            if assistant_quote and assistant_quote not in assistant_text:
                raise RelationshipMutationError("RELATIONSHIP_EVIDENCE_QUOTE_MISMATCH", "Assistant evidence quote is not present in persisted assistant messages.")
    if memory_ids:
        found = set(session.execute(select(Memory.id).where(
            Memory.id.in_(memory_ids),
            Memory.companion_id == companion_id,
            Memory.owner_companion_id == companion_id,
            Memory.deleted_at.is_(None),
            Memory.consent_status.notin_(("blocked", "revoked", "pending_review")),
        )).scalars())
        if found != set(memory_ids):
            raise RelationshipMutationError("RELATIONSHIP_EVIDENCE_SCOPE_MISMATCH", "Memory evidence is missing, unreviewed, or outside Companion scope.")


def _new_state(user_id: uuid.UUID, companion_id: uuid.UUID, now: datetime) -> RelationshipState:
    beliefs = initial_beliefs(now)
    means = summarize_beliefs(beliefs)
    return RelationshipState(
        user_id=user_id,
        companion_id=companion_id,
        **{dimension: means[dimension]["mean"] for dimension in DIMENSIONS},
        summary="Relationship evidence initialized after user confirmation.",
        revision=0,
        belief_state_json=beliefs,
        last_evidence_at=None,
    )


def _state_snapshot(state: RelationshipState) -> dict[str, Any]:
    return {**{dimension: float(getattr(state, dimension)) for dimension in DIMENSIONS}, "summary": state.summary}


def _state_dict(state: RelationshipState | None) -> dict | None:
    if state is None:
        return None
    uncertainty = summarize_beliefs(state.belief_state_json) if state.belief_state_json else {}
    return {
        "id": str(state.id), "user_id": str(state.user_id), "companion_id": str(state.companion_id),
        "revision": state.revision, "current_revision_id": str(state.current_revision_id) if state.current_revision_id else None,
        **{dimension: float(getattr(state, dimension)) for dimension in DIMENSIONS},
        "summary": state.summary, "uncertainty": uncertainty,
        "last_evidence_at": state.last_evidence_at.isoformat() if state.last_evidence_at else None,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


def _candidate_dict(row: RelationshipCandidate) -> dict:
    return {
        "id": str(row.id), "companion_id": str(row.companion_id),
        "conversation_id": str(row.conversation_id) if row.conversation_id else None,
        "status": row.status, "summary": row.summary,
        "dimension_signals": row.dimension_signals_json or [],
        "source_message_ids": [str(value) for value in row.source_message_ids or []],
        "source_memory_ids": [str(value) for value in row.source_memory_ids or []],
        "evidence_quotes": row.evidence_quotes_json or [],
        "validation": row.validation_json or {},
        "evidence_score": row.evidence_score, "confidence": row.confidence,
        "risk_level": row.risk_level, "requires_user_review": row.requires_user_review,
        "expected_state_revision": row.expected_state_revision,
        "provider_name": row.provider_name, "model_name": row.model_name,
        "algorithm_version": row.algorithm_version,
        "committed_revision_id": str(row.committed_revision_id) if row.committed_revision_id else None,
        "review_reason": row.review_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _revision_dict(row: RelationshipStateRevision | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": str(row.id), "companion_id": str(row.companion_id),
        "relationship_state_id": str(row.relationship_state_id),
        "source_candidate_id": str(row.source_candidate_id) if row.source_candidate_id else None,
        "previous_revision_id": str(row.previous_revision_id) if row.previous_revision_id else None,
        "restored_from_revision_id": str(row.restored_from_revision_id) if row.restored_from_revision_id else None,
        "revision": row.revision, "operation": row.operation, "reason": row.reason,
        "snapshot_before": row.snapshot_before_json or {}, "snapshot_after": row.snapshot_after_json or {},
        "algorithm_version": row.algorithm_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _explanation_for_event(
    event: RelationshipEvent,
    candidate: RelationshipCandidate,
    stats: dict[str, float],
) -> RelationshipExplanationEvent:
    return RelationshipExplanationEvent(
        user_id=event.user_id, companion_id=event.companion_id,
        conversation_id=event.conversation_id, trace_run_id=event.trace_run_id,
        relationship_event_id=event.id, dimension=event.dimension,
        title="Reviewed relationship understanding",
        explanation=candidate.summary,
        confidence=candidate.confidence,
        user_visible=True, user_confirmed=True,
        evidence_message_ids=candidate.source_message_ids or [],
        evidence_memory_ids=candidate.source_memory_ids or [],
        evidence_growth_record_ids=[],
        metadata_={
            "algorithm_version": ALGORITHM_VERSION,
            "posterior_variance": stats["variance"],
            "effective_evidence": stats["effective_evidence"],
        },
    )


def _uuid_list(values: Any) -> list[uuid.UUID]:
    return list(dict.fromkeys(uuid.UUID(str(value)) for value in (values or [])))


def _optional_uuid(value: Any) -> uuid.UUID | None:
    return uuid.UUID(str(value)) if value else None


def _unit(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))
