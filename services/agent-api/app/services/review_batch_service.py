"""Create, list, get, and apply review batches."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.review_batch import ReviewBatch
from app.db.models.memory import MemoryCandidate
from app.db.models.growth import GrowthCandidate
from app.db.models.memory_abstraction_candidate import MemoryAbstractionCandidate

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def create_batch(data: dict) -> dict:
    with get_session() as s:
        item_refs = data.get("item_refs", [])
        rb = ReviewBatch(
            user_id=uuid.UUID(data["user_id"]),
            companion_id=uuid.UUID(data["companion_id"]),
            conversation_id=uuid.UUID(data["conversation_id"]) if data.get("conversation_id") else None,
            batch_type=data["batch_type"],
            title=data.get("title"),
            description=data.get("description"),
            item_count=len(item_refs),
            accepted_count=0,
            edited_count=0,
            rejected_count=0,
            skipped_count=0,
            status="open",
            item_refs=item_refs,
            result_json={},
        )
        s.add(rb)
        s.commit()
        s.refresh(rb)
        return _rb_dict(rb)


def list_batches(
    companion_id: uuid.UUID | None = None,
    batch_type: str | None = None,
    status: str | None = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    with get_session() as s:
        stmt = select(ReviewBatch)
        if companion_id:
            stmt = stmt.where(ReviewBatch.companion_id == companion_id)
        if batch_type:
            stmt = stmt.where(ReviewBatch.batch_type == batch_type)
        if status:
            stmt = stmt.where(ReviewBatch.status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(ReviewBatch.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = [_rb_dict(rb) for rb in s.execute(stmt).scalars().all()]
        return {"items": items, "total": total}


def get_batch(batch_id: uuid.UUID) -> dict | None:
    with get_session() as s:
        rb = s.get(ReviewBatch, batch_id)
        if not rb:
            return None
        return _rb_dict(rb)


def apply_batch(batch_id: uuid.UUID, data: dict) -> dict:
    """Iterate over actions list and apply each one.

    Each action specifies what to do with a candidate:
      - accept_memory / reject_memory: operates on MemoryCandidate
      - commit_growth: operates on GrowthCandidate
      - reject_abstraction: operates on MemoryAbstractionCandidate

    Tracks counts and returns per-item results.
    """
    from app.services import memory_service, relationship_service

    prepared_memories: dict[uuid.UUID, dict] = {}
    with get_session() as read_session:
        for action in data.get("actions", []):
            if action.get("action") != "accept_memory":
                continue
            try:
                candidate_id = uuid.UUID(action.get("candidate_id", ""))
            except (TypeError, ValueError):
                continue
            candidate = read_session.get(MemoryCandidate, candidate_id)
            if candidate and candidate.status == "pending":
                prepared_memories[candidate_id] = memory_service.prepare_saved_memory_content(candidate.content)

    with get_session() as s:
        rb = s.get(ReviewBatch, batch_id)
        if not rb:
            return None

        actions = data.get("actions", [])
        results = []
        accepted = 0
        edited = 0
        rejected = 0
        skipped = 0

        for action in actions:
            action_type = action.get("action", "")
            candidate_id = action.get("candidate_id")
            item_result = {"action": action_type, "candidate_id": candidate_id, "status": "skipped"}

            if not candidate_id:
                item_result["status"] = "skipped"
                item_result["reason"] = "No candidate_id provided"
                skipped += 1
                results.append(item_result)
                continue

            try:
                cid = uuid.UUID(candidate_id)
            except (ValueError, TypeError):
                item_result["status"] = "skipped"
                item_result["reason"] = "Invalid candidate_id"
                skipped += 1
                results.append(item_result)
                continue

            if action_type == "accept_memory":
                cand = s.get(MemoryCandidate, cid)
                if cand and cand.status in ("pending",):
                    cand.status = "accepted"
                    cand.updated_at = datetime.now(timezone.utc)
                    s.flush()
                    # Auto-commit: create Memory directly
                    from app.db.models.memory import Memory
                    mem = Memory(
                        user_id=cand.user_id,
                        companion_id=cand.companion_id,
                        owner_companion_id=cand.companion_id,
                        conversation_id=cand.conversation_id,
                        memory_scope_type="private_companion",
                        memory_layer="companion_private",
                        type=cand.suggested_type,
                        content=cand.content,
                        summary=cand.suggested_summary or cand.content[:200],
                        importance=cand.importance,
                        confidence=cand.confidence,
                        memory_strength=max(0.5, cand.score or 0.5),
                        state="active",
                        consent_status="user_confirmed",
                    )
                    memory_service.initialize_saved_memory_in_session(
                        s, mem, prepared_memories[cid],
                        reason="user_accepted_review_batch_memory",
                        source_candidate_id=cand.id,
                    )
                    cand.status = "committed"
                    cand.accepted_memory_id = mem.id
                    item_result["status"] = "accepted"
                    item_result["memory_id"] = str(mem.id)
                    accepted += 1
                elif cand and cand.status == "committed":
                    item_result["status"] = "skipped"
                    item_result["reason"] = "Already committed"
                    skipped += 1
                else:
                    item_result["status"] = "skipped"
                    item_result["reason"] = f"Cannot accept memory candidate with status {cand.status if cand else 'not_found'}"
                    skipped += 1

            elif action_type == "reject_memory":
                cand = s.get(MemoryCandidate, cid)
                if cand:
                    cand.status = "rejected"
                    cand.feedback_label = "negative"
                    cand.updated_at = datetime.now(timezone.utc)
                    item_result["status"] = "rejected"
                    rejected += 1
                else:
                    item_result["status"] = "skipped"
                    item_result["reason"] = "Memory candidate not found"
                    skipped += 1

            elif action_type == "commit_growth":
                cand = s.get(GrowthCandidate, cid)
                if cand and cand.status in ("candidate", "accepted"):
                    from app.db.models.growth import GrowthRecord
                    gr = GrowthRecord(
                        user_id=cand.user_id,
                        companion_id=cand.companion_id,
                        source_candidate_id=cand.id,
                        type=cand.type,
                        content=cand.content,
                        reason=cand.reason,
                        evidence_memory_ids=cand.evidence_memory_ids or [],
                        evidence_message_ids=cand.evidence_message_ids or [],
                        impact_scope=cand.impact_scope or [],
                        status="committed",
                    )
                    s.add(gr)
                    s.flush()
                    cand.status = "committed"
                    cand.committed_growth_record_id = gr.id
                    cand.updated_at = datetime.now(timezone.utc)
                    item_result["status"] = "accepted"
                    item_result["growth_record_id"] = str(gr.id)
                    accepted += 1
                else:
                    item_result["status"] = "skipped"
                    item_result["reason"] = f"Cannot commit growth candidate with status {cand.status if cand else 'not_found'}"
                    skipped += 1

            elif action_type == "reject_abstraction":
                cand = s.get(MemoryAbstractionCandidate, cid)
                if cand:
                    cand.status = "rejected"
                    cand.rejection_reason = action.get("reason") or "Batch rejected"
                    cand.updated_at = datetime.now(timezone.utc)
                    item_result["status"] = "rejected"
                    rejected += 1
                else:
                    item_result["status"] = "skipped"
                    item_result["reason"] = "Abstraction candidate not found"
                    skipped += 1

            elif action_type == "commit_relationship":
                try:
                    result = relationship_service.commit_relationship_candidate(
                        cid,
                        rb.companion_id,
                        expected_revision=int(action.get("expected_revision", 0)),
                        reason=action.get("reason") or "Accepted from review batch",
                    )
                    item_result["status"] = "accepted"
                    item_result["relationship_revision_id"] = result["revision"]["id"]
                    accepted += 1
                except relationship_service.RelationshipMutationError as exc:
                    item_result["status"] = "skipped"
                    item_result["reason"] = exc.code
                    skipped += 1

            elif action_type == "reject_relationship":
                try:
                    relationship_service.reject_relationship_candidate(
                        cid,
                        rb.companion_id,
                        reason=action.get("reason") or "Rejected from review batch",
                    )
                    item_result["status"] = "rejected"
                    rejected += 1
                except relationship_service.RelationshipMutationError as exc:
                    item_result["status"] = "skipped"
                    item_result["reason"] = exc.code
                    skipped += 1

            else:
                item_result["status"] = "skipped"
                item_result["reason"] = f"Unknown action type: {action_type}"
                skipped += 1

            results.append(item_result)

        # Update batch counts and status
        rb.accepted_count = accepted
        rb.rejected_count = rejected
        rb.skipped_count = skipped
        rb.edited_count = edited
        rb.status = "completed"
        rb.completed_at = datetime.now(timezone.utc)
        rb.result_json = {"results": results}

        s.commit()
        s.refresh(rb)
        return {
            "batch": _rb_dict(rb),
            "results": results,
        }


def _rb_dict(rb: ReviewBatch) -> dict:
    return {
        "id": str(rb.id),
        "user_id": str(rb.user_id),
        "companion_id": str(rb.companion_id),
        "conversation_id": str(rb.conversation_id) if rb.conversation_id else None,
        "batch_type": rb.batch_type,
        "title": rb.title,
        "description": rb.description,
        "item_count": rb.item_count,
        "accepted_count": rb.accepted_count,
        "edited_count": rb.edited_count,
        "rejected_count": rb.rejected_count,
        "skipped_count": rb.skipped_count,
        "status": rb.status,
        "completed_at": rb.completed_at.isoformat() if rb.completed_at else None,
        "item_refs": rb.item_refs,
        "result_json": rb.result_json,
        "created_at": rb.created_at.isoformat() if rb.created_at else None,
        "updated_at": rb.updated_at.isoformat() if rb.updated_at else None,
    }
